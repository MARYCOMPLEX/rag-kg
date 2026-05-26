# ADR-0010: SSE Task Progress Event Protocol (extends ADR-0007)

**Status**: Accepted
**Date**: 2026-05-05
**Drives**: BACKEND_ROADMAP §2.2; PRD §14.2 (Pipeline Tree, live citations, cost dashboard)
**Extends**: ADR-0007 (QA SSE — kept unchanged)
**Related**: ADR-0009 (Arq queue), ADR-0011 (notification center)

## Context

ADR-0007 shipped a four-event SSE wire format for the **single-shot QA**
endpoint:

```
meta → token* → citations → done   (or error → close)
```

That contract is **stable and not changing here**. It works for QA because
QA has one stage, finishes in seconds, and the user is staring at the page.

Long-running research tasks have entirely different shape. Per PRD §14.2
("Tasks page" deliverables) and BACKEND_ROADMAP §2.2:

- Review can run 5–10 minutes across 5–8 sub-topic pipelines.
- Reason and Hypothesize chain multiple agentic retrieval rounds.
- Community rebuild and KG extraction are batch jobs the user may have left
  the page for.

The UI promises (per PRD §14.2 / `docs/UI_UX.md` S5–S7):

1. **Pipeline Tree**: a left-rail tree showing "正在召回第 3 子主题"
   with stage start, progress (3/5), and stage completion timestamps.
2. **Live citations panel**: citations stream into the right rail as the
   task discovers them — not after the fact.
3. **Cost / token dashboard**: realtime "$0.024 spent so far".
4. **Resume after page close**: user closes the laptop, comes back; the SSE
   reconnects and replays missed events from the last `seq` they saw.

The QA 4-event format cannot carry any of this without becoming a polymorphic
mess. We need a new, **uniform `TaskEvent`** that all long tasks emit and
the frontend renders generically.

This ADR specifies that protocol. ADR-0009 specifies who emits it (worker
jobs); ADR-0011 specifies the durable terminal-state notification.

### Why not WebSocket

The same reasoning as ADR-0007 §3 applies and is reaffirmed:

- Communication is **server → client** for progress; cancel is a separate
  HTTP POST (`POST /v1/libraries/{lib}/tasks/{task_id}/cancel`).
- SSE auto-reconnects in the browser; `Last-Event-ID` is built-in.
- SSE is proxy-friendly (vanilla HTTP/1.1 chunked or HTTP/2); WebSocket
  needs upgrade negotiation that some corporate proxies break.
- We already have an SSE infra stack from M7 (`apps/api/sse.py`).

## Decision

We define a single `TaskEvent` model, emitted by every long-running worker
job (ADR-0009), bridged from Redis pub/sub to SSE by a new endpoint, and
consumed by every progress-aware UI surface.

### 1. `TaskEvent` schema

```python
# packages/orchestration/events.py
from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, Field


TaskEventType = Literal[
    # lifecycle
    "task_queued",
    "task_started",
    "task_completed",
    "task_failed",
    "task_cancelled",
    # stages (Pipeline Tree drives off these)
    "stage_started",
    "stage_progress",
    "stage_completed",
    # streaming content
    "token",
    "citation_added",
    # accounting
    "cost_updated",
]


class TaskEvent(BaseModel):
    """Wire-stable event emitted by every long-running task.

    Versioned by `schema_version`. New event types may be added; existing
    types and fields MUST NOT be renamed or removed within a major version.
    See §6 (Versioning) of this ADR.
    """

    schema_version: int = 1
    library_id: str
    task_id: str

    # Monotonically increasing per (task_id). Producers use a Redis INCR
    # against `taskseq:{task_id}` so concurrent stage producers can't collide.
    # The frontend uses `seq` to detect gaps and trigger a replay request.
    seq: int = Field(ge=0)

    timestamp: datetime
    type: TaskEventType
    stage_name: str | None = None
    payload: dict = Field(default_factory=dict)


class TaskEventBus(Protocol):
    """Per PRD §16.6, every method takes `library_id` first.

    No method exposes a multi-library subscribe; cross-Library aggregation
    is L5 orchestration concern (Activity Log, ADR-0014), not the bus.
    """

    async def publish(self, library_id: str, event: TaskEvent) -> None: ...
    async def subscribe(
        self,
        library_id: str,
        task_id: str,
        *,
        since_seq: int | None = None,
    ) -> "AsyncIterator[TaskEvent]": ...
    async def replay(
        self,
        library_id: str,
        task_id: str,
        since_seq: int,
    ) -> list[TaskEvent]: ...
```

### 2. Canonical payload shapes

Each event type has a documented payload contract. Producers MUST conform;
the frontend MAY rely on these fields being present for the listed types.

| Event type            | Payload (canonical)                                           |
|-----------------------|---------------------------------------------------------------|
| `task_queued`         | `{"task_type": str, "input_summary": str}`                    |
| `task_started`        | `{"started_at": iso8601, "estimated_duration_s": int}`        |
| `stage_started`       | `{"stage": str, "estimated_duration_s": int}`                 |
| `stage_progress`      | `{"stage": str, "current": int, "total": int, "note": str?}`  |
| `stage_completed`     | `{"stage": str, "duration_s": float, "result_summary": str?}` |
| `token`               | `{"text": str, "delta_ms": int}`                              |
| `citation_added`      | `{"chunk_id": str, "rank": int, "source": str}`               |
| `cost_updated`        | `{"tokens_in": int, "tokens_out": int, "cost_usd": float}`    |
| `task_completed`      | `{"result_pointer": str, "duration_s": float}`                |
| `task_failed`         | `{"error_code": str, "message": str, "request_id": str}`      |
| `task_cancelled`      | `{"reason": str, "by": str}`                                  |

`stage_name` is required on every `stage_*` event and forbidden elsewhere.

### 3. Wire format on SSE

The endpoint `GET /v1/libraries/{library_id}/tasks/{task_id}/events`
streams the same `TaskEvent` envelope. Each event is sent as:

```
id: <seq>
event: <type>
data: <JSON of TaskEvent>

```

- `event:` carries the discriminator (so EventSource handlers can subscribe
  per type without parsing JSON).
- `id:` is `seq`. The browser's EventSource sends it back as
  `Last-Event-ID:` on reconnect.
- `data:` is the full `TaskEvent` JSON (the discriminator is duplicated as
  `type` for clients that prefer one parse path).

Heartbeat: every 15 s the server emits a `: keep-alive` comment line so
proxies don't time the connection out. Heartbeats are not events; they
have no `seq`.

On disconnect detection (`await request.is_disconnected()`), the handler
unsubscribes from Redis and exits cleanly.

### 4. Architecture: Redis pub/sub bridge

```
                        ┌─────────────────────────────┐
   apps/worker/jobs/*.run │  ─── publish(event) ──▶   │
                        │                             │
                        │   Redis (pub/sub + stream)  │
                        │     channel: task:{id}      │
                        │     stream: taskhist:{id}   │
                        │                             │
   apps/api/routes/sse  │  ─── subscribe + replay ──▶ │
                        └─────────────────────────────┘
                                                 │
                                                 ▼
                                       SSE → browser (EventSource)
```

Two Redis structures, **deliberately**:

- **Pub/sub channel `task:{task_id}`**: live broadcast. Subscribers
  attached at publish time receive the event. Pub/sub does *not* persist —
  late subscribers miss earlier events.
- **Stream `taskhist:{task_id}`**: append-only history. Used for
  `replay(since_seq=N)` on reconnect, and for end-of-task forensic
  inspection. TTL: 24 hours after `task_completed | task_failed |
  task_cancelled` (terminal events refresh the TTL one last time).

The bus implementation publishes to **both** atomically (Lua script) so
`replay()` and the live channel never disagree on history.

### 5. Reconnect protocol (`Last-Event-ID`)

EventSource semantics:

1. Client connects, no `Last-Event-ID`. Server sends `replay(since_seq=0)`
   first (catch up to current state), then attaches the live subscriber.
2. Connection drops. Browser auto-reconnects with the last received `seq`
   in `Last-Event-ID`.
3. Server reads `Last-Event-ID: <N>`, calls `replay(since_seq=N+1)` to
   fill the gap, then attaches the live subscriber.
4. If `replay()` returns history older than the in-memory live position,
   the join is seamless (the server emits each replayed event before the
   next live one).
5. If the stream has been TTL'd (task ended >24 h ago), the server returns
   `409 Conflict` with `ErrorEnvelope.code=TASK_HISTORY_EXPIRED` (per
   ADR-0007 envelope) and the client falls back to `GET /v1/libraries/
   {lib}/tasks/{task_id}` for terminal-state snapshot.

The frontend `useSSE` composable extends to track the highest seen `seq`
in a Pinia store keyed by `task_id`, surviving page reload via
`sessionStorage`.

### 6. Versioning policy

`schema_version` starts at **1**. Within v1:

- **Allowed**: adding new `TaskEventType` values; adding new optional
  fields to `payload` for existing types; adding new top-level optional
  fields to `TaskEvent` (with a default).
- **Forbidden**: renaming or removing existing types; renaming or removing
  fields; changing field types; changing `seq` semantics; changing
  `stage_name` rules.

Breaking changes require `schema_version: 2` and a parallel endpoint
`/v1/.../events?schema=2` for one full release before sunset of v1.

The frontend pins to a known set of event types and ignores unknown ones
(forward-compat). Producers may emit new types confident that older
clients degrade gracefully — they just don't render the new UI affordance.

### 7. Compatibility with ADR-0007 (QA SSE)

**No change to the QA SSE wire format.** The decision matrix:

| Endpoint                                                        | Wire format                  | Why |
|-----------------------------------------------------------------|------------------------------|-----|
| `GET /v1/libraries/{lib}/qa/stream`                             | ADR-0007 (`meta`/`token`/`citations`/`done`) | Stable; frontend `streamQuestion` already shipped |
| `GET /v1/libraries/{lib}/tasks/{task_id}/events`                | ADR-0010 (`TaskEvent`)       | New; long tasks need stage events |

Future migration of QA into the unified `TaskEvent` shape is **not on the
v1 roadmap**. If we ever do it, the ADR-0007 endpoint stays alongside the
new one for one release as a deprecation window. PRD §14.2 mandates
backward-compatible SSE for QA — do not break it.

## Consequences

### Positive

- Frontend can render Pipeline Tree, live citations, and cost panels from
  a single event stream — no per-task-type wire formats.
- Reconnect is built-in: a flaky home-WiFi user can close the page,
  reconnect, and miss zero events thanks to the `taskhist:*` stream.
- Adding a new task type (e.g. M8 deep-research) requires zero protocol
  change — emit existing event types with new `task_type` and `stage_name`
  values.
- Operators can `redis-cli XRANGE taskhist:abc - +` to forensically
  inspect any task's full event log within the 24 h window.

### Negative

- Two Redis structures (channel + stream) per active task; modest memory
  overhead. Stream entries are bounded by event volume per task (~100s)
  and the 24 h TTL.
- Producers must remember to use the Redis INCR for `seq`. Mitigated by a
  helper `TaskEventBus.next_seq(task_id)` that hides the detail.
- Atomic dual-publish via Lua script is one more piece of operational
  surface. The script is ~12 lines; tested in `tests/orchestration/test_event_bus.py`.

### Risks

| ID | Risk | Mitigation |
|----|------|-----------|
| E-R1 | Producer out-of-order `seq` (e.g. async tasks racing on `next_seq`) → frontend gap-detection fires false positives | `next_seq` is a single Redis INCR; jobs MUST always go through the helper. Lint rule forbids constructing `TaskEvent(seq=...)` outside the bus module |
| E-R2 | Slow consumer holding pub/sub channel buffer → Redis memory pressure | Subscriber buffer cap (`maxlen=500`); on overflow the connection is dropped and the client falls back to `replay()` |
| E-R3 | Stream TTL expires mid-long-task (theoretical: a >24 h task) | TTL is set on terminal events only; running tasks have no TTL on the stream. Reset the TTL on every cron-style heartbeat job |
| E-R4 | Schema drift — a worker emits a payload field the frontend doesn't recognize | Forward-compat by design (clients ignore unknown payload keys); CI snapshot test on `TaskEvent` JSON schema catches accidental field rename |

## Alternatives Considered

| Option | Pro | Con | Verdict |
|--------|-----|-----|---------|
| **Single `TaskEvent` over SSE** (chosen) | Uniform; reuses ADR-0007 infra; reconnect built-in | Two Redis primitives; producers must funnel through helper | Best fit |
| Polymorphic per-task SSE format | No schema constraint per task type | Frontend must parse N shapes; every new task ships a new endpoint | Rejected — combinatorial complexity |
| WebSocket | Bidi, frame-level; some libraries provide reliability | Proxy / TLS / corp-network friction; overkill for 1-direction; cancel is HTTP anyway | Rejected (same reasoning as ADR-0007) |
| Long-poll with cursor | Works through any proxy | Latency of ~RTT per event; manual reconnect; no built-in browser handler | Rejected — UX laggy for token streams |
| gRPC server-streaming | Schema-first; type-safe | Not browser-native; needs grpc-web shim; deployment complexity | Rejected — wrong tool for the use case |
| Postgres `LISTEN/NOTIFY` as bus | One fewer system | Payload size cap (8 KB); no replay; one-process subscription model | Rejected — replay is mandatory |
| Redis Streams only (no pub/sub) | One primitive | XREAD with BLOCK works but pub/sub fan-out is simpler for "many subscribers, one task" | Considered; rejected for fan-out simplicity. Stream is still the persistence layer |

## Open Questions

1. **Per-stage cancel?** Today cancel is task-level. If a Review stage 4
   gets stuck, the operator cancels the whole task. Stage-level cancel
   is a v1.1+ idea; deferred until a real user reports the pain.
2. **Compression on the wire?** Long token streams are repetitive. SSE
   over HTTP/2 picks up gzip if the proxy supports it; we do not enable
   `compression='deflate'` explicitly. Re-evaluate if the >100 KB / task
   audit trail becomes a bandwidth concern.
3. **Multi-task event multiplexing?** A user with 3 running tasks opens
   3 SSE connections today. We could multiplex onto one connection
   subscribed at `library_id` granularity. Defer until SSE connection
   count becomes a load concern (browsers cap ~6 / origin).
4. **Audit / export**: should the 24 h history TTL be configurable
   per-Library? Probably yes when ADR-0012 lands; tracked there.

## References

- BACKEND_ROADMAP §2.2 — `TaskEvent` model, file layout, DoD
- BACKEND_ROADMAP §2.1 — producer side (worker jobs)
- PRD §14.2 — Pipeline Tree, live citations, cost dashboard, "Run in
  background" UX
- PRD §16.6 — Library discipline (per-`library_id` subscription)
- ADR-0007 §3 — original QA SSE format (unchanged)
- ADR-0009 — task queue (event producer side)
- ADR-0011 — notification center (terminal-state durable handoff)
- `apps/api/sse.py` — existing SSE plumbing from M7
- `apps/web/src/composables/useSSE.ts` — frontend `EventSource` wrapper
