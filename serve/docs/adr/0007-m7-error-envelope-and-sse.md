# ADR-0007: M7 — Unified Error Envelope, Bearer Auth, SSE Streaming, and Ingest Idempotency

**Status**: Accepted
**Date**: 2026-04-29
**Drives**: M7 hardening exit criteria
**Supersedes**: none

## Context

M7 ("Hardening / UX") needed several cross-cutting infrastructure decisions
before the system could face real users:

1. The HTTP API returned `{detail: string}` for some errors and bare strings
   for others, making the frontend's error UI brittle.
2. PRD §14 promised "轻量认证" (optional, single-tenant). Full OIDC/Keycloak
   was rejected as overkill; we needed something working in <1 hour.
3. PRD §6.D5.4 mandated "long-task SSE progress so users can see 'retrieving
   sub-topic 3...'", but the existing QA endpoint was buffered.
4. Re-uploading the same paper to a Library re-ran the full parse / embed /
   upsert pipeline, costing real money on every retry.
5. PRD §14.2 mandated per-Library export/import for "research drill" reproducibility.

## Decisions

### 1. Unified `ErrorEnvelope`
Wire shape: `{code: ErrorCode, message: str, request_id: str, details?: object}`
where `ErrorCode` is a stable string enum (`packages/core/api_errors.py`).
Single FastAPI exception-handler module (`apps/api/middleware/error_handler.py`)
maps every uncaught exception — `HTTPException`, Pydantic `RequestValidationError`,
domain `LibraryNotFoundError`, generic `RKBError`, raw `Exception` — into the
same JSON shape. Routes throw domain errors; the handler maps to HTTP status.

**Rationale**: Frontend `ApiError` (already shipped in M7.1) catches one class.
Codes are wire-stable so we can add new errors without breaking the 5 conditional
branches in `client.ts`.

### 2. Bearer-token auth via `Settings.api_key`
- `api_key=""` (default) → `get_current_principal` returns `Principal(kind='anonymous')`
- `api_key=<value>` → request must carry `Authorization: Bearer <value>` (constant-time compare)
- Single dep, applied to every `/v1/**` route.

**Rationale**: Solo deployments need zero-config; locked-down deployments need
one env var. No JWT signing, no DB lookup, no session table.

**Trade-off**: This is **single-tenant**. Multi-tenant requires a real auth
provider; that's deferred to M8+.

### 3. SSE streaming via `EventSource`-friendly endpoint
`GET /v1/libraries/{id}/qa/stream?question=…` emits four event types:
`meta` (model, library_id) → `token` (incremental text) → `citations` (final list) → `done`
(duration / token counts). On error: `error` event then close. Disconnect detection via
`await request.is_disconnected()` between chunks.

The current implementation **chunks the finished `QATask` answer client-side**
(48 chars / 20 ms) because `OpenAICompatLLM.complete` is buffered. When the
LLM adapter grows true streaming, only the inner `_stream_or_chunk` helper changes —
the wire format and frontend code stay the same.

**Rationale**: WebSockets need full duplex we don't use; long-poll would lose
the cancel signal. SSE is single-direction, plays nicely with proxies, and the
browser's `EventSource` handles reconnect natively (we still cap at 5 retries
in `useSSE` to avoid hammering).

### 4. Ingest idempotency via SHA-256 + sqlite state store
`packages/ingestion/state.py` — `(library_id, file_sha256)` unique key, status
`pending|done|failed`. The runner (`apps/_shared/factories/ingest_runner.py`)
hashes the file before any work, looks up state, returns the prior `IngestResult`
directly when status=done. `--force` overrides; `--report-only` dry-runs.

**Rationale**: Operating on PDFs (large, content-addressable) makes hashing
cheap (~50 ms / MB), and the marginal cost of re-running a successful ingest
is dollars for embeddings + minutes of LLM time on KG extraction. Skipping is
the obviously-right default.

**Trade-off**: We chose sqlite over Postgres because the data is
operator-local (not shared between API + worker). When worker is added, this
will need to migrate to Postgres or shared file path.

### 5. Per-Library backup as opaque tar.gz
`rkb library export <id>` packages library_meta + corpus + qdrant scroll +
graph.json + community summaries + ingest state → `<id>.tar.gz`. Import
restores meta + corpus only; user re-runs `ingest` (which is now idempotent
+ embedding-cached, so it's fast).

**Rationale**: Re-running ingest is cheaper than implementing N adapter-specific
bulk-restore APIs. The embedding cache hits 100% on restore, so the only real
work is the 4 store upserts.

## Consequences

- Frontend `ApiError` catch is 1 class instead of N.
- Runbook §1.7 documents `request_id` as the single handle that ties a user
  bug-report to backend traces.
- Idempotent ingest unblocks the M7.4 "drag-drop a folder" UX without burning
  budget on retries.
- SSE adds a single new client lifecycle (cancel mid-stream) — the rest of the
  request layer stays HTTP/JSON.
- The chunked-reveal fallback inside `qa/stream` is a known-temporary mock
  until the LLM adapter implements `complete_stream()` (tracked in M8 backlog).

## References

- `packages/core/api_errors.py` — ErrorCode + ErrorEnvelope
- `apps/api/middleware/{request_id,error_handler,rate_limit}.py`
- `apps/api/{auth,sse}.py`
- `apps/_shared/factories/ingest_runner.py` — idempotent runner
- `packages/ingestion/{state,idempotency}.py`
- `packages/core/backup.py` — export/import orchestration
- `apps/web/src/api/endpoints/qa.ts` — `streamQuestion` SSE client
- PRD §14 (M7 Hardening)
