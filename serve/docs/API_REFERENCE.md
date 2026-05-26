# RAG-KG Copilot — HTTP API Reference

The authoritative source is the live `/openapi.json` (FastAPI auto-derives it
from the route signatures). This file is a hand-written summary kept in sync
during M7. To regenerate the OpenAPI JSON:

```
uv run python -c "import json; from apps.api.main import app; print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))" > docs/openapi.json
```

## Conventions

- **Base URL**: `http://localhost:8000` (default)
- **Content-Type**: `application/json` for non-multipart routes
- **Auth**: optional. When `API_KEY` is set, send `Authorization: Bearer <token>`
- **Request id**: every response carries `X-Request-Id`. Mirror the inbound header if you set one.
- **Errors**: every non-2xx returns `ErrorEnvelope` (code, message, request_id, details?). See `packages/core/api_errors.py:ErrorCode` for stable codes.

## Health & introspection

| Method | Path | Description |
| --- | --- | --- |
| GET | `/healthz` | Liveness — always 200 |
| GET | `/readyz` | Readiness — returns 200 (extends in M7+) |
| GET | `/metrics` | Prometheus text exposition |
| GET | `/docs` | Swagger UI |
| GET | `/openapi.json` | Raw OpenAPI 3 schema |

## Library CRUD

### Create
`POST /v1/libraries` — body `{library_id, name, description?}`.
- 201 → `LibraryResponse`
- 409 → `LIBRARY_ALREADY_EXISTS`
- 422 → validation

### List
`GET /v1/libraries` → `[LibraryResponse, ...]`

### Get
`GET /v1/libraries/{library_id}` → `LibraryResponse` or 404

### Delete
`DELETE /v1/libraries/{library_id}` → 204 or 404
Hard-removes Postgres meta + Qdrant collection + Neo4j subgraph + MinIO prefix.

## Document ingest

### Upload
`POST /v1/libraries/{library_id}/ingest?force=false` — multipart `file=<pdf>`
- 200 → `IngestResponse {doc_id, title, chunks_created, chunks_upserted}`
- 400 if not a PDF
- 404 if library missing

Idempotent by SHA-256: same file → same doc_id, no work. Use `?force=true` to re-ingest.

## Question answering

### One-shot
`POST /v1/libraries/{library_id}/qa` — body `{question}`
- 200 → `QAResponse`
- citations are the **only** authoritative chunks; the frontend filters all `[chunk_id]` markers against this list

### Streaming (SSE)
`GET /v1/libraries/{library_id}/qa/stream?question=...`
- Response headers: `content-type: text/event-stream`
- Events:
  - `event: meta\ndata: {library_id, model}`
  - `event: token\ndata: {text: "..."}` (zero or more)
  - `event: citations\ndata: [{chunk_id, doc_id, page, snippet}, ...]`
  - `event: done\ndata: {duration_ms, model, input_tokens, output_tokens}`
  - on error: `event: error\ndata: {code, message}`
- Backend honours `await request.is_disconnected()` between chunks

## Knowledge graph

### Neighborhood
`GET /v1/libraries/{library_id}/entities/{entity_id}/neighborhood?depth=1..3`
→ `NeighborhoodResponse {library_id, entity_id, depth, triples[]}`

### Schema (entity/relation types)
`GET /v1/libraries/{library_id}/schema`
→ `LibrarySchemaResponse {library_id, entity_types: [{type, color}], relation_types[]}`
Colors are deterministic from a 12-hue colorblind-safe palette.

## Library stats
`GET /v1/libraries/{library_id}/stats`
→ `LibraryStatsResponse {library_id, documents, chunks, entities, triples, communities, summary_freshness_iso}`
Returns 0 for any sub-count when the underlying adapter doesn't expose a count
helper — non-fatal.

## Generative tasks

### Review
`POST /v1/libraries/{library_id}/review` — body `{topic}`
→ `ReviewResponse {library_id, topic, abstract, sections[]}`. Each section
includes `citations[]`.

### Hypothesis
`POST /v1/libraries/{library_id}/hypothesis` — body `{head_entity_id, tail_entity_id}`
→ `HypothesisResponse {library_id, head_entity_id, tail_entity_id, hypotheses[]}`
Each hypothesis has `statement`, `rationale`, `confidence`, `counter_evidence`.

## Error code reference

```
VALIDATION_ERROR        # 400, 422
AUTH_ERROR              # 401, 403
NOT_FOUND               # 404 generic
LIBRARY_NOT_FOUND       # 404 specific
LIBRARY_ALREADY_EXISTS  # 409
CONFLICT                # 409 generic
RATE_LIMITED            # 429 + Retry-After header
UPSTREAM_ERROR          # transient external failure
INTERNAL_ERROR          # 500
```
