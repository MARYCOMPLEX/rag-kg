# ADR-0009: Async Task Queue Selection (Arq)

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: BACKEND_ROADMAP §2.1; PRD §14.2 (M7 后台任务) and §14.3 D7.5
**Related**: ADR-0001 (modular monolith), ADR-0007 (SSE for QA), ADR-0010 (task progress events), ADR-0011 (notification center)

## Context

Through M0–M6 we built a synchronous, single-process API. Every long-running
research task — single-PDF ingest, batch ZIP ingest, KG extraction (NER/RE/EL),
Leiden community rebuild, Review, Reason, Hypothesize — runs **inline on the
FastAPI request thread**. That worked while the only consumer was the
operator's terminal, but M7 (PRD §14, "Hardening / UX") changes the rules:

1. **PRD §14.2 D7.5** mandates that Review / Reason / Hypothesize can be
   "Run in background", the user can close the page, and resume from the task
   page or top-bar Notify center later.
2. **PRD §14.3** lists D7.5 "后台任务 + 通知" as an explicit deliverable.
3. **BACKEND_ROADMAP §2.1** documents the symptom: `apps/worker/main.py` is a
   noop placeholder. Synchronous long tasks now block API workers, defeating
   FastAPI's async event loop and starving every other request.
4. The community-rebuild job alone can run 3–8 minutes on a 200-paper Library;
   a Review task can exceed 10 minutes. Holding a TCP connection that long is
   not viable behind a typical reverse proxy.
5. ADR-0007 already chose SSE for *QA* streaming. Long tasks need a different
   shape: structured stage events delivered over potentially-reconnecting
   streams, decoupled from the worker's lifetime. That requires (a) a real
   queue and (b) a pub/sub bus the worker writes to and the API reads from.
   ADR-0010 specifies the bus; this ADR picks the queue.

We are also constrained by the modular-monolith decision (ADR-0001):
- The worker process must share the codebase. No separate repo, no separate
  language, no separate dependency tree.
- The queue must be Python-native and play with `asyncio` so the existing
  `async def` adapters (LLM gateway, Qdrant client, Neo4j driver) compose
  without thread-pool gymnastics.
- Solo-dev operational budget: we already run Postgres + Qdrant + Neo4j +
  OpenSearch + Redis + MinIO. **Adding a new control-plane service is a
  non-starter.**

### Forces

- **Persistence**: a worker crash mid-Review must not silently lose the task.
- **Cancellability**: PRD §14.2 references "Run in background" with implicit
  user-driven cancel. Cancel needs to surface inside the running coroutine.
- **Idempotency**: ADR-0007 made ingest idempotent via SHA-256. The queue
  layer must allow safe retries — i.e., re-running a job is the operator's
  prerogative, not the framework's reflex.
- **`library_id` propagation**: every task is Library-scoped (PRD §16.6).
  The queue must pass `library_id` end-to-end without leaking through global
  state.
- **Observability**: every job must emit a Langfuse trace span tagged with
  `library_id` and `task_id` (M6 baseline).

## Decision

We adopt **[Arq](https://arq-docs.helpmanual.io/)** as the async task queue,
backed by the **Redis we already run** for rate-limiting and embedding cache.

The integration is hidden behind a `TaskQueue` Protocol so a future swap
(e.g. to Temporal in v2) does not ripple through call sites.

### 1. `TaskQueue` Protocol contract

The Protocol lives in `packages/orchestration/task_queue.py` (per
BACKEND_ROADMAP §2.1):

```python
# packages/orchestration/task_queue.py
from typing import Protocol

from packages.core.models import (
    TaskHandle,
    TaskSpec,
    TaskState,
)


class TaskQueue(Protocol):
    """Library-scoped async task queue.

    Per PRD §16.6, every method takes `library_id` as the first positional
    parameter. No method accepts `library_ids: list` — cross-Library
    aggregation is L5 orchestration concern (see Activity Log, ADR-0014),
    not a queue concern.
    """

    async def enqueue(
        self,
        library_id: str,
        task: TaskSpec,
        *,
        priority: int = 0,
    ) -> TaskHandle:
        """Persist the spec and emit a `task_queued` event."""

    async def get(
        self,
        library_id: str,
        task_id: str,
    ) -> TaskState | None:
        """Return current state or None if unknown / outside library scope."""

    async def cancel(
        self,
        library_id: str,
        task_id: str,
    ) -> bool:
        """Cooperative cancel. Returns False if task already in terminal state."""

    async def list_active(
        self,
        library_id: str,
    ) -> list[TaskHandle]:
        """Active = status in {queued, running}. Used by /v1/libraries/{lib}/tasks."""
```

The Arq-backed implementation lives at
`packages/orchestration/adapters/arq_task_queue.py`. `apps/api` only ever sees
the Protocol; the adapter is wired in via the `apps/_shared/factories`
container.

### 2. Job registry and `WorkerSettings`

Job files live under `apps/worker/jobs/` (one file per task type):

```
apps/worker/jobs/
  ingest_document.py        # single PDF
  ingest_batch.py           # ZIP / folder
  extract_kg.py             # NER + RE + EL → Neo4j
  rebuild_community.py      # Leiden + summarize
  run_review.py
  run_reason.py
  run_hypothesize.py
  library_status_check.py   # cron, see ADR-0013
  eval_snapshot.py          # daily KPI snapshot
```

Each module exports a single coroutine `async def run(ctx, library_id, …)`
that is registered in `apps/worker/main.py`:

```python
# apps/worker/main.py
from arq.connections import RedisSettings

from apps.worker.jobs import (
    eval_snapshot,
    extract_kg,
    ingest_batch,
    ingest_document,
    library_status_check,
    rebuild_community,
    run_hypothesize,
    run_reason,
    run_review,
)
from apps._shared.factories import build_worker_context


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_dsn)
    functions = [
        ingest_document.run,
        ingest_batch.run,
        extract_kg.run,
        rebuild_community.run,
        run_review.run,
        run_reason.run,
        run_hypothesize.run,
        library_status_check.run,
        eval_snapshot.run,
    ]
    cron_jobs = [
        library_status_check.cron(),  # every 5 min
        eval_snapshot.cron(),         # daily at 02:00 UTC
    ]
    on_startup = build_worker_context
    on_shutdown = teardown_worker_context
    max_jobs = 4
    keep_result = 3600   # seconds; final TaskState lives in Postgres anyway
    job_timeout = 1800   # 30 min hard ceiling (Review / community)
```

### 3. Job design principles

Every `apps/worker/jobs/*.py` MUST:

1. **Be idempotent.** A re-run with the same input yields the same effect
   (mirrors ADR-0007 ingest idempotency). Concretely: the first action of a
   job is to load `TaskState` and short-circuit on terminal status.
2. **Be resumable.** Stage boundaries are checkpoints. If the worker dies
   mid-stage, a re-enqueue with `resume_from=<stage>` continues from the
   last completed checkpoint. State carries `current_stage` (per
   BACKEND_ROADMAP §2.1 `TaskState` model).
3. **Propagate `library_id` end-to-end.** Every adapter call inside the job
   takes `library_id`. No `contextvars` magic — explicit args, audited at
   review time.
4. **Write state to Postgres, not Redis.** Arq's Redis result store is a
   convenience for short-lived completions; the durable record lives in the
   `tasks` table (see schema below). Redis can be wiped on upgrade with
   zero data loss.
5. **Emit `TaskEvent`s on every transition** (per ADR-0010). The event bus
   bridges worker → API SSE.
6. **Run inside a single Langfuse trace** with `task_id` as trace id and
   each stage as a span (M6 observability baseline).

### 4. Persistence schema

The durable task table (Postgres):

```sql
CREATE TABLE tasks (
    task_id          TEXT PRIMARY KEY,
    library_id       TEXT NOT NULL,
    task_type        TEXT NOT NULL,
    status           TEXT NOT NULL,               -- queued|running|completed|failed|cancelled
    progress         REAL NOT NULL DEFAULT 0.0,
    current_stage    TEXT,
    input_payload    JSONB NOT NULL,
    result_pointer   TEXT,                        -- MinIO key or Postgres row ref
    error            TEXT,
    enqueued_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,
    created_by       TEXT,                        -- principal id from ADR-0007 auth
    cost_usd         NUMERIC(10, 6) DEFAULT 0
);
CREATE INDEX tasks_library_status_idx ON tasks (library_id, status, enqueued_at DESC);
CREATE INDEX tasks_active_idx ON tasks (library_id) WHERE status IN ('queued', 'running');
```

This table is the **single source of truth**. The Arq Redis state is
ephemeral; the Postgres row outlives Redis flushes.

### 5. Cancel and retry semantics

- **Cancel**: `cancel()` writes `status=cancelled` to Postgres, and publishes
  a `task_cancelled` event on the bus. The running coroutine polls a
  `should_cancel(task_id)` helper at every stage boundary and at every chunk
  inside long stages. Cooperative — no thread-kill.
- **Retry**: not automatic. Failures terminate the job; the user re-queues
  from the UI (Tasks page → "Retry"). Arq's built-in `max_tries` is set to
  `1` — we explicitly do not want silent retries on a Review that consumed
  $0.40 in tokens. PRD §17 R01 (cost) outweighs the convenience.

### 6. Relation to ADR-0010 (events) and ADR-0011 (notifications)

- **ADR-0010**: every job uses an injected `TaskEventBus` (Redis pub/sub) to
  emit `TaskEvent`s. The API server SSE handler subscribes to
  `task:{task_id}:events`.
- **ADR-0011**: on terminal status (`completed | failed | cancelled`), the
  job's last action is to insert a `Notification` row. The Notification
  carries `library_id` (or `NULL` for system-level alerts like worker
  offline). Outbox-style: same Postgres transaction as the final
  `tasks.status` update.

These three ADRs are deliberately separate so that the **queue
implementation** (Arq) can be swapped without touching the **event protocol**
(stable wire format) or the **notification storage** (durable table).

## Consequences

### Positive

- API request handlers return `TaskHandle` in milliseconds; long work is
  invisible to the request lifecycle.
- Worker can be restarted (e.g. for code deploy) without losing queued jobs:
  Arq persists the queue in Redis with at-least-once delivery semantics.
- Same code, same tests, same lint rules as the rest of the monolith — a job
  is just an `async def`.
- Cron jobs (library status check, daily eval snapshot) reuse the same
  worker process; no separate scheduler.
- Postgres `tasks` table is queryable by operators ("show me yesterday's
  failed Reviews") with plain SQL.

### Negative

- New operational dependency on Redis durability. Mitigation: enable AOF
  persistence (`appendonly yes`); the durable `tasks` row already covers
  worst-case Redis loss.
- Arq is a small project (≈3k GitHub stars). If it goes unmaintained we
  must port the Protocol implementation. The Protocol abstraction is the
  insurance.
- Worker process means two Python interpreters in production — slightly
  more memory, two Langfuse SDK initializations, two Sentry connections.

### Risks

| ID | Risk | Mitigation |
|----|------|-----------|
| Q-R1 | Worker stalls hold jobs forever (Redis BLPOP wedge) | `job_timeout=1800`; `library_status_check` cron monitors heartbeat and emits `alert_triggered` Notification (ADR-0011) when heartbeat lags > 60 s |
| Q-R2 | Cancel races with stage completion → state thrash | Cancel is checked at *stage boundary*; mid-stage work is allowed to finish so partial cost is not wasted before the cancel resolves |
| Q-R3 | Re-enqueueing a "completed" task by mistake re-runs expensive work | `enqueue()` rejects when `tasks.status='completed'` unless explicit `force=True` (parallels ADR-0007 ingest `--force`) |
| Q-R4 | Arq's at-least-once delivery on worker crash → duplicate side effects (e.g. duplicate Notify, duplicate Neo4j writes) | Job idempotency principle (Decision §3.1) is the primary defense; KG writes use MERGE; Notify uses `(task_id, type)` unique key |

## Alternatives Considered

| Option | Pro | Con | Verdict |
|--------|-----|-----|---------|
| **Arq** (chosen) | Async-native; Redis already deployed; <500 LOC integration; Python-native types | Small community; minimalist (no admin UI) | Best fit for solo-dev modular monolith |
| **Temporal** | Best-in-class durability, retries, signals, complex workflows | Requires temporal-server cluster (Cassandra / Postgres + history-shards); SDK is heavy; learning curve significant; overkill for v1 9-job catalog | Rejected as **too heavy for v1**; revisit at M8+ if multi-host scaling demands it |
| **FastAPI `BackgroundTasks`** | Zero new dependency; trivial integration | In-process — dies with the API worker; no persistence; no cancel; no cross-process visibility | Rejected — fails PRD §14.2 D7.5 ("close the page and come back") |
| **Celery** | Mature; broad ecosystem; flower UI | Sync-first design forces awkward `asgiref.sync_to_async`; configuration sprawl; AMQP or Redis broker; pickle-based serialization invites footguns; community drift toward maintenance mode | Rejected — friction against the async stack is a daily tax |
| **RQ** (Redis Queue) | Simple, Redis-backed | Sync only; no async support; cron is a separate package | Rejected — same async impedance mismatch as Celery |
| **Dramatiq** | Async-friendly, RabbitMQ or Redis | Smaller than Celery, larger than Arq; no obvious advantage over Arq for our scale | Rejected — no decisive win over Arq |
| **Custom asyncio queue + Postgres** | Total control | Reinventing the wheel; cron, retries, timeouts, dashboards all DIY | Rejected — YAGNI inverted (we'd be building a worse Arq) |

### Why not Temporal in v1

Temporal solves the next decade of distributed-workflow problems. We don't
have those problems yet. Specifically:

1. We have **one worker process** in v1. Temporal's value is multi-host
   workflow durability and signal-driven sagas — neither applies.
2. Temporal's history-shard architecture imposes a 4× operational complexity
   step (Cassandra/PG cluster, frontend service, matching service, history
   service, worker SDK).
3. The Protocol abstraction makes Temporal a viable v2 swap when (and only
   when) the symptom is "we run multi-host workers and Arq's at-least-once
   semantics aren't enough". That is an M8+ conversation.

## Open Questions

1. **Priority lanes**: Do we need a dedicated "interactive" queue separate
   from "batch" so an ad-hoc Review doesn't queue behind a 30-min batch
   ingest? Decision deferred to first observed contention.
2. **Multi-worker scaling**: When does a second worker process pay off?
   Likely once daily Review volume passes ~50 / Library / day. Track via
   Grafana queue-depth panel from M6 baseline.
3. **Retention**: How long should `tasks` rows live? Initial proposal: 90
   days, then archive to MinIO (mirrors ADR-0014 Activity Log retention).
   Confirm with first user cohort.
4. **Result payload size**: Some Review results approach 200 KB markdown.
   Store inline in `result_pointer` (MinIO) rather than `tasks.result_pointer`
   row column? Yes — `result_pointer` is MinIO key; the row column stores
   the key, never the payload.

## References

- BACKEND_ROADMAP §2.1 — async queue scope, file layout, DoD
- PRD §14.2 D7.5 — background-task UX requirement
- PRD §16.6 — Library discipline (no `library_ids: list` in queue Protocol)
- PRD §17 R01 — LLM cost discipline (no auto-retry)
- ADR-0001 — modular monolith (worker shares codebase)
- ADR-0007 — ingest idempotency, error envelope (`request_id` propagates as
  `task_id` for queued work)
- ADR-0010 — `TaskEvent` protocol (consumed by jobs)
- ADR-0011 — Notification center (terminal-state outbox)
- Arq docs — https://arq-docs.helpmanual.io/
