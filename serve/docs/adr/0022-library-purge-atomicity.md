# ADR-0022: Library Purge — Cross-Storage Atomicity Strategy

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: M7 safety red line; BACKEND_ROADMAP §4.2 (DeleteConfirmModal real purge)
**Related**: ADR-0003 (Library as Data Partition), ADR-0014 (Activity Log),
ADR-0007 (Error Envelope), ADR-0011 (Notification), ADR-0015 (Cost Cap),
ADR-0001 (Modular Monolith)

## Context

`DELETE /v1/libraries/{lib}?purge=1` must remove a Library's data from
**five physically-separate backends**:

| # | Backend         | What is stored                                      | Purge primitive                                  |
|---|-----------------|-----------------------------------------------------|--------------------------------------------------|
| 1 | Qdrant          | `chunks_<library_id>` collection (vectors)          | `client.delete_collection(...)`                  |
| 2 | Neo4j           | composite database `kg_<library_id>`                | `DROP DATABASE kg_<library_id>` (or label sweep) |
| 3 | BM25 (OpenSearch / BM25S) | per-Library index                         | `index.delete()`                                 |
| 4 | MinIO           | corpus + KG snapshots under `<library_id>/`         | `remove_objects(prefix=...)`                     |
| 5 | Postgres        | rows in `documents`, `chunks`, `library_config`, `library_daily_cost`, `notifications`, `answer_feedback`, `eval_snapshots`, `activity_log`, `conversations`, `turns`, `memory_entries`, `libraries` | `DELETE ... WHERE library_id = ?` |

Today's behaviour is **only metadata is deleted**: the `libraries` row goes
but Qdrant collection, Neo4j DB, BM25 index, and MinIO prefix all stay. A
user who deletes a Library and re-creates it under the same slug inherits
the prior data — a **CRITICAL data-integrity bug** (PRD §17 R11) and a
silent disk leak.

The fix sounds easy ("just delete the rest"), but there are five real
problems:

1. **No cross-backend transaction**: Qdrant / Neo4j / BM25 / MinIO have no
   2PC; even Postgres-only XA is operationally heavy. A naive sequential
   delete that fails halfway leaves the Library in an inconsistent half-purged
   state.
2. **Partial-failure recovery**: a worker restart between step 3 and step 4
   must be able to resume. Without explicit state, the purge is "lost".
3. **Idempotency**: each adapter must accept "I already purged you" and
   "you never existed" without raising — otherwise retries explode.
4. **FK ordering**: Postgres has FK constraints (`documents → libraries`,
   `chunks → documents`, etc.) — wrong delete order errors out and aborts.
5. **Misuse**: `purge` is irrevocable; one wrong click loses a research
   month. PRD §14.2 calls for a `DeleteConfirmModal` with slug confirmation.

## Decision

Adopt a **Saga + state-machine** approach: idempotent per-backend purge
operations driven by an explicit `LibraryPurgeStatus` enum, with
worker-level resume-on-restart for partial failures.

### 1. State machine

```
                  POST /v1/libraries/{id}?purge=1
                              │
                              ▼
                    ┌────────────────────┐
                    │   active           │
                    └─────────┬──────────┘
                              │ admin.start_purge()
                              ▼
                    ┌────────────────────┐
        ┌───────────┤   purging          │◄──────────┐
        │           └─────────┬──────────┘           │
        │                     │                      │ worker resume
        │  any adapter raises │ all adapters ok      │
        │                     ▼                      │
        ▼            ┌────────────────────┐          │
┌────────────────┐   │   pg_pending       │          │
│ partial_purged │   └─────────┬──────────┘          │
└────────┬───────┘             │ pg DELETE rows      │
         │ retry               ▼                      │
         └──────────┐  ┌────────────────────┐         │
                    └─►│   purged           │─────────┘
                       └────────────────────┘
                              │ TTL 30s undo window (optional)
                              ▼
                       row hard-deleted
```

The `libraries.status` column is extended to include the new states:

```python
class LibraryStatus(StrEnum):
    HEALTHY          = "healthy"
    INDEXING         = "indexing"
    STALE_COMMUNITY  = "stale_community"
    PURGING          = "purging"          # NEW: purge in flight
    PARTIAL_PURGED   = "partial_purged"   # NEW: at least one adapter failed
    PG_PENDING       = "pg_pending"       # NEW: stores cleared, pg rows pending
    PURGED           = "purged"           # NEW: terminal, row about to be removed
```

Once `status = purged`, the next `library_status_check` cron sweep removes
the row (or, if undo window is enabled per §6, after 30 s).

### 2. Idempotent `purge_library` Protocol contract

Every storage adapter implements:

```python
class LibraryAware(Protocol):
    """Mixed into every adapter that holds Library-scoped data."""

    async def init_library(self, library_id: str) -> None: ...

    async def purge_library(self, library_id: str) -> PurgeReceipt: ...
        # MUST be idempotent: missing collection / DB / index / prefix
        # is NOT an error and returns receipt(found=False).

class PurgeReceipt(BaseModel):
    library_id:   str
    backend:      Literal["qdrant", "neo4j", "bm25", "minio", "postgres"]
    found:        bool                  # was anything actually present?
    deleted:      int                   # rows / objects / 1 for collections
    duration_ms:  int
    error:        str | None = None     # exception message if raised mid-way
```

Idempotency rules per backend:

- **Qdrant**: catch `UnexpectedResponse(404)` on missing collection → `found=False, error=None`.
- **Neo4j**: `DROP DATABASE IF EXISTS` is idempotent; community edition uses label sweep with a transaction-level retry of 3.
- **BM25S / OpenSearch**: `index.delete(ignore=[404])` style guards.
- **MinIO**: `remove_objects` returns silent on missing keys; we list first then delete.
- **Postgres**: `DELETE` of zero rows is idempotent by definition; we still emit a `PurgeReceipt`.

Adapters that *do* raise on missing resources are wrapped at the
adapter-edge to translate to `found=False`, so the saga never sees a
"missing" raised as failure.

### 3. Saga orchestration

```python
# packages/core/library_admin.py

PURGE_ORDER: tuple[str, ...] = (
    "qdrant",     # vectors first — no other store references them
    "bm25",       # bm25 next — independent
    "neo4j",      # KG next
    "minio",      # blob storage next
    # postgres LAST so that we always have *some* metadata while volatiles
    # are vanishing; pg rows are guarded by FK ordering inside step 5.
)

async def purge_library(
    library_id: str,
    *,
    requested_by: str | None,
    force_resume: bool = False,
) -> LibraryPurgeResult:
    # Step 1: state transition active → purging (CAS-protected)
    transition_to(library_id, LibraryStatus.PURGING)
    activity.record(library_id, "library_purge_started", payload={...})

    receipts: list[PurgeReceipt] = []
    failures: list[str] = []

    for backend_name in PURGE_ORDER:
        adapter = get_adapter(backend_name)
        try:
            r = await adapter.purge_library(library_id)
            receipts.append(r)
        except Exception as e:
            failures.append(backend_name)
            receipts.append(PurgeReceipt(
                library_id=library_id, backend=backend_name,
                found=False, deleted=0, duration_ms=0, error=str(e)
            ))

    if failures:
        transition_to(library_id, LibraryStatus.PARTIAL_PURGED,
                      meta={"failed_backends": failures, "receipts": receipts})
        notify(library_id, type=NotificationType.PURGE_PARTIAL,
               severity="danger", payload={"failed_backends": failures})
        return LibraryPurgeResult(status="partial_purged", receipts=receipts)

    # All non-pg adapters cleared; clear Postgres rows in FK-safe order
    transition_to(library_id, LibraryStatus.PG_PENDING)
    pg_receipt = await purge_postgres_rows(library_id)
    receipts.append(pg_receipt)

    transition_to(library_id, LibraryStatus.PURGED)
    activity.record(library_id, "library_purged",
                    payload={"requested_by": requested_by, "receipts": receipts})
    return LibraryPurgeResult(status="purged", receipts=receipts)
```

The Postgres step uses one transaction with explicit FK-safe order:

```python
async def purge_postgres_rows(library_id: str) -> PurgeReceipt:
    async with pg.transaction():
        await pg.execute("DELETE FROM turns          WHERE conversation_id IN "
                         "(SELECT id FROM conversations WHERE library_id = $1)",
                         library_id)
        await pg.execute("DELETE FROM conversations  WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM memory_entries WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM activity_log   WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM notifications  WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM answer_feedback WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM eval_snapshots WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM library_daily_cost WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM library_config WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM chunks         WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM documents      WHERE library_id = $1", library_id)
        await pg.execute("DELETE FROM libraries      WHERE library_id = $1", library_id)
    return PurgeReceipt(...)
```

Order: leaf tables first, root last. The whole Postgres block is one
transaction — either all rows go or none. (Single-DB transactions *are*
ACID; the cross-backend problem is solved separately by the Saga.)

### 4. Resume on worker restart

`apps/worker/main.py` startup hook:

```python
async def resume_partial_purges() -> None:
    rows = await pg.fetch(
        "SELECT library_id FROM libraries "
        "WHERE status IN ('purging', 'partial_purged', 'pg_pending')"
    )
    for r in rows:
        log.warning("resuming purge", library_id=r["library_id"])
        # Re-runs the saga; idempotent purge_library on every adapter
        # makes already-cleared backends a no-op (found=False).
        await purge_library(r["library_id"], requested_by="worker_resume", force_resume=True)
```

Hence "worker dies mid-purge" is recoverable: at next startup the worker
picks up any `purging` / `partial_purged` / `pg_pending` Library and replays
the saga. Idempotency guarantees re-run safety.

### 5. Activity log and audit trail

Per ADR-0014, the Activity Log is the *audit trail* and **must survive the
Library it logs about**. We solve this by:

- Writing `library_purge_started` and `library_purged` events with full
  receipts payload **before** the Postgres saga step nukes the
  `activity_log` rows for this Library.
- Mirroring those two events into a separate `archived_activity_log`
  table at write time when the event type is `library_purge_*`.
- Postgres saga step **does** delete this Library's rows from
  `activity_log` (owned data) but **does not** touch
  `archived_activity_log` (audit data).

This keeps a tamper-evident record of "Library X was purged at T by User
U" available indefinitely (90-day default retention from ADR-0014 may be
overridden to "forever" for `library_purge_*` events).

### 6. Optional 30-second undo window

A user-friendly safety net: between `status = purged` and actual row
deletion, a 30-second window allows a single API call:

```
POST /v1/libraries/{id}/undo-purge   (only valid in PURGED state, < 30s old)
  → restores libraries row only; data backends are unrecoverable
  → returns 410 Gone if window expired
```

**This window only undoes the metadata row**, not the data — by the time
`status = purged` is reached the volatiles are gone. The undo therefore
restores a **shell Library** with the same slug; the user's data is still
lost. We considered this misleading, so the undo path is **off by default**
and hidden behind `Settings.purge_undo_enabled = False`. The
DeleteConfirmModal makes irreversibility crystal clear regardless.

### 7. UX guardrails — DeleteConfirmModal

Frontend (per BACKEND_ROADMAP §4.2):
- Modal opens with the Library's full `slug` shown.
- User must **type the complete slug** (case-sensitive) into a confirm input.
- Submit button stays disabled until input matches `slug`.
- A second confirmation checkbox: "I understand this is irreversible."

Backend **must independently re-validate** the slug match in the
`DELETE` handler — never trust client-side gating (PRD §16.4 security
posture):

```python
@router.delete("/v1/libraries/{library_id}")
async def delete_library(
    library_id: str,
    purge: bool = Query(False),
    confirm_slug: str = Query(...),
    principal: Principal = Depends(get_current_principal),
) -> Response:
    lib = await library_repo.get_or_404(library_id)
    if confirm_slug != lib.slug:
        raise APIError(ErrorCode.PURGE_SLUG_MISMATCH, status=400)
    if not purge:
        # Soft delete: mark archived, keep volatiles (out of scope here)
        ...
    else:
        # Hard purge — the Saga from §3
        await library_admin.purge_library(library_id, requested_by=principal.user_id)
    return Response(status_code=202)
```

`PURGE_SLUG_MISMATCH` is a new `ErrorCode` per ADR-0007.

### 8. Test requirements (chaos)

Per BACKEND_ROADMAP §7 BR05, the purge implementation MUST include:

```
tests/integration/test_library_purge_chaos.py:
  - test_purge_happy_path
  - test_purge_qdrant_fails_then_retry_succeeds
  - test_purge_neo4j_fails_then_retry_succeeds
  - test_purge_minio_fails_then_retry_succeeds
  - test_purge_postgres_fk_violation_rolls_back
  - test_purge_worker_restart_mid_saga_resumes
  - test_purge_when_collection_already_missing_succeeds (idempotency)
  - test_purge_double_invocation_is_safe (concurrent admin clicks)
  - test_purge_with_slug_mismatch_returns_400
  - test_archived_activity_log_preserved
```

Each chaos test injects a fault into one adapter via fixture monkey-patch
and asserts the state machine transitions correctly to
`partial_purged` then re-runs to `purged`.

## Consequences

### Positive

- **No data leak**: re-creating the same slug yields a fresh Library;
  R11 is closed.
- **Resilient to crashes**: explicit state + idempotent adapters → workers
  can die anywhere mid-saga without leaving the system stuck.
- **Auditable**: `archived_activity_log` keeps a permanent record of who
  purged what when, even after the Library is gone.
- **No 2PC complexity**: the saga + idempotency pattern matches the
  storage layer's actual capabilities.

### Negative

- **Eventual rather than atomic**: a Library can be observably
  `partial_purged` for the duration of a retry (seconds to minutes for the
  90 % case; longer if a backend is fully down). Downstream consumers must
  treat "Library not in `healthy`" set as "not usable".
- **Audit table grows unboundedly** for purge events. Mitigated by the
  90-day default retention (ADR-0014) — purge events explicitly **opt out**
  of expiry, so they accumulate. We accept this as a feature, not a bug;
  ten purge events a year is negligible volume.
- **Slug squatting**: after `status = purged` the slug is free for reuse
  immediately. A user could re-create with the same slug while the worker
  is still running the saga on the old one. **Mitigation**: the
  `libraries.slug` UNIQUE constraint stays enforced; while
  `status ∈ {purging, partial_purged, pg_pending}`, the row exists, so
  re-create fails with 409. Only after `purged → row deleted` is the slug
  free.

### Risks

- **R-PURGE-1**: Worker restart during `partial_purged` state never
  triggers retry (e.g. resume hook bug). **Mitigation**: a periodic cron
  scan (every 15 min) for Libraries in `partial_purged` ≥ 1 h old, raising
  a danger Notification to the operator.
- **R-PURGE-2**: Adapter reports `purge_library` success but data is still
  there (silent failure). **Mitigation**: post-purge probe — for Qdrant /
  Neo4j / BM25 / MinIO, attempt a *read* immediately after delete and
  expect 404 / not-found. Probe failure transitions to `partial_purged`.
- **R-PURGE-3**: User accidentally purges. **Mitigations** (defence in
  depth):
  1. DeleteConfirmModal with full-slug typing
  2. Backend re-validates slug match
  3. Optional `Settings.purge_undo_enabled` 30 s window
  4. Activity log + danger-severity Notification on every purge invocation
- **R-PURGE-4**: A future adapter is added that does not implement
  idempotent `purge_library`. **Mitigation**: `tach` rule enforces that
  every package implementing `LibraryAware` provides both `init_library`
  and `purge_library`; a CI test instantiates each adapter and calls
  `purge_library` against a non-existent ID, expecting `found=False`.

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| **Cross-backend 2PC / XA** | Qdrant / Neo4j / BM25 / MinIO have no XA support. Implementing a custom 2PC coordinator adds a critical-path failure mode and an order of magnitude of code for a problem the saga solves. |
| **Soft delete** (mark `is_deleted=true`, keep data) | Disk usage for vectors + KG of an abandoned 5 k paper Library is ~30 GB. Users delete *because* they want the disk back. Also creates indefinite Cost Cap accumulation ambiguity (does a soft-deleted Library count?). |
| **Outbox / event-driven** (write a `purge_requested` event, consumers individually act) | Adds Postgres pub/sub or message broker. Overkill for at-most-monthly events. Saga over our existing in-process call-graph is simpler and tach-compatible. |
| **Postgres-first delete then volatiles** | Loses ability to re-resume on worker crash — the metadata is gone, so we cannot find the Library to retry. Volatiles → metadata is the right order for recovery. |
| **One giant cross-backend transaction with manual rollback per backend** | Adapter-specific rollback is brittle (some operations like Qdrant `delete_collection` are non-rollbackable). Saga + state-machine is the textbook pattern for exactly this shape of problem. |
| **No chaos tests** | Without them BR05 is unmitigated. Mandatory. |

## Open Questions

- **Q1**: Should we offer a `DELETE ?purge=0` (soft-delete-style, archive
  metadata only, free volatiles) as a separate operation? **Tentative**:
  no — soft delete and purge are different mental models and the latter is
  what users want when they click "Delete Library". We may revisit if α
  testers ask for an "archive" operation.
- **Q2**: Should purge cascade to `eval_snapshots` rows that aggregate
  *across* Libraries? **Tentative**: there are no such rows in the M7 schema —
  every snapshot row is per-Library. But ADR-0021 alerting may compute
  cross-Library aggregates that should not include purged Libraries. The
  alert engine reads from current Library list; this is naturally handled.
- **Q3**: Should we surface a real-time SSE stream of purge progress to the
  UI? **Tentative**: per-stage progress is nice-to-have but the DeleteConfirmModal
  closes immediately and the user expects the operation to "just work";
  notification on completion (or failure) is the contract. SSE is P2.
- **Q4**: Embedding cache (Redis) — does it carry per-Library entries? If
  yes, it needs an adapter too. **Action**: audit
  `packages/embedding/cache.py`; if cache is shared across Libraries (it
  should not be, but check), add a sixth backend to `PURGE_ORDER`.

## Relationship to Other ADRs

- **ADR-0003 (Library as Data Partition)**: this ADR is the operational
  closure of ADR-0003 — every backend named in §12.5 is enumerated in
  `PURGE_ORDER`. Adding a new backend in the future requires updating
  this ADR.
- **ADR-0014 (Activity Log)**: defines retention and `archived_activity_log`
  precedent for purge audit trail.
- **ADR-0011 (Notification Center)**: emits `daily_cost_blocked`-style
  notifications for partial purges (`PURGE_PARTIAL`, severity=danger).
- **ADR-0007 (Error Envelope)**: introduces `PURGE_SLUG_MISMATCH`,
  `PURGE_IN_PROGRESS`, `PURGE_PARTIAL_FAILURE`, `PURGE_UNDO_EXPIRED` codes;
  HTTP statuses 400 / 409 / 500 / 410 respectively.
- **ADR-0015 (Cost Cap)**: `library_daily_cost` is one of the Postgres
  tables cleared in step 5; cost data does not survive a purge.
- **ADR-0001 (Modular Monolith)**: `library_admin` lives as a thin helper
  per `CODING_STANDARDS §6.5`, calling adapter Protocols directly — no
  new package.
- **ADR-0013 (Library State Machine)**: this ADR extends the enum with
  three new states; the `library_status_check` cron must be updated to
  ignore Libraries in `purging` / `partial_purged` / `pg_pending` states
  (do not flip them back to `healthy`).

## References

- PRD §14.2 (M7 — `Purge 复用 DeleteConfirmModal 模式`)
- PRD §16.6 (Library 维度纪律 — physical isolation per backend)
- PRD §17 R09 (Neo4j/Qdrant 数据丢失 — purge is the inverse risk:
  *intentional* loss must be complete)
- PRD §17 R11 (Library 数据混淆 — non-purge causes A's data to surface in
  B's answers)
- BACKEND_ROADMAP §4.2 (M2 DeleteConfirmModal — real purge gap)
- BACKEND_ROADMAP §6 P0 (item 4, ADR-0022 + 真 Purge — safety red line)
- BACKEND_ROADMAP §7 BR05 (跨存储 purge 部分失败 — primary mitigation)
- ADR-0003 (per-backend isolation strategy enumerated here)
- `packages/core/library_admin.py` (implementation site)
