# RAG-KG Copilot — Operator Runbook

Audience: whoever runs the system in production (single host or k8s).

## Bring-up

```
docker compose up -d   # qdrant, neo4j, opensearch, redis, minio, postgres
cp .env.example .env   # set LLM keys + API_KEY (optional)
uv sync
uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000
# in another shell:
cd apps/web && pnpm install && ./setup-configs.sh && pnpm dev
```

Health: `curl http://localhost:8000/healthz` → `{"status":"ok",...}`
Metrics: `curl http://localhost:8000/metrics`

## Endpoints surface

| Endpoint | Notes |
| --- | --- |
| `GET /healthz`, `/readyz` | Liveness / readiness |
| `GET /metrics` | Prometheus exposition (no auth required) |
| `POST /v1/libraries` | Create |
| `GET /v1/libraries` | List |
| `GET /v1/libraries/{id}` | Read |
| `DELETE /v1/libraries/{id}` | Hard delete + index purge |
| `POST /v1/libraries/{id}/ingest?force=` | Multipart PDF upload (idempotent by SHA-256) |
| `POST /v1/libraries/{id}/qa` | One-shot QA |
| `GET /v1/libraries/{id}/qa/stream?question=` | SSE QA |
| `GET /v1/libraries/{id}/stats` | Documents/chunks/entities/triples/communities counts |
| `GET /v1/libraries/{id}/schema` | Entity/relation type list + colors |
| `GET /v1/libraries/{id}/entities/{eid}/neighborhood?depth=1..3` | KG neighborhood |
| `POST /v1/libraries/{id}/review` | Generate literature review |
| `POST /v1/libraries/{id}/hypothesis` | Generate hypotheses between two entities |

All `/v1/**` routes accept the same `Authorization: Bearer ${API_KEY}`.
Errors come back as JSON envelopes:
```json
{
  "code": "LIBRARY_NOT_FOUND",
  "message": "Library not found: foo",
  "request_id": "8e3f4a5...",
  "details": { "library_id": "foo" }
}
```
Wire-stable codes are listed in `packages/core/api_errors.py:ErrorCode`.

## Observability

- Prometheus metrics exposed at `/metrics` — naming convention `rag_<comp>_<metric>_<unit>`
- OpenTelemetry traces (when `OTEL_ENABLED=true`) — exported to OTLP endpoint
- Langfuse LLM traces (when `LANGFUSE_ENABLED=true`)
- Every response carries `X-Request-Id` (echo of inbound or freshly minted)
- Error envelopes embed the same `request_id` so users can hand it to oncall

Dashboards live in `infra/grafana/dashboards/` — rag-llm-overview, rag-retrieval, rag-tasks. All have a Library filter.

## Rate limit

Off by default. To enable:
```
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=120
RATE_LIMIT_BURST=40
REDIS_URL=redis://localhost:6379/0
```
Algorithm: token-bucket per (principal, route) in Redis Lua. Principal =
`Bearer` token prefix or client IP. `/healthz`, `/readyz`, `/metrics`, `/docs`,
`/openapi.json` are bypassed. If Redis is unreachable the limiter
**fails open** (logs a warning) so the API stays up.

## Backups

Per-library:
```
uv run rkb library export <id> --out data/backups
uv run rkb library import data/backups/<id>.tar.gz --as <new-id>
```
Global snapshot (cron-friendly):
```
RETENTION_DAYS=30 scripts/snapshot_all.sh data/backups
```
The archive contains: `library_meta.json`, `documents.tar.gz`,
`qdrant.jsonl`, `graph.json`, `communities.jsonl`, `ingest_state.json`,
`manifest.json`. Importing only restores meta + corpus today —
re-run `rkb ingest` to repopulate indices (cheap because the embedding cache
hits 100%).

## Ingest idempotency

Each ingest call hashes the file (SHA-256) and looks it up in
`data/state/ingest.sqlite`. If status is `done`, returns the prior
`IngestResult` without re-doing parse/embed/upsert. Override with `--force`
(CLI) or `?force=true` (API).

## 10 common failures and how to fix them

### 1. `pyright` complains after a dependency upgrade
- Run `uv sync`, then `uv run pyright`
- If a vendor package ships `Unknown` types, prefer a narrow `cast(T, ...)` over `# pyright: ignore`

### 2. `redis: connection refused` in dev
- `docker compose up -d redis` — the rate limiter / cache assume it
- Confirm `REDIS_URL` points at the right port (default `6379`)

### 3. `qdrant: collection does not exist for library X`
- The `library create` step must run first — that's what initializes the per-library Qdrant collection
- Or run `await container.vector_index.init(library_id)` directly

### 4. Ingest stalls on a giant PDF
- Increase `embedding_timeout_s` and/or chunk size
- For files > 100 MB, split externally and upload per-chapter

### 5. SiliconFlow / OpenAI 5xx on QA
- Backoff is built in (3 attempts with 2s base wait)
- If persistent, check the upstream status page; the LLM client logs the model name + duration

### 6. `Library not found` after delete
- `library delete` purges Postgres meta + Qdrant collection. If you see ghost data, run `library purge` (CLI) — it's the bigger hammer

### 7. Frontend 401 loop
- `API_KEY` is set on backend but missing on frontend. Set `VITE_API_BASE` correctly and put the bearer token in the `Authorization` header (UI auto-attaches if you store it in `localStorage['rag-kg.token']`)

### 8. Stats endpoint returns zeros
- The library is brand new — ingest hasn't completed yet
- Or one of the index adapters returned an exception; check `journalctl` / `docker logs` for `WARN` lines tagged `stats:`

### 9. KG canvas freezes on big graph
- Default cap is 50 neighbors per expand. If you bumped it, lower it again
- `cytoscape-dagre` layout is heavier than the default `cose`; switch via the toolbar

### 10. Tests pass locally but CI is red
- Pin Python via `pyproject.toml` (3.13 currently)
- Container tests need `docker run --rm hello-world` to work in CI; if not available, run only unit tests and skip the `tests/integration/test_*_endpoint.py` (they need real backends)

## Upgrade procedure

1. Snapshot all libraries: `scripts/snapshot_all.sh data/backups/$(date +%F)`
2. Bump versions: `uv lock --upgrade`, `pnpm update`
3. Re-run gates: `uv run pyright && uv run ruff check . && uv run pytest -q && (cd apps/web && pnpm typecheck && pnpm lint && pnpm test)`
4. Rolling restart the API + worker; the Vite SPA is served as static assets so it just refreshes on the next page load
5. Spot-check 3 queries against the previous prod baseline

## Disaster recovery

- All state is on disk under `data/` (sqlite ingest state, Qdrant, Neo4j, MinIO)
- `docker compose down -v` is destructive — only do it after you have a snapshot
- To restore: extract the archive, run `rkb library import`, then re-ingest the corpus
- Embedding cache survives via the `data/cache/embeddings.sqlite` file — copy it across hosts to skip re-embedding on restore
