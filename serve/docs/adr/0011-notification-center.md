# ADR-0011: Notification Center — Postgres + SSE

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: BACKEND_ROADMAP §2.3; PRD §14.2 (顶栏 Notify 中心), §14.3 D7.5
**Related**: ADR-0007 (SSE infra, error envelope), ADR-0009 (task queue producer), ADR-0010 (in-task event protocol)

## Context

PRD §14.2 specifies a top-bar **Notify center** ("任务完成、告警、配额提醒等")
and §14.3 D7.5 makes it an explicit deliverable: "Review/Reason/Hypothesize
可后台运行；完成时顶栏通知；任务页可恢复进度".

Today (post-M6) we have **no user-visible notification channel**:

- Task completion is observable only by polling `GET .../tasks/{id}`.
- `library_status_check` (ADR-0013, BACKEND_ROADMAP §2.5) has nowhere to
  surface "your community summary is now Stale".
- Daily-cost cap breaches (ADR-0015, BACKEND_ROADMAP §2.7) need to interrupt
  the user, not just write a log line.
- Worker-process down / Redis offline alerts can't reach the user.

The notification system is distinct from the in-task `TaskEvent` stream
(ADR-0010). Those events answer **"what is happening inside this task right
now?"**. Notifications answer **"what events outside my current page should
I know about?"** — they are durable, per-user, with read/unread state, and
must survive page reloads and browser closes.

### Forces

- **Durability**: a user closes the laptop on Friday, returns Monday, the
  Friday-evening Review-failed notification must still be there.
- **Read/unread state**: the top-bar red dot needs an authoritative count
  of unread items; that state must be persistent.
- **Cross-Library scope**: some notifications are global ("worker offline";
  "daily cost cap hit on multiple libraries"); most are per-Library.
- **Outbox semantics**: when a task transitions to terminal status (per
  ADR-0009), the notification insert MUST be in the same DB transaction as
  the `tasks.status` update. No "task completed but no notification" race.
- **Realtime push**: the top-bar dot should appear within ≤ 30 s of the
  triggering event (BACKEND_ROADMAP §2.3 DoD), so a passive 60 s polling
  loop is borderline.

## Decision

We implement the notification center as a **Postgres `notifications` table**
plus a **dedicated SSE endpoint** that streams new notifications and
supports historical pull on reconnect. No additional broker, no separate
storage tier.

### 1. Storage schema

```sql
CREATE TABLE notifications (
    id              TEXT PRIMARY KEY,                  -- ULID; sortable
    library_id      TEXT,                              -- NULL = global / system-wide
    type            TEXT NOT NULL,                     -- enum below
    severity        TEXT NOT NULL,                     -- info | warning | danger
    title           TEXT NOT NULL,                     -- short, < 80 chars
    body            TEXT,                              -- optional longer message
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    read            BOOLEAN NOT NULL DEFAULT FALSE,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '90 days'),
    -- For outbox dedup (e.g. retries of the same Review terminal write)
    dedup_key       TEXT,
    UNIQUE (dedup_key)
);

CREATE INDEX notifications_unread_idx
    ON notifications (created_at DESC)
    WHERE read = FALSE;

CREATE INDEX notifications_library_unread_idx
    ON notifications (library_id, created_at DESC)
    WHERE read = FALSE;

CREATE INDEX notifications_expires_idx
    ON notifications (expires_at);
```

Key choices:

- **ULID** for `id` (lexicographically sortable, monotonically increasing
  per-millisecond) — gives stable cursor pagination without a separate
  `seq` column.
- **Partial indexes on `read=FALSE`** — the unread dot count is a hot
  query; partial index keeps it cheap as the table grows.
- **`dedup_key`** — the outbox writer (worker job) computes a deterministic
  key like `task_completed:{task_id}` so a duplicate insert from an
  at-least-once retry no-ops via `ON CONFLICT (dedup_key) DO NOTHING`.
- **`expires_at`** with `+ 90 days` default — see TTL discussion below.

### 2. `Notification` Pydantic model

```python
# packages/core/models.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


NotificationType = Literal[
    # task lifecycle
    "task_completed",
    "task_failed",
    # ingest convenience aliases (a task_completed for ingest is also a UX-distinct event)
    "ingest_completed",
    "ingest_failed",
    # library state
    "library_status_changed",
    # operator-facing alerts
    "alert_triggered",
    # cost
    "daily_cost_warning",
    "daily_cost_blocked",
    # system-wide
    "worker_offline",
    "worker_recovered",
]


class Notification(BaseModel):
    """Per PRD §16.6, `library_id=None` means system-wide; not a list.

    Cross-Library aggregation (e.g. the Notify center listing items from
    every Library the user owns) happens at the **L5 orchestration**
    layer (the `/v1/notifications` endpoint) — never at the data
    Protocol level. The `NotificationStore` Protocol below enforces this.
    """

    id: str
    library_id: str | None = None
    type: NotificationType
    severity: Literal["info", "warning", "danger"]
    title: str
    body: str | None = None
    payload: dict = Field(default_factory=dict)
    read: bool = False
    read_at: datetime | None = None
    created_at: datetime
    expires_at: datetime
```

### 3. `NotificationStore` Protocol

```python
# packages/orchestration/notifications.py
from typing import Protocol


class NotificationStore(Protocol):
    """Library-scoped writes; user-scoped reads.

    Per PRD §16.6:
    - `record(library_id, ...)` writes to one library (or `None` for global).
    - `list_unread()` and `list_history()` are L5-only and may aggregate
      across the user's libraries — they return rows that each carry their
      own `library_id` for client-side filtering. They do NOT accept
      `library_ids: list` parameter (PRD §16.6 hard rule).
    """

    async def record(
        self,
        library_id: str | None,
        *,
        type: NotificationType,
        severity: Literal["info", "warning", "danger"],
        title: str,
        body: str | None = None,
        payload: dict | None = None,
        dedup_key: str | None = None,
    ) -> Notification: ...

    async def list_unread(
        self,
        principal_id: str,
        *,
        limit: int = 50,
    ) -> list[Notification]: ...

    async def list_history(
        self,
        principal_id: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Notification]: ...

    async def mark_read(
        self,
        notification_id: str,
    ) -> bool: ...

    async def mark_all_read(
        self,
        principal_id: str,
    ) -> int: ...
```

The Protocol scoping is intentional: the Notify center is the canonical
example of the **L5 read-only meta-view exception** in PRD §16.6 —
aggregated across the user's libraries, never used to drive a write.

### 4. HTTP / SSE surface

Three endpoints in `apps/api/routes/notifications.py`:

```
GET  /v1/notifications?unread=1&since=<iso8601>&limit=50
       → List[Notification], paginated by `created_at` desc

POST /v1/notifications/{id}/read
       → 204 No Content (idempotent)

POST /v1/notifications/read-all
       → {"marked": <int>}

GET  /v1/notifications/stream      (SSE; per-principal subscription)
       → events: notification_created, notification_read, ping
```

The SSE endpoint **reuses ADR-0007's SSE infrastructure** (`apps/api/sse.py`,
disconnect detection via `await request.is_disconnected()`). The wire format
is intentionally simpler than ADR-0010's `TaskEvent`:

```
event: notification_created
id: <ulid>
data: {<full Notification JSON>}

event: notification_read
id: <ulid>
data: {"id": "<ulid>"}
```

`Last-Event-ID` reconnect: server reads the ULID, runs
`SELECT * FROM notifications WHERE id > $1 AND <user_filter> ORDER BY id`
to backfill missed events, then attaches the live subscriber.

The live subscriber is fed by Postgres `LISTEN/NOTIFY` on the
`notifications_channel` channel (small payload: just the ULID + library_id
+ principal_id). On `NOTIFY`, the SSE handler refetches the row and pushes
it. This avoids depending on a separate broker for the realtime path while
keeping payloads small (Postgres NOTIFY caps payloads at 8 KB).

### 5. Outbox pattern with the worker

Per ADR-0009, when a worker job reaches a terminal state it does:

```python
# apps/worker/jobs/run_review.py (illustrative)
async with db.transaction():
    await tasks_repo.update_status(
        task_id=task_id,
        status="completed",
        finished_at=now(),
        result_pointer=pointer,
    )
    await notifications_store.record(
        library_id=library_id,
        type="task_completed",
        severity="info",
        title=f"Review «{title_short}» completed",
        body=None,
        payload={"task_id": task_id, "task_type": "review"},
        dedup_key=f"task_completed:{task_id}",
    )
# Postgres NOTIFY fires AFTER COMMIT (trigger on notifications insert),
# guaranteeing we never NOTIFY for a row that rolled back.
```

A Postgres trigger emits `pg_notify('notifications_channel', payload)` on
insert. Same DB transaction = no orphan notifications, no orphan task
state.

### 6. Cross-Library policy

| `library_id`     | Visible to                                   | Example |
|------------------|----------------------------------------------|---------|
| Specific lib     | Owner of the lib                             | `task_completed`, `library_status_changed`, `daily_cost_warning` |
| `NULL` (global)  | All authenticated principals                 | `worker_offline`, `worker_recovered`, system-wide `alert_triggered` |

The query that drives the top-bar dot is:

```sql
SELECT count(*) FROM notifications
WHERE read = FALSE
  AND (library_id IS NULL OR library_id = ANY($1::text[]))
  AND expires_at > now();
```

`$1` is the principal's library list (in v1 single-tenant: all libraries;
ADR-0007 bearer auth treats the operator as having global scope). When
multi-tenancy lands in v2, `$1` becomes the user's owned set.

### 7. TTL and retention

- Default `expires_at = created_at + 90 days`. A daily worker cron
  (`apps/worker/jobs/notifications_gc.py`) deletes rows past their
  `expires_at`. 90 days mirrors the Activity Log retention proposal in
  ADR-0014, keeping retention semantics consistent.
- `severity='danger'` notifications get **180 days** TTL (operators may
  need them for postmortems).
- Marking a notification read does NOT extend or shorten its TTL.

### 8. Read-state semantics

- A notification is created `read=FALSE`.
- `POST /v1/notifications/{id}/read` sets `read=TRUE, read_at=now()`. The
  call is idempotent — calling it twice is fine, no error.
- `read-all` marks every unread row visible to the principal as read; the
  return value is the count actually flipped (so the UI can show a toast).
- The SSE stream emits a `notification_read` event when `read=TRUE` is
  flipped (so a second open tab updates its dot count without polling).

## Consequences

### Positive

- A single SQL table answers every Notify center query (count unread,
  list with pagination, history backfill).
- Outbox in the same transaction as the worker's terminal write =
  exactly-once user-visible signals from the user's POV.
- Reuses Postgres + `LISTEN/NOTIFY` + ADR-0007 SSE infra. No new operational
  surface area.
- Notify history survives server restarts, Redis flushes, and worker crashes.
- 90 d retention gives operators a forensic trail without unbounded growth.

### Negative

- Postgres `LISTEN/NOTIFY` payload is capped at 8 KB; mitigated by sending
  only the row id and refetching. This is one extra DB roundtrip per push.
- A user with thousands of stale unread notifications would see degraded
  Notify-center load. Mitigated by `severity!='danger'` 90 d TTL plus the
  partial index on `read=FALSE`.
- One more SSE endpoint to maintain alongside ADR-0007 (QA) and ADR-0010
  (task events). The shared `apps/api/sse.py` keeps duplication small.

### Risks

| ID | Risk | Mitigation |
|----|------|-----------|
| N-R1 | A high-volume burst of notifications (e.g. 200-paper batch ingest) floods the user's dot | Worker MAY collapse per-batch ingest into one summary notification (`ingest_completed` with `payload.count=200`) instead of N rows. Job-level decision; protocol allows either |
| N-R2 | LISTEN/NOTIFY backlog if the SSE handler is slow / disconnected | Postgres queues NOTIFYs to the listening backend; if no backend is listening they are dropped. Reconnect path uses the durable table to backfill — no listener, no loss |
| N-R3 | Dedup key collisions (e.g. operator manually re-creates same task_id) | `dedup_key` includes `task_id` which is a ULID; collision is operationally impossible. Manual `dedup_key=None` is the documented escape hatch |
| N-R4 | Single-tenant `principal_id` scoping is a placeholder | ADR-0007 bearer auth has the same constraint. When multi-tenancy lands, `notifications` gains an `owner_principal_id TEXT` column with a backfill migration |

## Alternatives Considered

| Option | Pro | Con | Verdict |
|--------|-----|-----|---------|
| **Postgres + SSE** (chosen) | Durable; transactional outbox; reuses infra; SQL-queryable | Manual TTL GC; LISTEN/NOTIFY caveat | Best fit for v1 |
| Redis Streams (`XADD`/`XREAD`) | Built-in fan-out; consumer groups; very fast | History TTL is per-stream not per-user; read/unread is not native (would need a parallel store); replay is sequence-id only, no time queries; harder to query "show me last week's danger items" by SQL | Rejected — read/unread state is the killer. Redis would shadow Postgres for state |
| WebSocket | True full-duplex | Same proxy/upgrade friction as ADR-0007/0010 rejection; no value over SSE for one-way push; cancel/dismiss is HTTP anyway | Rejected — same reasoning as ADR-0007 |
| Email | Universal | Requires SMTP infra and user opt-in; latency unpredictable; spam filters; not realtime; severity-`info` notifications would be obnoxious | Rejected for v1 in-app; revisit as a *secondary* channel for `severity=danger` only |
| Slack/Discord webhook | Engaging; familiar | External dependency; per-user opt-in; not appropriate for solo-dev personal Library | Rejected |
| Browser Push API (Web Push) | Wakes the OS even when tab closed | VAPID infra, service worker plumbing, per-browser quirks; user-permission UX overhead | Rejected for v1 in favor of in-app SSE; Web Push is a v1.1 candidate |
| Server-side polling only | Simplest possible | 30 s tick → up to 30 s of perceived staleness; doubles the API request volume | Rejected — fails BACKEND_ROADMAP §2.3 DoD ("≤ 30 秒") and is wasteful |

### Why not Redis Streams

Redis Streams is a sound fit for **transient task progress** (which is why
ADR-0010 uses it). Notifications are different:

1. They have **per-user read state** that outlives delivery. A Stream entry
   has no concept of read/unread; we'd build a sidecar table anyway.
2. They are **queryable**: "show me all `daily_cost_blocked` events from
   last week, grouped by Library". SQL excels at this; Streams require
   loading + filtering in app code.
3. They are **rare**: a busy day produces ~100 notifications, not 100k.
   The throughput case for Streams doesn't apply.
4. The single-tenant v1 has small data volumes; the Postgres `notifications`
   table will not exceed 100k rows in any plausible scenario before v2.

If v2 brings true multi-tenancy and notification volumes explode, the
Protocol abstraction lets us swap to Streams + a state-tracking sidecar
without changing API contracts.

## Open Questions

1. **Quiet hours / digest mode**: should `severity=info` notifications
   batch into a daily digest if the user's prefs say so? Defer to v1.1
   pending real-user feedback.
2. **Per-Library mute**: should a user be able to mute notifications for
   one Library temporarily? Schema supports it via `library_config` (per
   ADR-0012); endpoint TBD.
3. **Mobile / desktop OS push**: out of scope for v1; revisit when first
   user requests it.
4. **Audit retention beyond 90 d**: do we ship an `archive` step that
   moves expired rows to MinIO compressed JSON? Probably yes, mirroring
   ADR-0014 Activity Log archival; deferred until first GC cycle observed.

## References

- BACKEND_ROADMAP §2.3 — notifications scope, model, DoD
- BACKEND_ROADMAP §2.5 — library status changes (notification trigger)
- BACKEND_ROADMAP §2.7 — daily cost cap (notification trigger)
- PRD §14.2 — top-bar Notify center
- PRD §14.3 D7.5 — background-task notification deliverable
- PRD §16.6 — Library discipline (single `library_id`, L5 read-only
  meta-view exception)
- ADR-0007 — bearer auth (`Principal`), error envelope (`request_id`),
  SSE infra
- ADR-0009 — task queue (terminal-state outbox writer)
- ADR-0010 — `TaskEvent` (the in-task counterpart; not a substitute)
- `apps/api/sse.py` — shared SSE plumbing
