# AnyFast RAG/KG

AnyFast RAG/KG is a self-hosted research copilot for literature-heavy work. It organizes PDFs into isolated Libraries, indexes them for retrieval, builds graph-oriented context, and exposes API-backed Chat and Review workflows with traceable evidence.

## Current Status

The frontend/backend integration baseline is complete and verified locally.

- Frontend verified commit: `e984523eec5a9697964460a3d5e4b709db796f79`
- Backend verified commit: `b7eeeebbc19d036c0a7f938ca75635ab5d4f42bf`
- Final verification: <https://github.com/MARYCOMPLEX/rag-kg/issues/4#issuecomment-4567426819>

See [docs/ENGINEERING_HANDOFF.md](docs/ENGINEERING_HANDOFF.md) for operational details and the exact verification scope.

## Repository Layout

```text
contracts/   Shared API contract and integration notes
serve/       FastAPI backend, worker, CLI, domain packages, tests
web/         Vue 3 frontend
scripts/     Windows local startup, shutdown, and smoke verification helpers
```

## Core Capabilities

- Library-scoped document workspace.
- PDF/document ingestion surfaces and retry/upload feedback.
- Search, shell metadata, graph workspace, and evaluation dashboard APIs.
- Durable chat lifecycle with SSE events.
- Review generation lifecycle with current/create/SSE/regenerate/cancel.
- API-mode frontend with Vite proxy support for local browser verification.

## Local Development

Start backend API, Arq worker, and frontend in API mode:

```powershell
.\scripts\start-local.ps1 -BackendPort 8013 -FrontendPort 5181
```

Start Docker data services first when needed:

```powershell
.\scripts\start-local.ps1 -StartInfra -BackendPort 8013 -FrontendPort 5181
```

Verify the local pairing:

```powershell
.\scripts\verify-local.ps1 -BackendPort 8013 -FrontendPort 5181
```

Stop local processes started by the helper:

```powershell
.\scripts\stop-local.ps1
```

## Frontend

The frontend uses Vue 3, Pinia, TypeScript, and Vite. It can run in mock mode or API mode:

```powershell
$env:VITE_DATA_SOURCE='api'
$env:VITE_API_PROXY_TARGET='http://127.0.0.1:8013'
pnpm dev --host 127.0.0.1 --port 5181
```

The UI layers are:

```text
views/components -> stores -> services/repositories -> mocks or HTTP client -> domain types
```

## Backend

The backend uses FastAPI with layered packages for ingestion, structuring, indexing, retrieval, orchestration, LLM access, embeddings, and evaluation.

The local data layer uses Postgres, Redis, Qdrant, Neo4j, OpenSearch, and MinIO. SiliconFlow is used for the current LLM/embedding/reranker configuration.

## Coordination

The project uses GitHub Issues for multi-agent coordination:

- `#2`: frontend integration work.
- `#3`: backend integration work.
- `#4`: final integration verification.

No integration is considered complete until API-mode frontend behavior is verified against real backend endpoints.
