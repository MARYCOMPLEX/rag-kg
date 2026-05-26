# ADR-0015: per-Library Daily Cost Cap 拦截策略

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: M7 horizontal hardening — Risk R01 mitigation; BACKEND_ROADMAP §2.7
**Related**: ADR-0011 (Notification Center), ADR-0012 (per-Library Config Override),
ADR-0016 (VAR Computation), ADR-0008 (Context Management — token budget)

## Context

PRD §17 (Risk Register) flags **R01 — LLM 成本失控** as the project's
highest-probability / highest-impact risk; PRD §3.2 caps "每题平均 token 花费 ≤
$0.10". `BACKEND_ROADMAP §2.7` mandates a per-Library / per-day cost ceiling
(`daily_cost_cap_usd`) with both **soft warning** and **hard block** behaviour.

Today the system has Langfuse traces for every LLM call but **no aggregation
table, no enforcement point, and no notification surface**. A user who fires
50 `Review Generation` tasks against a small Library can burn through a full
month's API budget in an hour without any pre-emptive backstop. This is
unacceptable for a tool that is supposed to be safe to leave running on a
self-hosted machine.

The problem decomposes into five orthogonal questions:

1. **Where do we accumulate cost?** Langfuse alone is too slow (it is a
   tracing backend, not an OLTP counter), and a remote dependency for a
   safety-critical guard.
2. **At what threshold do we warn vs block?** A hard 100 % block with no
   prior warning surprises the user mid-task.
3. **At what granularity does the block bite?** Mid-stream — kill an
   already-running Review at LLM-call N — or task-level — refuse to *start*
   the next Review?
4. **Which costs count?** LLM-only, +Embedder, +storage egress?
5. **When does the daily counter reset?** UTC midnight is simple but
   unhelpful for users in UTC+8.

Per PRD §16.6 (Library 维度纪律) all of this must be partitioned by
`library_id`; the global `Settings.daily_cost_cap_usd` is only a fallback
when `LibraryConfig.daily_cost_cap_usd` is `None`.

## Decision

### 1. Storage: Postgres `library_daily_cost`, atomic upsert

A new table accumulates spend per `(library_id, date)`:

```sql
CREATE TABLE library_daily_cost (
    library_id   TEXT        NOT NULL REFERENCES libraries(library_id) ON DELETE CASCADE,
    date         DATE        NOT NULL,                          -- in user_timezone, see §6
    llm_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
    request_count INTEGER    NOT NULL DEFAULT 0,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (library_id, date)
);

CREATE INDEX library_daily_cost_date_idx
    ON library_daily_cost (date DESC);
```

`packages/llm/gateway.py` accumulates after every successful LLM response:

```python
INSERT INTO library_daily_cost (library_id, date, llm_cost_usd, request_count, last_updated)
VALUES ($1, $2, $3, 1, now())
ON CONFLICT (library_id, date) DO UPDATE
SET llm_cost_usd  = library_daily_cost.llm_cost_usd + EXCLUDED.llm_cost_usd,
    request_count = library_daily_cost.request_count + 1,
    last_updated  = now();
```

Postgres is chosen over Redis (see §Trade-offs) because daily aggregation is
naturally relational, the data must survive restarts, and we already pay the
Postgres dependency cost.

### 2. Two-tier threshold: 80 % warn / 100 % block

| Tier  | Threshold                       | Behaviour                                                  |
|-------|---------------------------------|------------------------------------------------------------|
| OK    | `today_cost / cap < 0.8`        | No-op; record and continue                                 |
| WARN  | `0.8 ≤ today_cost / cap < 1.0`  | First crossing → emit `daily_cost_warning` notification    |
| BLOCK | `today_cost / cap ≥ 1.0`        | Reject *new* task starts; emit `daily_cost_blocked` notif  |

The 80 % default is configurable per Library:

```python
class LibraryConfig(BaseModel):           # extends ADR-0012
    daily_cost_cap_usd:        Decimal | None = None      # None → inherit Settings
    daily_cost_warn_ratio:     float          = 0.8       # tunable
    daily_cost_reset_timezone: str            = "UTC"     # IANA tz
```

Crossing detection is **edge-triggered** — we only emit the warning the
*first* time `today_cost` crosses 0.8; subsequent calls within `[0.8, 1.0)`
do not spam. The transition is recorded by writing the `daily_cost_warning`
notification with `idempotency_key = f"warn:{library_id}:{date}"`.

### 3. Block granularity: **task-level**, not call-level

When `today_cost ≥ cap`, the orchestrator **refuses to start** new
`review`, `reason`, `hypothesize`, `qa`, or `ingest` tasks. **In-flight tasks
are allowed to finish** — they were already underwritten when admission
happened.

Rationale:
- A Review task that has already spent $5 on retrieval + planning and is
  one summarising LLM call away from completion will produce **less value
  per dollar refunded** if killed.
- Mid-stream killing breaks SSE consumers (ADR-0007) — the user sees a
  cryptic `error` event after watching tokens stream.
- Task-level admission is naturally idempotent and unit-testable.

The check happens at *two* gates:

```
┌────────────────────┐  Gate 1 (admission)
│ POST /tasks/start  │ ──→ TaskRunner.start_if_allowed
└────────────────────┘     ├── over cap?  → 402 Payment Required + ErrorCode.DAILY_COST_BLOCKED
                           └── allowed    → enqueue Arq job

┌────────────────────┐  Gate 2 (per-LLM-call accounting, not enforcement)
│ LLMGateway.complete│ ──→ accumulate(library_id, cost)
└────────────────────┘     └── publish notification on threshold crossing
```

Gate 1 is the enforcement point. Gate 2 only updates the counter and emits
notifications; it does **not** raise on already-running tasks.

`QA stream` is a special case: it is conceptually one task, so Gate 1 fires
once at request start. The streaming itself is uninterruptible.

### 4. Protocol surface

```python
# packages/orchestration/budget.py

class DailyCostStore(Protocol):
    async def get_today_cost(self, library_id: str, *, on_date: date) -> Decimal: ...
    async def record(
        self, library_id: str, *, on_date: date, delta_usd: Decimal
    ) -> RecordResult: ...

class RecordResult(BaseModel):
    library_id: str
    date: date
    new_total_usd: Decimal
    crossed: Literal["none", "warn", "block"]    # which threshold this call crossed

class CostGuard(Protocol):
    """Admission control for new tasks."""

    async def check_admission(
        self, library_id: str, estimated_cost_usd: Decimal | None = None
    ) -> AdmissionDecision: ...

class AdmissionDecision(BaseModel):
    allowed:        bool
    today_cost:     Decimal
    cap:            Decimal | None       # None = unlimited
    ratio:          float                # today / cap, 0 if cap is None
    reason:         Literal["ok", "warn", "blocked"]
    error_code:     ErrorCode | None     # populated when allowed=False
```

The Gateway calls `record`; routes call `check_admission` as the *first*
step, before allocating a task ID.

### 5. Notification integration (ADR-0011)

Two notification types extend ADR-0011's enum:

```python
class NotificationType(StrEnum):
    DAILY_COST_WARNING = "daily_cost_warning"   # severity=warning
    DAILY_COST_BLOCKED = "daily_cost_blocked"   # severity=danger
```

Payload schema:

```python
{
    "library_id": "graphrag-rag",
    "date":       "2026-05-05",
    "today_cost_usd":  4.12,
    "cap_usd":         5.00,
    "ratio":           0.824,
    "currency":        "USD",
    "reset_at":        "2026-05-06T00:00:00+08:00"
}
```

Edge-triggered idempotency key (from §2) prevents notification spam for the
same `(library, date, tier)`.

### 6. Reset timezone: per-Library, default UTC

Daily counters reset at the *start of the next day in `daily_cost_reset_timezone`*.
The `date` column is computed at write time:

```python
on_date = datetime.now(ZoneInfo(library_config.daily_cost_reset_timezone)).date()
```

UTC is the safe default. Users in fixed-offset locales (CN/JP/EU) can
override per-Library. Daylight-saving handling is delegated to `zoneinfo`;
no custom rules.

### 7. Cost scope (v1): **LLM tokens only**

For v1 we count *only* `llm_cost_usd` (input + output token cost via
SiliconFlow / OpenAI / local pricing tables). Embedding cost is excluded
because:

- Embedder calls are amortised across many queries (cache hit rates >70 %
  per `MEMORY.md` Library `rag-agent` notes).
- A typical Embedder call is < $0.001 — counting it muddies the signal.
- Pricing for local Embedders (Qwen3-Embedding) is zero, so partial-counting
  produces misleading dashboards.

Storage egress (MinIO bandwidth) is also excluded — it has no per-Library
attribution today and is a fixed-cost item for self-hosted deployments.

This decision is revisited in v1.1 when Embedder pricing varies per Library
(per ADR-0012 override). The model leaves a `__future__` field
`embedder_cost_usd NUMERIC` reserved.

### 8. Read API

```
GET /v1/libraries/{lib}/cost?days=30
→ {
    "library_id": "graphrag-rag",
    "cap_usd":    5.00,
    "today":      { "date": "2026-05-05", "cost_usd": 4.12, "ratio": 0.824 },
    "history":    [
      { "date": "2026-05-04", "cost_usd": 3.21, "request_count": 217 },
      { "date": "2026-05-03", "cost_usd": 1.05, "request_count":  62 },
      ...
    ]
  }
```

Used by the Settings UI panel and the Eval Dashboard cost trend
(BACKEND_ROADMAP §3.8 Gap 1).

### 9. Error envelope (ADR-0007 alignment)

```python
class ErrorCode(StrEnum):
    ...
    DAILY_COST_BLOCKED = "daily_cost_blocked"
```

HTTP status: **402 Payment Required** (closest semantic match; `403` was
considered but conflates with auth).

```json
{
  "code":    "daily_cost_blocked",
  "message": "Library 'graphrag-rag' has reached its daily cost cap of $5.00.",
  "request_id": "...",
  "details": {
    "today_cost_usd": 5.07,
    "cap_usd": 5.00,
    "reset_at": "2026-05-06T00:00:00+00:00"
  }
}
```

The frontend special-cases this code into a non-toast modal explaining the
cap, with a link to Settings.

## Consequences

### Positive

- **R01 mitigated**: a misbehaving prompt or runaway loop cannot consume
  more than `cap_usd` per Library per day — bounded blast radius.
- **No remote dependency** in the safety path: Postgres is already mandatory
  per ADR-0001; Langfuse outage does not disable the cap.
- **Per-Library granularity**: a noisy Library cannot starve a quiet one;
  alignment with PRD §16.6 (Library 维度纪律).
- **Edge-triggered notifications** keep the Notify tray usable.

### Negative

- **Coarse granularity in v1**: a single 12 ¢ LLM call can push the counter
  from 79 % to 81 %, "wasting" 19 ¢ of budget before the warning fires. We
  consider this acceptable for v1; v1.1 may add pre-call estimation.
- **Task-level enforcement** allows in-flight tasks to overshoot the cap —
  users may see total spend slightly above `cap_usd`. We document this
  explicitly in the Operator Runbook.
- **Embedder cost not counted** can mask real burn for Libraries using
  paid hosted Embedders. Mitigated by the `embedder_cost_usd` reserved
  column for v1.1.

### Risks

- **Langfuse-vs-local divergence**: the Postgres counter and Langfuse may
  disagree on cost (different rounding / different pricing tables). We
  treat Postgres as the source of truth for *enforcement*; Langfuse remains
  the source for *attribution / drill-down*. Discrepancy is logged but
  non-fatal.
- **Counter drift on Postgres failure**: if the `INSERT ... ON CONFLICT`
  fails (e.g. connection drop after LLM call succeeded), cost is *under-counted*.
  Mitigation: the Gateway logs a warning and retries up to 3 times; failure
  beyond that is recorded in `cost_record_failures` and surfaced in Grafana.
  We **do not** roll back the LLM response — it would be worse to fail a
  successful answer than to under-count by a few cents.
- **Cap set too low**: a freshly-created Library with the global default
  $1/day will block on the second Review. Mitigation: Settings UI shows
  current cap prominently; LibraryCreateModal lets the user set it during
  onboarding.

## Alternatives Considered

| Option | Rejected Because |
|---|---|
| **Redis INCR counter** | No durability — restart loses today's accumulation. Could be solved with RDB persistence but adds operational complexity. Postgres already required, no new infra. |
| **Pure Langfuse query at admission** | Adds latency (~200 ms remote call) on every task start; Langfuse outage breaks task admission entirely. Tracing backends are not enforcement backends. |
| **No cap, only warning** | PRD R01 demands enforcement; a warning-only system is "documentation that it broke" not "a brake". |
| **Hard kill mid-stream** | Breaks SSE contract (ADR-0007); poor UX; complex transactional rollback across LLM provider, evidence DB, conversation log. Marginal value over admission-only. |
| **Pre-call cost estimate then reserve** | Requires accurate input-token counting *before* prompt assembly, which is composition-dependent and would tightly couple Gateway to Composer. v1.1 candidate. |
| **Global daily cap only** | Violates PRD §16.6 — different Libraries have different value-per-dollar; a dev sandbox should cap low while a production Library may need $20/day. |

## Open Questions

- **Q1**: Should `cost cap` apply to ingestion (KG extraction LLM calls) or
  only retrieval/answer flows? **Tentative**: yes, ingestion counts — KG
  extraction is the largest single cost in M2 (per BACKEND_ROADMAP §3.4).
  But we may want a separate `ingest_cost_cap_usd` so a giant ZIP upload
  does not exhaust the user's question budget.
- **Q2**: Should we expose the cap reset countdown as an SSE channel so the
  UI can live-update "you have $0.88 left today"? Likely yes in M7.4.
- **Q3**: For organisations, should cap be per-user-per-Library? Out of
  scope for v1 (single-tenant), but the schema's primary key
  `(library_id, date)` would extend cleanly to `(library_id, user_id, date)`.

## Relationship to Other ADRs

- **ADR-0007 (Error Envelope)**: defines `DAILY_COST_BLOCKED` error code and
  402 status mapping; reuses `request_id` correlation.
- **ADR-0011 (Notification Center)**: this ADR is the largest source of
  user-facing notifications; both ADRs share the edge-triggered idempotency
  pattern.
- **ADR-0012 (per-Library Config Override)**: `daily_cost_cap_usd`,
  `daily_cost_warn_ratio`, and `daily_cost_reset_timezone` live in
  `LibraryConfig`; `None` means "inherit from `Settings`".
- **ADR-0016 (VAR Computation)**: VAR's denominator includes refused tasks
  (they are still "asked questions"); refused requests count as `useful=False`
  in the VAR feedback aggregator. See ADR-0016 for the joint policy.
- **ADR-0008 (Context Management)**: token budgets for context assembly are
  *separate* from cost caps — context budget is per-call (input-side), cost
  cap is per-Library-per-day (sum of all calls). Both can fail
  independently.
- **ADR-0003 (Library as Data Partition)**: `library_daily_cost` is partitioned
  by `library_id` like every other Library-scoped table; ADR-0022 (Purge)
  must clean it during `purge_library`.

## References

- PRD §3.2 (Guardrails — `每题平均 token 花费 ≤ $0.10`)
- PRD §17 R01 (LLM 成本失控)
- PRD §14.2 (M7 — `per-Library 每日成本上限`)
- PRD §16.6 (Library 维度纪律)
- BACKEND_ROADMAP §2.7 (per-Library Daily Cost 统计与上限)
- BACKEND_ROADMAP §6 P1 (item 9, ADR-0015 + Daily Cost Cap)
- BACKEND_ROADMAP §7 BR07 (Self-RAG cost amplification — this ADR is the
  primary mitigation)
