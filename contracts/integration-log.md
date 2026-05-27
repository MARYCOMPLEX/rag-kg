# Integration Log

This file records frontend-backend integration issues, fixes, and verification status.

Use this log during local integration, E2E testing, and contract verification. Every issue should reference the related GitHub Issue when one exists.

## Status Values

| Status | Meaning |
| --- | --- |
| `open` | Issue has been found and still needs investigation or work. |
| `in-progress` | An Agent is actively fixing the issue. |
| `fixed` | A fix has been implemented. |
| `verified` | The fix has passed integration or E2E verification. |
| `wont-fix` | The team decided not to change behavior. |

## Log Template

```markdown
## <YYYY-MM-DD HH:mm> - <short issue title>

- Time:
- Agent:
- Issue:
- Cause:
- Fix status:
```

## Logs

## 2026-05-27 14:41 - Frontend evaluation dashboard API

- Time: 2026-05-27 14:41 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend requested a real API-mode evaluation dashboard endpoint to replace mock KPI, trend, budget alert, failure-case, and settings data.
- Fix status: fixed
- Fix:
  - Added OpenAPI contract for `GET /api/libraries/{libraryId}/evaluation/dashboard`.
  - Added the frontend `/api` evaluation adapter backed by existing eval snapshot and alert adapters when data is available.
  - Empty or unavailable evaluation stores return `200` with empty filter/KPI/trend/failure-case arrays and `budgetAlert: null`; `librarySettings` reports real library/global backend settings.
  - Missing library returns `404 LIBRARY_NOT_FOUND`; invalid dataset, invalid time range, and invalid explicit date range return `400 VALIDATION_ERROR`; invalid query parameter types return `422 VALIDATION_ERROR`.
- Verification:
  - `uv run --group test pytest tests\integration\api\test_frontend_evaluation_routes.py -q`: passed, 7 tests.
  - `uv run --group test pytest tests\integration\api\test_frontend_evaluation_routes.py tests\integration\api\test_frontend_graph_routes.py tests\integration\api\test_frontend_shell_routes.py tests\integration\api\test_frontend_documents_routes.py tests\integration\api\test_frontend_libraries_routes.py -q`: passed, 47 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps\api\routes\frontend_evaluation.py apps\api\routes\__init__.py tests\integration\api\test_frontend_evaluation_routes.py`: passed.
  - `uv run --group dev ruff format --check apps\api\routes\frontend_evaluation.py apps\api\routes\__init__.py tests\integration\api\test_frontend_evaluation_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make lint`: failed on pre-existing unrelated Ruff issues in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.

## 2026-05-27 14:34 - Frontend knowledge graph API

- Time: 2026-05-27 14:34 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend requested real API-mode graph workspace and entity detail endpoints to replace graph mock data and hardcoded entity drawer values.
- Fix status: fixed
- Fix:
  - Added OpenAPI contract for `GET /api/libraries/{libraryId}/graph` and `GET /api/libraries/{libraryId}/graph/entities/{entityId}`.
  - Added the frontend `/api` graph adapter backed by KG entity metadata and triples when available.
  - Empty or unavailable graph reads return `200` with empty node/edge arrays and zero summary labels rather than seeded graph content.
  - Missing library returns `404 LIBRARY_NOT_FOUND`; missing entity returns `404 NOT_FOUND`; invalid entity type filter or unsupported layout returns `400 VALIDATION_ERROR`; invalid numeric query bounds return `422 VALIDATION_ERROR`.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_graph_routes.py -q`: passed, 8 tests.
  - `uv run --group test pytest tests/integration/api/test_frontend_graph_routes.py tests/integration/api/test_frontend_shell_routes.py tests/integration/api/test_frontend_documents_routes.py tests/integration/api/test_frontend_libraries_routes.py -q`: passed, 40 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps/api/routes/frontend_graph.py apps/api/routes/__init__.py packages/indexing/adapters/neo4j_graph.py tests/integration/api/test_frontend_graph_routes.py`: passed.
  - `uv run --group dev ruff format --check apps/api/routes/frontend_graph.py apps/api/routes/__init__.py packages/indexing/adapters/neo4j_graph.py tests/integration/api/test_frontend_graph_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make lint`: failed on pre-existing unrelated Ruff issues in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.

## 2026-05-27 13:52 - Frontend command search and shell metadata API

- Time: 2026-05-27 13:52 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend requested real API-mode command palette search and dynamic shell metadata to replace mock search, recent sessions, and library stats.
- Fix status: fixed
- Fix:
  - Added OpenAPI contract for `GET /api/libraries/{libraryId}/search` and `GET /api/libraries/{libraryId}/shell/metadata`.
  - Added the frontend `/api` shell adapter while preserving existing `/v1/search` behavior.
  - Search is backed by the existing cross-resource search service and maps document/entity/library/action hits into frontend `id`, `type`, `label`, `meta`, `screen`, and `target` fields.
  - Shell metadata returns recent chat sessions from the context store and document/chunk stats from ingest state, with optional metadata omitted when unavailable.
- Verification:
  - `uv run --group test pytest tests\integration\api\test_frontend_shell_routes.py -q`: passed, 6 tests.
  - `uv run --group test pytest tests\integration\api\test_frontend_libraries_routes.py tests\integration\api\test_frontend_documents_routes.py tests\integration\api\test_frontend_shell_routes.py -q`: passed, 32 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps\api\routes\frontend_shell.py apps\api\routes\__init__.py tests\integration\api\test_frontend_shell_routes.py`: passed.
  - `uv run --group dev ruff format --check apps\api\routes\frontend_shell.py apps\api\routes\__init__.py tests\integration\api\test_frontend_shell_routes.py`: passed after formatting the touched route registry file.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - ASGI smoke against local app: search actions returned `200` with `generate_review`; shell metadata for `rag-agent` returned `200` with document/chunk stats; invalid scope returned `400 VALIDATION_ERROR`; missing library returned `404 LIBRARY_NOT_FOUND`.
  - `make lint`: failed on unrelated pre-existing Ruff issues in `apps\api\_activity_reader.py`, `apps\api\_notification_reader.py`, and `scripts\generate_ui_images.py`.

## 2026-05-27 13:16 - Frontend multipart document upload API

- Time: 2026-05-27 13:16 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend clarified that `/api/libraries/{libraryId}/documents:upload` should accept `multipart/form-data` with one or more PDF files under repeated field `files`, return frontend mutation feedback, and expose queued rows through the existing document list endpoint.
- Fix status: fixed
- Fix:
  - Added OpenAPI contract for `POST /api/libraries/{libraryId}/documents:upload`.
  - Added the frontend upload adapter while preserving existing `/v1` ingest behavior.
  - Accepted repeated multipart `files`, validated PDF file names/media types/magic bytes/size, staged accepted PDFs under backend `data/uploads/{libraryId}/`, enqueued `ingest_document` tasks, and wrote pending ingest-state rows.
  - Extended the existing error envelope code enum and HTTP mapping for upload-specific `413 PAYLOAD_TOO_LARGE` and `415 UNSUPPORTED_MEDIA_TYPE`.
- Verification:
  - `uv run --group test pytest tests\integration\api\test_frontend_documents_routes.py -q`: passed, 17 tests.
  - `uv run --group test pytest tests\unit\test_api_errors.py tests\integration\test_error_envelope.py -q`: passed, 7 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps\api\middleware\error_handler.py apps\api\routes\frontend_documents.py packages\core\api_errors.py tests\integration\api\test_frontend_documents_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - ASGI upload smoke with fake queue: success upload returned `202`; missing file returned `400 VALIDATION_ERROR`; non-PDF returned `415 UNSUPPORTED_MEDIA_TYPE`; missing library returned `404 LIBRARY_NOT_FOUND`; subsequent `GET /api/libraries/smoke-lib/documents` returned uploaded row `paper.pdf` with status `indexing`.

## 2026-05-27 05:41 - Backend document smoke seed and retry upstream envelope

- Time: 2026-05-27 05:41 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend needed backend-backed document rows to verify successful document drawer rendering and failed-document retry UI. Live retry of a failed document also exposed that Redis/Arq unavailability returned `500 INTERNAL_ERROR` instead of the contracted upstream error envelope.
- Fix status: fixed
- Fix:
  - Added `serve/scripts/seed_frontend_documents.py`, an idempotent local seed utility that writes normal ingest-state rows for `rag-agent`.
  - Seeded `2210.03629` as a ready document and `frontend-retry-failed` as a failed document in `data/state/ingest.sqlite`.
  - Updated `/api/libraries/{libraryId}/documents/{documentId}:retry` so queue initialization/enqueue failures return `503 UPSTREAM_ERROR` with message `Document retry queue unavailable`.
  - Added `503` to the HTTP exception error-code map so HTTP boundary code can use the existing upstream error envelope.
  - Kept OpenAPI unchanged because document read, retry success, and retry upstream-error responses were already contracted.
- Verification:
  - `uv run python scripts\seed_frontend_documents.py --library rag-agent`: passed; seeded 2 records.
  - `uv run --group test pytest tests\integration\api\test_frontend_documents_routes.py -q`: passed, 12 tests.
  - `uv run --group test pytest tests\integration\api\test_frontend_libraries_routes.py tests\integration\api\test_frontend_documents_routes.py -q`: passed, 21 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps\api\middleware\error_handler.py apps\api\routes\frontend_documents.py tests\integration\api\test_frontend_documents_routes.py scripts\seed_frontend_documents.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - Live Uvicorn smoke: `GET /healthz` returned 200; `GET /api/libraries/rag-agent/documents` returned 2 seeded rows; `GET /api/libraries/rag-agent/documents/2210.03629` returned document detail; `POST /api/libraries/rag-agent/documents/frontend-retry-failed:retry` returned `503 UPSTREAM_ERROR` while Redis was unavailable.

## 2026-05-27 05:18 - Document retry missing-resource envelope fix

- Time: 2026-05-27 05:18 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend API-mode verification found `POST /api/libraries/{libraryId}/documents/{documentId}:retry` returned delayed `500 INTERNAL_ERROR` with `TimeoutError` for missing libraries/documents because the task queue dependency initialized before resource validation.
- Fix status: fixed
- Fix:
  - Moved frontend retry queue initialization until after library existence, document existence, and retry-state validation.
  - Preserved successful failed-document retry behavior and existing `/v1/libraries/{library_id}/docs/{doc_id}/retry` behavior.
  - Kept OpenAPI unchanged because `404 LIBRARY_NOT_FOUND` and `404 NOT_FOUND` were already contracted.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_documents_routes.py -q`: passed, 11 tests.
  - `uv run --group test pytest tests/integration/api/test_frontend_libraries_routes.py tests/integration/api/test_frontend_documents_routes.py -q`: passed, 20 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps/api/routes/frontend_documents.py tests/integration/api/test_frontend_documents_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make lint`: still blocked by pre-existing unrelated Ruff failures in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.

## 2026-05-27 05:05 - Frontend document retry mutation API slice

- Time: 2026-05-27 05:05 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend requested API-mode document mutation feedback for `DocumentsView`, `DocumentDrawer`, and `documentRepository.ts`.
- Fix status: fixed
- Fix:
  - Added OpenAPI path and schema for `POST /api/libraries/{libraryId}/documents/{documentId}:retry`.
  - Added a frontend `/api` retry adapter that queues an `ingest_document` task for failed documents and returns `{ tone, title, detail, action }`.
  - Preserved existing `/v1/libraries/{library_id}/docs/{doc_id}/retry` behavior.
  - Kept `/api/libraries/{libraryId}/documents:upload` blocked because upload transport and body fields remain undefined.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_documents_routes.py -q`: passed, 9 tests.
  - `uv run --group test pytest tests/integration/api/test_frontend_libraries_routes.py tests/integration/api/test_frontend_documents_routes.py -q`: passed, 18 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps/api/routes/frontend_documents.py tests/integration/api/test_frontend_documents_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make lint`: still blocked by pre-existing unrelated Ruff failures in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.

## 2026-05-27 04:53 - Frontend document read API slice

- Time: 2026-05-27 04:53 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend requested API-mode document workspace and document detail reads for `DocumentsView`, `DocumentDrawer`, and `documentRepository.ts`.
- Fix status: fixed
- Fix:
  - Added OpenAPI paths and schemas for `GET /api/libraries/{libraryId}/documents` and `GET /api/libraries/{libraryId}/documents/{documentId}`.
  - Added a frontend `/api` document read adapter backed by existing library metadata and ingest-state records.
  - Empty libraries return `200` with zero summary labels and an empty `documents` list.
  - Detail responses include stable drawer fields, statistics, sections, and chunk previews when the vector adapter can provide per-document chunks.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_documents_routes.py -q`: passed, 6 tests.
  - `uv run --group test pytest tests/integration/api/test_frontend_libraries_routes.py tests/integration/api/test_frontend_documents_routes.py -q`: passed, 15 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps/api/routes/frontend_documents.py apps/api/routes/__init__.py tests/integration/api/test_frontend_documents_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make lint`: still blocked by pre-existing unrelated Ruff failures in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.

## 2026-05-27 04:25 - Frontend library create Qdrant fallback

- Time: 2026-05-27 04:25 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend API-mode verification found valid `POST /api/libraries` returned `500 INTERNAL_ERROR` when Qdrant returned `502 Bad Gateway`, while metadata had already been persisted and appeared in later `GET /api/libraries` responses.
- Fix status: fixed
- Fix:
  - Kept the frontend OpenAPI response contract unchanged: valid creates return `201 { library, redirectTo }`.
  - Changed the `/api/libraries` frontend adapter to treat vector resource initialization as best-effort for this first dashboard/create slice, logging initialization failures instead of failing the request after metadata creation.
  - Kept existing `/v1/libraries` lifecycle behavior unchanged.
  - Added default CORS origins for Vite fallback port `5174` on localhost and 127.0.0.1.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_libraries_routes.py -q`: passed, 9 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps/api/routes/frontend_libraries.py packages/core/config.py tests/integration/api/test_frontend_libraries_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - Live curl smoke against local Uvicorn: `GET /healthz` returned 200, `GET /api/libraries` returned summaries, `OPTIONS /api/libraries` from `http://localhost:5174` returned CORS 200, and valid `POST /api/libraries` returned 201 even while Qdrant returned 502 in the server log.
  - `make lint`: still blocked by pre-existing unrelated Ruff failures in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.

## 2026-05-27 04:20 - Frontend library list/create API slice

- Time: 2026-05-27 04:20 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend requested contract-backed `GET /api/libraries` and `POST /api/libraries` for API-mode library dashboard and create modal integration.
- Fix status: fixed
- Fix:
  - Added OpenAPI paths and schemas for `GET /api/libraries` and `POST /api/libraries`.
  - Added backend `/api/libraries` adapter that preserves existing `/v1/libraries` behavior and maps `library_id` to frontend `id`.
  - Returns stable default count labels (`0 documents`, `0 chunks`, `0 entities`) until aggregate stats are available.
  - Enabled local Vite dev CORS origins for browser API-mode verification.
- Verification:
  - `uv sync --group test --group dev`: passed.
  - `uv run --group test pytest tests/integration/api/test_frontend_libraries_routes.py -q`: passed, 7 tests, 1 Starlette deprecation warning for HTTP 422 constant.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside the new route.
  - `uv run --group dev ruff check apps/api/main.py packages/core/config.py apps/api/routes/frontend_libraries.py apps/api/routes/__init__.py tests/integration/api/test_frontend_libraries_routes.py`: passed.
  - `make lint`: blocked by pre-existing unrelated Ruff failures in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.
