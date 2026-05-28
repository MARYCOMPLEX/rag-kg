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

## 2026-05-29 00:21 - Review create task-store library FK fix

- Time: 2026-05-29 00:21 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend review API-mode verification found `frontend-smoke-040442` in `GET /api/libraries`, but `POST /api/libraries/frontend-smoke-040442/reviews` returned `503 UPSTREAM_ERROR` because the durable task store rejected `library_id=frontend-smoke-040442` as a missing Postgres `libraries` FK.
- Fix status: fixed
- Fix:
  - Added task-store library materialization before frontend review create/regenerate enqueue.
  - The materialization upserts the API-visible filesystem `Library` metadata into the Postgres `libraries` table used by durable task FKs.
  - Preserved the existing `/api/libraries/{libraryId}/reviews*` OpenAPI response and error shapes; no frontend field changes are required.
- Verification:
  - `uv run --group test pytest tests\integration\api\test_frontend_review_routes.py -q`: passed, 11 tests.
  - `uv run --group test pytest tests\integration\api\test_frontend_review_routes.py tests\integration\worker\test_run_review_job.py -q`: passed, 13 tests.
  - `uv run --group dev ruff check apps\api\_task_deps.py apps\api\routes\frontend_reviews.py packages\orchestration\adapters\postgres_task_store.py tests\integration\api\test_frontend_review_routes.py`: passed.
  - `uv run --group dev ruff format --check apps\api\_task_deps.py apps\api\routes\frontend_reviews.py packages\orchestration\adapters\postgres_task_store.py tests\integration\api\test_frontend_review_routes.py`: passed.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make typecheck`: failed on pre-existing unrelated `apps/cli/main.py` adapter-list type errors at lines 208, 210, and 212; touched files produced no pyright errors.
  - Live smoke from a short-lived local API on `127.0.0.1:8014`: `GET /api/libraries` returned `frontend-smoke-040442` and `rag-agent`; `POST /api/libraries/frontend-smoke-040442/reviews` returned `202` with task `01KSQP72FE99F0XGR8099MS316`; `POST /api/libraries/rag-agent/reviews` returned `202` with task `01KSQP72M5ZN0Y5DSF6MN4J7JY`.

## 2026-05-28 22:13 - Review lifecycle durable stream runtime handoff

- Time: 2026-05-28 22:13 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: The first review lifecycle live smoke produced durable `status`, `pipeline`, `stats`, and `done` events but no live `draft_delta` or `citations`, so frontend verification was held.
- Fix status: fixed
- Fix:
  - Hardened the real review outline parser to accept JSON arrays and numbered/bulleted outline lists in addition to the existing object shape.
  - Kept the existing durable `/api/libraries/{libraryId}/reviews*` contract and route behavior unchanged.
  - Added unit coverage for JSON-array and numbered-list outline outputs.
- Verification:
  - `uv run --group test pytest tests/unit/test_review_task.py tests/unit/orchestration/test_review_citation_style.py -q`: passed, 16 tests.
  - `uv run --group test pytest tests/integration/api/test_frontend_review_routes.py tests/integration/worker/test_run_review_job.py -q`: passed, 11 tests.
  - `uv run --group dev ruff check packages/orchestration/tasks/review_task.py tests/unit/test_review_task.py apps/worker/jobs/run_review.py apps/api/routes/frontend_reviews.py tests/integration/api/test_frontend_review_routes.py tests/integration/worker/test_run_review_job.py`: passed.
  - `uv run --group dev ruff format --check packages/orchestration/tasks/review_task.py tests/unit/test_review_task.py apps/worker/jobs/run_review.py apps/api/routes/frontend_reviews.py tests/integration/api/test_frontend_review_routes.py tests/integration/worker/test_run_review_job.py`: passed.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make typecheck`: failed on pre-existing unrelated `apps/cli/main.py` adapter-list type errors at lines 208, 210, and 212; the touched review files produced no pyright errors.
  - Live smoke on `127.0.0.1:8013` with isolated `REDIS_URL=redis://localhost:6379/15`, local Postgres task store, Redis event bus, Arq worker, SiliconFlow LLM/embeddings, and the ingested `rag-agent` vector corpus: `POST /api/libraries/rag-agent/reviews` returned `202` with task `01KSQETREFN54TP1BF6826BADP`; SSE emitted event counts `status: 3`, `pipeline: 20`, `draft_delta: 6`, `citations: 1`, `stats: 1`, `done: 1`, `error: 0`.

## 2026-05-28 17:05 - Frontend review lifecycle API slice

- Time: 2026-05-28 17:05 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Supervisor dispatched the frontend review generation lifecycle API request so `ReviewView` can stop relying on mock review state and timer-driven progress.
- Fix status: implemented
- Fix:
  - Added OpenAPI paths and schemas for `GET /api/libraries/{libraryId}/reviews/current`, `POST /api/libraries/{libraryId}/reviews`, `POST /api/libraries/{libraryId}/reviews/{reviewRunId}/sections/{sectionId}:regenerate`, `POST /api/libraries/{libraryId}/reviews/{reviewRunId}:cancel`, and `GET /api/libraries/{libraryId}/reviews/{reviewRunId}/events`.
  - Added `apps/api/routes/frontend_reviews.py`, registered it in route discovery, and preserved existing `/v1/libraries/{library_id}/review` behavior.
  - Review create/regenerate now enqueue real durable `run_review` tasks; cancel uses the existing task queue cancellation path; current returns `200 { run: null }` when no active review task exists.
  - The review SSE adapter maps durable task events to frontend `draft_delta`, `pipeline`, `citations`, `stats`, `status`, `done`, and `error` events.
  - Updated the `run_review` worker to emit durable `draft_delta` and `citations` events from actual `ReviewGenerationTask` output when sections/citations are produced.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_review_routes.py tests/integration/worker/test_run_review_job.py -q`: passed, 11 tests.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `uv run --group dev ruff check apps/api/routes/frontend_reviews.py apps/api/routes/__init__.py apps/worker/jobs/run_review.py tests/integration/api/test_frontend_review_routes.py tests/integration/worker/test_run_review_job.py`: passed.
  - `uv run --group dev ruff format --check apps/api/routes/frontend_reviews.py apps/api/routes/__init__.py apps/worker/jobs/run_review.py tests/integration/api/test_frontend_review_routes.py tests/integration/worker/test_run_review_job.py`: passed.
  - `make typecheck`: failed on pre-existing unrelated `apps/cli/main.py` adapter list type errors; no new `frontend_reviews.py` pyright errors were reported.
  - Live smoke on `127.0.0.1:8012` with local API, Postgres task store, Redis event bus, and Arq worker: `GET /healthz` returned 200, `GET /api/libraries/rag-agent/reviews/current` returned 200, `POST /api/libraries/rag-agent/reviews` returned 202 with task `01KSPWVG557R4VP3YNB39YNQM5`, and the returned stream emitted durable `status`, `pipeline`, `stats`, and `done`.
- Runtime blocker:
  - The live review smoke did not emit `draft_delta` or `citations` for task `01KSPWVG557R4VP3YNB39YNQM5`; the worker completed the run with stats but no generated sections/citations surfaced in the task event stream.
  - Frontend review verification should wait for a backend runtime handoff that includes live `draft_delta` and, when grounded evidence is available, `citations` events. The route and worker tests cover those event shapes with durable task events.

## 2026-05-28 12:57 - Durable chat grounded frontend handoff

- Time: 2026-05-28 12:57 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: The durable chat task/event path was implemented, but frontend handoff needed runtime evidence that the real worker could produce grounded answer events after upstream model access was restored.
- Fix status: implemented
- Fix:
  - Kept the durable chat implementation unchanged: `/api/libraries/{libraryId}/chat/questions` enqueues `run_chat`, and `/api/libraries/{libraryId}/chat/questions/{taskId}/events` reads durable task/event-bus events.
  - Re-ran the live smoke with local Postgres task store, Redis event bus, Arq worker, SiliconFlow embeddings, and the `rag-agent` PDF corpus.
  - Ingested 5 local arXiv PDFs into the real vector store for `rag-agent`; Qdrant collection `chunks_rag_agent` reported `843` points with vector size `1024`.
  - Confirmed the durable stream emitted `status`, `token`, `evidence`, `citations`, `status`, and `done` events grounded in the ingested GraphRAG paper.
- Verification:
  - `uv run python -m apps.cli.main ingest data\\libraries\\rag-agent\\corpus\\spike --library rag-agent`: passed; `5 files (0 skipped), 843 chunks, 0 entities, 0 triples`; embedding cache `840 entries`.
  - `GET http://127.0.0.1:6333/collections/chunks_rag_agent`: passed; `points_count: 843`, vector size `1024`, status `green`.
  - `POST http://127.0.0.1:8010/api/libraries/rag-agent/chat/questions`: passed with `202`, task `01KSPF1DJE9JBJNR09DG357EXN`.
  - `GET -N http://127.0.0.1:8010/api/libraries/rag-agent/chat/questions/01KSPF1DJE9JBJNR09DG357EXN/events`: passed; event counts `status: 2`, `token: 15`, `evidence: 1`, `citations: 1`, `done: 1`.
  - Backend handoff target: frontend should verify chat API mode against backend SHA `3a2958ad6f68725f282b132cf6218c59083b4124` or newer.

## 2026-05-28 11:37 - Durable chat live runtime recheck

- Time: 2026-05-28 11:37 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: The durable chat code was pushed, but the previous live runtime check stopped at the Postgres task-store dependency before queue execution could be verified.
- Fix status: in-progress
- Fix:
  - Created the expected `rkb` role/database in the already-running local `anyfast-postgres` container because port `5432` was occupied by that container instead of the project compose Postgres.
  - Ran `uv run alembic upgrade head` against the `rkb` database.
  - Seeded the real `rag-agent` library metadata row into Postgres so the durable `tasks.library_id` foreign key can validate the existing filesystem library.
  - Kept backend code, OpenAPI, and production behavior unchanged.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_chat_routes.py tests/integration/worker/test_run_chat_job.py -q`: passed, 10 tests, 1 existing Starlette deprecation warning.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - Live runtime smoke on port `8011`: `GET /healthz` returned `200`; `GET /api/libraries/rag-agent/chat/session` returned `200`; `POST /api/libraries/rag-agent/chat/questions` returned `202` with task id `01KSPAJ2YVQ350ZNPRCT141D7H`; Arq worker started with `run_run_chat`; SSE streamed durable `status` then terminal `error`.
  - Current blocker: worker failed before grounded answer output because the embedding upstream returned `403 Forbidden` for `https://api.siliconflow.cn/v1/embeddings`. Frontend handoff remains blocked until the embedding API key/account/model access is fixed.

## 2026-05-28 03:30 - Durable chat task correction

- Time: 2026-05-28 03:30 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Supervisor rejected the previous frontend chat handoff because it used process-local SSE instead of the durable task/event architecture.
- Fix status: in-progress
- Fix:
  - Removed the process-local chat stream from the final `/api` chat path.
  - `POST /api/libraries/{libraryId}/chat/questions` now enqueues durable task type `run_chat` through `TaskQueue` and returns the durable frontend `streamUrl`.
  - `GET /api/libraries/{libraryId}/chat/questions/{taskId}/events` now validates task existence and maps durable `TaskEventBus` events into the frontend SSE contract.
  - Added worker job `apps/worker/jobs/run_chat.py`, registered it in `apps/worker/main.py`, and fixed Arq enqueue kwargs so keyword-only worker jobs receive `library_id`, `task_id`, and `input_payload`.
  - Added `503 UPSTREAM_ERROR` OpenAPI responses for chat question creation and stream dependency failures.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_chat_routes.py tests/integration/worker/test_run_chat_job.py -q`: passed, 10 tests, 1 existing Starlette deprecation warning.
  - `uv run --group test pytest tests/integration/api/test_frontend_documents_routes.py tests/integration/api/test_frontend_chat_routes.py tests/integration/worker/test_run_chat_job.py -q`: passed, 27 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps/api/_task_deps.py apps/api/routes/frontend_chat.py apps/api/routes/frontend_documents.py apps/worker/main.py apps/worker/jobs/run_chat.py packages/orchestration/queue.py packages/orchestration/adapters/arq_queue.py tests/integration/api/test_frontend_chat_routes.py tests/integration/worker/test_run_chat_job.py`: passed.
  - `uv run --group dev ruff format --check apps/api/_task_deps.py apps/api/routes/frontend_chat.py apps/api/routes/frontend_documents.py apps/worker/main.py apps/worker/jobs/run_chat.py packages/orchestration/queue.py packages/orchestration/adapters/arq_queue.py tests/integration/api/test_frontend_chat_routes.py tests/integration/worker/test_run_chat_job.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make lint`: failed on pre-existing unrelated Ruff issues in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.
  - Runtime check: local Redis responds and Arq worker starts with `run_run_chat` registered for task type `run_chat`, but live `POST /api/libraries/rag-agent/chat/questions` returns `503 UPSTREAM_ERROR` because the configured Postgres role `rkb` does not exist. Superseded by the 2026-05-28 11:37 recheck above, which fixed the local Postgres setup and exposed the current embedding upstream `403 Forbidden` blocker.

## 2026-05-27 18:23 - Frontend chat session and stream API

- Time: 2026-05-27 18:23 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend requested contract-backed ChatView APIs for loading the current session, creating questions, and consuming grounded answer stream events without seeded mock messages/evidence/tokens.
- Fix status: fixed
- Fix:
  - Added OpenAPI paths and schemas for `GET /api/libraries/{libraryId}/chat/session`, `POST /api/libraries/{libraryId}/chat/questions`, and `GET /api/libraries/{libraryId}/chat/questions/{taskId}/events`.
  - Added `apps/api/routes/frontend_chat.py` as a frontend `/api` adapter backed by the existing library repo, context service, and real QA task output.
  - Empty chat sessions return `200` with `messages: []` and `evidence: []`.
  - Question creation validates the request, persists the user turn, returns `202` with a pending assistant placeholder and `streamUrl`, then emits SSE events derived from backend QA output.
  - The current stream is process-local because the durable Arq task subsystem has no registered chat task type yet; this is documented in the API request note and the frontend should use the returned `streamUrl`.
- Verification:
  - `uv run --group test pytest tests/integration/api/test_frontend_chat_routes.py -q`: passed, 8 tests.
  - `uv run --group test pytest tests/integration/api/test_frontend_chat_routes.py tests/integration/api/test_frontend_libraries_routes.py tests/integration/api/test_frontend_documents_routes.py tests/integration/api/test_frontend_shell_routes.py tests/integration/api/test_frontend_graph_routes.py tests/integration/api/test_frontend_evaluation_routes.py -q`: passed, 57 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps/api/routes/frontend_chat.py apps/api/routes/__init__.py tests/integration/api/test_frontend_chat_routes.py`: passed.
  - `uv run --group dev ruff format --check apps/api/routes/frontend_chat.py apps/api/routes/__init__.py tests/integration/api/test_frontend_chat_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - `make lint`: failed on pre-existing unrelated Ruff issues in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.

## 2026-05-27 17:00 - Evaluation dashboard slow-store timeout fix

- Time: 2026-05-27 17:00 +08:00
- Agent: Backend Agent
- Issue: #3
- Cause: Frontend API-mode verification found valid `GET /api/libraries/{libraryId}/evaluation/dashboard` requests timed out when local eval snapshot/alert stores were slow or unavailable, while invalid dataset/time-range and missing-library requests returned promptly.
- Fix status: fixed
- Fix:
  - Added bounded eval-store reads in the frontend `/api` evaluation adapter.
  - Loaded dataset KPIs, trend rows, and active alerts concurrently so unavailable stores degrade to the contracted empty dashboard instead of blocking the response.
  - Kept OpenAPI unchanged because the endpoint still returns the existing `EvaluationDashboard` schema and uses the existing error envelope.
- Verification:
  - `uv run --group test pytest tests\integration\api\test_frontend_evaluation_routes.py -q`: passed, 8 tests.
  - `uv run --group test pytest tests\integration\api\test_frontend_evaluation_routes.py tests\integration\api\test_frontend_graph_routes.py tests\integration\api\test_frontend_shell_routes.py tests\integration\api\test_frontend_documents_routes.py tests\integration\api\test_frontend_libraries_routes.py -q`: passed, 48 tests, 1 existing Starlette deprecation warning.
  - `uv run --group dev ruff check apps\api\routes\frontend_evaluation.py tests\integration\api\test_frontend_evaluation_routes.py`: passed.
  - `uv run --group dev ruff format --check apps\api\routes\frontend_evaluation.py tests\integration\api\test_frontend_evaluation_routes.py`: passed.
  - `make typecheck`: passed, 0 errors with 20 existing warnings outside this change.
  - `uv run python -c "import yaml; yaml.safe_load(open('..\\contracts\\openapi.yaml', encoding='utf-8')); print('openapi yaml parsed')"`: passed.
  - ASGI smoke against local app: `GET /api/libraries/rag-agent/evaluation/dashboard` returned `200` in 1.19s with the contracted empty dashboard while local eval stores had no data.
  - `make lint`: failed on pre-existing unrelated Ruff issues in `apps/api/_activity_reader.py`, `apps/api/_notification_reader.py`, and `scripts/generate_ui_images.py`.

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
## 2026-05-29 02:41 - Vite dev proxy restored for API-mode browser smoke

- Time: 2026-05-29 02:41 +08:00
- Agent: Frontend Agent
- Issue: #2
- Backend SHA: `b7eeeebbc19d036c0a7f938ca75635ab5d4f42bf`
- Frontend SHA before this log update: `ac690b8`
- Verification:
  - Updated the tracked `web/vite.config.js` so `pnpm dev` now loads the `/api` proxy alongside the existing TypeScript config and honors `VITE_API_PROXY_TARGET` / `VITE_API_BASE_URL`.
  - Started Vite on `http://127.0.0.1:5178` with `VITE_DATA_SOURCE=api` and `VITE_API_PROXY_TARGET=http://127.0.0.1:8013`.
  - `GET http://127.0.0.1:5178/api/libraries`: passed with `200 application/json` from the backend instead of Vite HTML.
  - Browser smoke at `http://127.0.0.1:5178/libraries/frontend-smoke-040442/review`: passed API-mode library shell metadata load, empty review state, `POST /api/libraries/frontend-smoke-040442/reviews` with `202`, and live SSE stream wiring without page errors.
  - Browser smoke at `http://127.0.0.1:5178/libraries/rag-agent/chat`: passed API-mode session load, `POST /api/libraries/rag-agent/chat/questions` with `202`, and live SSE stream wiring without page errors.
  - `VITE_DATA_SOURCE=api VITE_API_PROXY_TARGET=http://127.0.0.1:8013 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_PROXY_TARGET=http://127.0.0.1:8013 pnpm build`: passed.
- Fix status: verified
- Backend note:
  - The dev-server proxy path is back in sync with the TypeScript config, so browser API-mode smoke can use the local frontend origin again without falling through to HTML responses.

## 2026-05-28 23:59 - Review lifecycle API-mode verified through proxy

- Time: 2026-05-28 23:59 +08:00
- Agent: Frontend Agent
- Issue: #2
- Backend SHA: `7e47ad572381c46c10c9af52ca1ae7080f9f1989`
- Frontend SHA before this log update: `6092e6ff4828ceb5443181ff433ed42b8c8c6614`
- Verification:
  - Added a Vite dev proxy for `/api` and switched API clients to relative URLs when `VITE_API_PROXY_TARGET` is set, so browser API-mode requests stay same-origin during local review work.
  - `GET /api/libraries/rag-agent/reviews/current`: passed with `200 { run: null }`.
  - `POST /api/libraries/rag-agent/reviews` with `{}`: passed with `202` and the contracted snapshot shape (`run`, `pipelineSteps`, `runStats`, `citations`, `draft`, `streamUrl`).
  - `POST /api/libraries/rag-agent/reviews/01KSQMZ3DYZZM9154X829ESJPA/sections/retrieval-augmented-generation-for-knowledge-intensive-tasks:regenerate`: passed with `202` and a new queued run snapshot.
  - `POST /api/libraries/rag-agent/reviews/01KSQN47S56STMVMD0RTBHF5DV:cancel`: passed with warning feedback and a cancelled `run`.
  - Browser smoke at `http://127.0.0.1:5176/libraries/rag-agent/review`: passed API-mode empty state, start-review action, queued/live run rendering, live pipeline and draft updates, citation updates, and cancel control through the Vite proxy.
  - Browser smoke at `http://127.0.0.1:5176/libraries/frontend-smoke-040442/review`: empty state rendered, but start review returned `503 UPSTREAM_ERROR` because the backend task store rejected `library_id=frontend-smoke-040442` as a foreign-key miss.
  - `pnpm typecheck`: passed.
  - `pnpm build`: passed.
- Fix status: verified
- Backend note:
  - The review lifecycle contract is now exercised end to end for `rag-agent`.
  - The smoke library shows a backend data consistency issue on create that is separate from the contract itself.

## 2026-05-27 18:58 - Evaluation dashboard API-mode retest verified

- Time: 2026-05-27 18:58 +08:00
- Agent: Frontend Agent
- Issue: #2
- Backend SHA: `63789540fa185ee59f630b66c2e9a9448065414d`
- Frontend SHA before this log update: `bebc9c0fb20bc7a67dff8dc0b214e93ceec0e5bc`
- Verification:
  - Restarted the local backend listener because the existing Uvicorn process on port `8000` was started before the latest backend checkout; retest after restart reflects backend SHA `63789540fa185ee59f630b66c2e9a9448065414d`.
  - `GET http://localhost:8000/healthz`: passed with `{"status":"ok","version":"0.1.0"}`.
  - `GET /api/libraries/rag-agent/evaluation/dashboard`: passed with `200` in `1207ms`, returning the contracted empty dashboard with `budgetAlert: null`, empty KPI/trend/failure arrays, and populated `librarySettings`.
  - `GET /api/libraries/rag-agent/evaluation/dashboard?dataset=smoke&timeRange=7d`: passed with `200` in `1059ms` and `timeRangeLabel: Last 7 days`.
  - `GET /api/libraries/rag-agent/evaluation/dashboard?dataset=smoke&from=2026-05-01&to=2026-05-27`: passed with `200` in `1066ms` and the explicit date label.
  - Invalid dataset `unknown`: passed with `400 VALIDATION_ERROR`.
  - Invalid time range `14d`: passed with `400 VALIDATION_ERROR`.
  - Missing library: passed with `404 LIBRARY_NOT_FOUND`.
  - Playwright via system Chrome at `http://127.0.0.1:5174/libraries/rag-agent/eval`: passed empty dashboard rendering without timeout, no mock KPI/budget/trend/failure content, backend `librarySettings` rendering, browser-context filtered fetch, and traceable error/retry rendering.
- Fix status: verified
- Backend note:
  - The evaluation dashboard blocker is cleared in a restarted backend process at the requested SHA.
  - Empty dashboard responses expose no dataset/time-range filter options, so select-control filter changes are not available until backend returns filter choices; the filtered API requests themselves no longer hang.

## 2026-05-27 18:22 - Upload, command search, and shell metadata smoke verified

- Time: 2026-05-27 18:22 +08:00
- Agent: Frontend Agent
- Issue: #2
- Backend SHA: `63789540fa185ee59f630b66c2e9a9448065414d`
- Frontend SHA before this log update: `0e67b063e8394c920a7f58c889006c09be2579ab`
- Verification:
  - `GET http://localhost:8000/healthz`: passed with `{"status":"ok","version":"0.1.0"}`.
  - Browser smoke at `http://127.0.0.1:5174/libraries/rag-agent/docs`: passed API-backed document list, shell metadata rendering, and upload entry points.
  - Upload PDF smoke: `POST /api/libraries/rag-agent/documents:upload` returned `503 UPSTREAM_ERROR` with message `Document upload queue unavailable`; the document list stayed at 2 rows and no fake success row rendered.
  - Command palette blank search: passed empty state `No commands found in this Library.`.
  - Command palette search for `review`: passed `Actions` result `Generate Literature Review`, and selecting it navigated to `/libraries/rag-agent/review`.
  - Side-nav metadata: rendered `Documents 2`, `Chunks 65`, and `No recent sessions` from the backend shell metadata response.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
- Fix status: verified
- Backend note:
  - Upload transport is wired; the remaining upload blocker is backend queue availability for the `202` path.
  - Search and shell metadata are wired and rendering in API mode.

## 2026-05-27 17:25 - Evaluation dashboard fix still exceeds frontend timeout

- Time: 2026-05-27 17:25 +08:00
- Agent: Frontend Agent
- Issue: #2
- Backend SHA: `c6ab292e2d5c71ecabbf96e7b83338e3c061feb2`
- Frontend SHA before this log update: `5d014b0`
- Frontend fix:
  - Kept backend-provided `librarySettings` visible for empty successful evaluation dashboards without rendering empty/mock KPI, trend, or failure-case panels.
- Verification:
  - `GET http://localhost:8000/healthz`: passed with `{"status":"ok","version":"0.1.0"}`.
  - `GET /api/libraries/rag-agent/evaluation/dashboard`: returned `200` with the contracted empty dashboard, but took `32.684444s`.
  - `GET /api/libraries/rag-agent/evaluation/dashboard?dataset=smoke&timeRange=7d`: returned `200` with the contracted empty dashboard, but took `32.679893s`.
  - `GET /api/libraries/rag-agent/evaluation/dashboard?dataset=smoke&from=2026-05-01&to=2026-05-27`: returned `200` with the contracted empty dashboard, but took `32.758821s`.
  - Invalid dataset `unknown`: passed with `400 VALIDATION_ERROR`.
  - Invalid time range `14d`: passed with `400 VALIDATION_ERROR`.
  - Missing library: passed with `404 LIBRARY_NOT_FOUND`.
  - Playwright via system Chrome at `http://127.0.0.1:5174/libraries/rag-agent/eval`: still reached the frontend `20s` API timeout before the valid dashboard response, so browser empty-success rendering remains blocked.
- Fix status: blocked
- Backend follow-up:
  - Valid evaluation dashboard reads should return the contracted empty dashboard within the frontend request timeout, ideally without waiting on unavailable/empty evaluation stores.

## 2026-05-27 16:27 - Upload search shell graph integrated, evaluation dashboard timeout

- Time: 2026-05-27 16:27 +08:00
- Agent: Frontend Agent
- Issue: #2
- Backend SHA: `3535ca6c978c9a89c65db6be65f75cc1ce6d6b46`
- Frontend fix:
  - Wired document upload to `multipart/form-data` with repeated `files` fields and no JSON `Content-Type`.
  - Added API-backed command search and shell metadata repositories/stores for `CommandPalette` and `SideNav`.
  - Added API-backed graph workspace/entity repositories and loading/empty/error states.
  - Added API-backed evaluation dashboard repository, filters, panels, and a 20s frontend request timeout so hanging requests surface as retryable errors.
- Verification:
  - `GET /healthz`: passed with `{"status":"ok","version":"0.1.0"}`.
  - Upload no files: `400 VALIDATION_ERROR`; non-PDF: `415 UNSUPPORTED_MEDIA_TYPE`; missing library: `404 LIBRARY_NOT_FOUND`; PDF while Redis/Arq unavailable: expected `503 UPSTREAM_ERROR`.
  - Search actions/broad/blank/one-character/invalid-scope and shell metadata/missing-library checks passed.
  - Graph workspace/filtered/invalid filter/invalid layout/missing library/missing entity checks passed; entity detail success skipped because live graph had no nodes.
  - Evaluation invalid dataset, invalid time range, and missing library checks passed.
  - Evaluation valid dashboard requests timed out after 30 seconds with no HTTP status/body.
  - Playwright via system Chrome at `http://127.0.0.1:5174`: passed document upload feedback, command palette search/empty/navigation, side-nav metadata, graph empty state, and evaluation timeout error state.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
- Fix status: verified for upload transport/error handling, search/shell, and graph empty workspace; blocked for valid evaluation dashboard reads.
- Backend follow-up:
  - `GET /api/libraries/rag-agent/evaluation/dashboard` and valid filtered variants should return the contracted empty dashboard promptly instead of hanging past 30 seconds.
  - Redis/Arq remains unavailable locally, so upload `202` success and queued indexing row refresh still need verification in an environment with the queue running.

## 2026-05-27 13:22 - Review and graph seed content moved behind mock boundary

- Time: 2026-05-27 13:22 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Review draft prose and graph canvas/entity seed values still lived directly in components and stores, even though API mode already hid those surfaces pending OpenAPI contracts.
- Fix status: fixed
- Frontend fix:
  - Added typed review draft and graph canvas/entity seed structures.
  - Moved hardcoded review draft text, citation markers, graph SVG nodes/edges, graph counts, and graph entity detail values into `web/src/mocks`.
  - Kept the existing non-API mock experience while preserving API-mode pending-contract behavior.
- Verification:
  - `pnpm typecheck`: passed.
  - `pnpm build`: passed.
  - `rg -n "Recent advancements in GraphRAG|MOCK-ENTITY-001|8,491 entities|31,219 triples|Graph-augmented RAG|D\. Edge et al\.|MultiHop-RAG|Leiden algorithm|Community detection|Mock Author|Haiku 4\.5|14,328 tokens" src --glob "!src/mocks/**"`: passed with no matches.
  - Playwright smoke at `http://127.0.0.1:5176/libraries/rag-agent/review` and `/libraries/rag-agent/kg` in mock mode: passed; review draft and graph/entity details still render through mock-backed store data.
- Backend follow-up:
  - No new backend requirement from this cleanup. Existing requested review and graph contracts remain blocked until OpenAPI defines those endpoints.

## 2026-05-27 12:52 - API mode hides mock graph workspace data

- Time: 2026-05-27 12:52 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `GraphView.vue`, `GraphEntityDrawer.vue`, and `useGraphStore` still rendered seeded graph filters, static SVG nodes and edges, graph counts, entity detail values, mention trends, co-occurring entities, and cite-in-chat mutation behavior in API mode even though OpenAPI does not define graph workspace or entity detail contracts.
- Fix status: fixed
- Frontend fix:
  - Gated graph filters, mention trends, co-occurring entities, selected node state, context menu, and cite-in-chat behavior behind non-API data source mode.
  - Added an API-mode pending-contract empty state for the graph workspace.
  - Hid the static graph canvas and entity drawer in API mode.
  - Removed targeted fake review/graph strings from non-mock source surfaces.
- Verification:
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
  - `rg -n "GraphRAG advances|Yue Lin|Live Citations \(37\)|Spec: Switch to WebGL|C-000123|Graph RAG|taskStore keeps|POST /v1/tasks/rev_2405" src --glob "!src/mocks/**"`: passed with no matches.
  - Playwright smoke at `http://127.0.0.1:5175/libraries/rag-agent/review` and `/libraries/rag-agent/kg`: passed; both pending-contract states rendered and seeded review/graph content stayed hidden.

## 2026-05-27 12:47 - API mode hides mock review run data

- Time: 2026-05-27 12:47 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `ReviewView.vue`, `useReviewStore`, and review components still rendered seeded pipeline steps, run stats, citation rows, hardcoded draft prose, notice-bar prototype notes, and timer-driven progress in API mode even though OpenAPI does not define the review run lifecycle or stream contracts.
- Fix status: fixed
- Frontend fix:
  - Gated review pipeline, citations, stats, runtime progress, and mutation simulation behind non-API data source mode.
  - Added an API-mode pending-contract empty state for the review workspace.
  - Made citation count/footer rendering derive from the provided citation array instead of fixed mock counts.
  - Removed a fake review run ID from the background task pill.
- Verification:
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
  - Playwright smoke at `http://127.0.0.1:5175/libraries/rag-agent/review`: passed; review pending-contract state rendered and seeded draft/citation count content stayed hidden.

## 2026-05-27 12:34 - API mode hides mock chat session data

- Time: 2026-05-27 12:34 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `useChatStore` and `ChatView.vue` still rendered seeded chat messages, evidence cards, static session copy, and timer-driven answer tokens in API mode even though OpenAPI does not define the chat session, question, or stream contracts.
- Fix status: fixed
- Frontend fix:
  - Gated chat mock messages, evidence, active citation state, and simulated stream tokens behind non-API data source mode.
  - Added API-mode pending-contract empty states for the conversation and evidence panel.
  - Disabled chat sending in API mode with a traceable pending-contract toast.
  - Made `CitationPopover.vue` tolerate an empty evidence list.
- Verification:
  - `pnpm typecheck`: passed.
  - `pnpm build`: passed.

## 2026-05-27 12:17 - API mode hides mock evaluation dashboard

- Time: 2026-05-27 12:17 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `EvaluationView.vue` still rendered seeded KPI cards, trend data, failure cases, budget warning, model labels, budget limits, and data actions in API mode even though OpenAPI does not define `/api/libraries/{libraryId}/evaluation/dashboard`.
- Fix status: fixed
- Frontend fix:
  - Gated `useEvaluationStore` mock dashboard data behind non-API data source mode.
  - Updated `EvaluationView.vue` to hide mock dashboard/settings sections in API mode and render a pending-contract empty state while preserving the real library selector.
- Verification:
  - `pnpm typecheck`: passed.
  - `pnpm build`: passed.

## 2026-05-27 12:04 - API mode hides mock search and shell metadata

- Time: 2026-05-27 12:04 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `useSearchStore`, `useUiStore`, `CommandPalette.vue`, and `SideNav.vue` still rendered mock document/entity search results, recent sessions, library stats, storage, and profile metadata when the app was running in API mode without a contracted search/shell metadata backend.
- Fix status: fixed
- Frontend fix:
  - Gated mock command search records behind non-API data source mode.
  - Gated mock recent sessions, library stats, storage, and profile metadata behind non-API data source mode.
  - Added shell empty states for API mode and removed fixture-specific command palette section copy.
  - Removed a fixture-specific graph canvas accessibility label from `web/src/views/GraphView.vue`.
- Verification:
  - `pnpm typecheck`: passed.

## 2026-05-27 12:01 - Evaluation library selector fake options removed

- Time: 2026-05-27 12:01 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: The evaluation dashboard still displayed hardcoded fake library selector options and a stale `graphrag-survey` settings label after the evaluation API request was clarified.
- Fix status: fixed
- Frontend fix:
  - Updated `web/src/views/EvaluationView.vue` to source the evaluation library selector from `useLibraryStore`.
  - Kept evaluation library selection aligned with workspace routing through `goToScreen('eval')`.
  - Updated `web/src/components/evaluation/LibrarySettingsPanel.vue` to receive the selected library label as a prop instead of rendering a fixture label.
- Verification:
  - `pnpm typecheck`: passed.

## 2026-05-27 11:34 - Static navigation moved out of mocks

- Time: 2026-05-27 11:34 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Frontend-owned route navigation and suggested command actions were exported from `web/src/mocks/navigation.ts`, and the suggested command actions still contained the removed hardcoded `graphrag-survey` library slug.
- Fix status: fixed
- Frontend fix:
  - Moved `screenNavigation`, `mainNavigation`, and suggested command action templates into `web/src/app/staticNavigation.ts`.
  - Updated `useUiStore` to build suggested command actions from the active library instead of a mock library slug.
  - Left only dynamic shell metadata placeholders (`recentSessions`, `libraryStats`) in `web/src/mocks/navigation.ts` until OpenAPI defines `/api/libraries/{libraryId}/shell/metadata`.
- Verification:
  - `pnpm typecheck`: passed.

## 2026-05-27 11:19 - Command search and shell metadata API request clarified

- Time: 2026-05-27 11:19 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `CommandPalette.vue`, `search.ts`, `ui.ts`, `web/src/mocks/search.ts`, and `web/src/mocks/navigation.ts` still mix backend-owned search/session/stat data with frontend-owned route/navigation constants; the existing API request did not define which shell data should come from backend and which should stay static.
- Fix status: open
- Contract request:
  - Requested command search endpoint: `GET /api/libraries/{libraryId}/search`.
  - Requested shell metadata endpoint: `GET /api/libraries/{libraryId}/shell/metadata`.
  - Requested search scopes: `documents`, `entities`, `libraries`, and `actions`.
  - Requested dynamic shell fields: `recentSessions`, `libraryStats`, optional `notifications`, and optional `profile`.
  - Frontend-static decision: `screenNavigation`, `mainNavigation`, TopBar section labels, keyboard shortcuts, footer hints, route names, and icon names remain frontend-owned UI chrome.
- Verification:
  - `pnpm typecheck`: passed.

## 2026-05-27 11:17 - Evaluation API request clarified

- Time: 2026-05-27 11:17 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `EvaluationView.vue`, `LibrarySettingsPanel.vue`, `evaluation.ts`, and `web/src/mocks/evaluation.ts` still depend on mock KPI/trend/failure rows plus hardcoded library selector, budget alert, model labels, budget limits, and filter copy; the existing API request did not give backend exact dashboard, filter, alert, settings, and empty-state shapes to implement.
- Fix status: open
- Contract request:
  - Requested dashboard endpoint: `GET /api/libraries/{libraryId}/evaluation/dashboard`.
  - Requested query params: optional `dataset`, optional `timeRange`, optional ISO `from`/`to`.
  - Requested response groups: `summary`, `filters`, `budgetAlert`, `kpis`, `trend`, `failureCases`, and `librarySettings`.
  - Requested empty behavior: return `200` with empty metric arrays and `budgetAlert: null` where applicable, rather than seeded/fake evaluation data.
- Verification:
  - `pnpm typecheck`: passed.

## 2026-05-27 11:02 - Graph API request clarified

- Time: 2026-05-27 11:02 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `GraphView`, `GraphEntityDrawer`, and `graph.ts` still depend on `web/src/mocks/graph.ts` plus hardcoded SVG nodes, edges, counts, entity IDs, aliases, stats, and chart labels; the existing API request did not give backend exact graph workspace and entity detail shapes to implement.
- Fix status: open
- Contract request:
  - Requested graph workspace endpoint: `GET /api/libraries/{libraryId}/graph`.
  - Requested entity detail endpoint: `GET /api/libraries/{libraryId}/graph/entities/{entityId}`.
  - Requested workspace query params: optional `entityTypes`, `minConfidence`, `limit`, and `layout`.
  - Requested workspace response: `filters`, `canvas`, and `summary`, including node/edge arrays and large-graph fallback metadata.
  - Requested entity detail response: stable entity identity, aliases, summary, network stats, mention trend, and co-occurring entities.
- Verification:
  - `pnpm typecheck`: passed.
- Backend follow-up:
  - Update OpenAPI for the graph workspace/entity detail contract, or reject with a concrete alternate before frontend removes `web/src/mocks/graph.ts` and static graph markup.

## 2026-05-27 10:59 - Review API request clarified

- Time: 2026-05-27 10:59 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `ReviewView`, `review.ts`, and review components still depend on `web/src/mocks/review.ts`, hardcoded draft prose/citation markers, and timer-generated progress/token counts; the existing API request did not give backend exact current-run/create/regenerate/cancel/SSE contracts to implement.
- Fix status: open
- Contract request:
  - Requested current run endpoint: `GET /api/libraries/{libraryId}/reviews/current`.
  - Requested run creation endpoint: `POST /api/libraries/{libraryId}/reviews`.
  - Requested section regeneration endpoint: `POST /api/libraries/{libraryId}/reviews/{reviewRunId}/sections/{sectionId}:regenerate`.
  - Requested cancel endpoint: `POST /api/libraries/{libraryId}/reviews/{reviewRunId}:cancel`.
  - Requested stream behavior: SSE `draft_delta`, `pipeline`, `citations`, `stats`, `status`, `done`, and `error` events.
- Verification:
  - `pnpm typecheck`: passed.
- Backend follow-up:
  - Update OpenAPI for the review run lifecycle and SSE contract, or reject with a concrete alternate before frontend removes `web/src/mocks/review.ts` and hardcoded draft content.

## 2026-05-27 10:32 - Chat API request clarified

- Time: 2026-05-27 10:32 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `ChatView` and `chat.ts` still depend on seeded messages, evidence records, and timer-generated answer tokens from `web/src/mocks/chat.ts`; the existing API request did not give backend an exact session/question/stream contract to implement.
- Fix status: open
- Contract request:
  - Requested current session endpoint: `GET /api/libraries/{libraryId}/chat/session`.
  - Requested question creation endpoint: `POST /api/libraries/{libraryId}/chat/questions`.
  - Requested question body: `question`, optional `sessionId`, optional `context` with selected `evidenceIds` and `entityIds`.
  - Requested success response: `202 { taskId, streamUrl, userMessage, assistantMessage, evidence? }`.
  - Requested stream behavior: SSE token, citations, evidence, status, done, and error events.
- Verification:
  - `pnpm typecheck`: passed.
- Backend follow-up:
  - Update OpenAPI for the chat session/question/SSE contract or reject with a concrete alternate before frontend removes `web/src/mocks/chat.ts` from the chat store.

## 2026-05-27 10:03 - Document queue footer no longer uses hardcoded counts

- Time: 2026-05-27 10:03 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `DocumentsView` still rendered fixed queue metrics (`14 indexing`, `3 parsing`, `1 failed`, and a fake daily cap) even when the document workspace was loaded from the real API.
- Fix status: fixed
- Frontend fix:
  - Queue footer now derives indexing, parsing, and failed counts from the current `documents` rows returned by the active repository.
  - Removed the fake daily spend/cap display because no OpenAPI contract currently provides that metadata.
- Verification:
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
- Remaining backend follow-up:
  - Upload remains requested as multipart `POST /api/libraries/{libraryId}/documents:upload`.
  - Dedicated queue/cost metadata should stay absent from the UI until OpenAPI defines it.

## 2026-05-27 05:53 - Seeded document read/detail verified in API mode

- Time: 2026-05-27 05:53 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Backend handed back seeded `rag-agent` document data so frontend could verify successful document list/detail rendering and failed-row retry handling without frontend fixtures.
- Fix status: verified for document read/detail; retry success still depends on Redis/Arq availability; upload remains requested.
- Backend SHA: `ee96a8226e1ace1602e60c48e8582a5f0e74a9af`
- Frontend SHA tested before log update: `7ed4092`
- Verification:
  - `GET http://localhost:8000/healthz`: passed with `{"status":"ok","version":"0.1.0"}`.
  - `GET http://localhost:8000/api/libraries`: passed and returned `frontend-smoke-040442` and `rag-agent`.
  - `OPTIONS http://localhost:8000/api/libraries/rag-agent/documents` from `http://127.0.0.1:5174`: passed with `Access-Control-Allow-Origin: http://127.0.0.1:5174`.
  - `GET http://localhost:8000/api/libraries/rag-agent/documents`: passed with 2 seeded rows, ready document `2210.03629` and failed document `frontend-retry-failed`.
  - `GET http://localhost:8000/api/libraries/rag-agent/documents/2210.03629`: passed with document detail fields, statistics, sections, and chunk preview arrays.
  - `POST http://localhost:8000/api/libraries/rag-agent/documents/frontend-retry-failed:retry`: returned contracted `503 UPSTREAM_ERROR` while Redis/Arq was unavailable.
  - Playwright via system Chrome against `http://127.0.0.1:5174/libraries/rag-agent/docs`: passed seeded list rendering, ready document drawer success path, drawer close, failed-row rendering, retry request dispatch, and retry error toast; observed API statuses `GET 200`, `GET 200`, `POST 503`.
- Remaining backend follow-up:
  - Run Redis/Arq or provide a verification environment where failed-document retry returns the successful `202 { tone, title, detail, action }` path.
  - Update OpenAPI and implement `/api/libraries/{libraryId}/documents:upload` multipart transport, or reject the requested transport with a concrete alternate.

## 2026-05-27 05:32 - Document upload transport request clarified

- Time: 2026-05-27 05:32 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Backend issue #3 remains blocked on undefined `/api/libraries/{libraryId}/documents:upload` upload transport, while the frontend Documents page exposes Upload PDFs and drop-zone entry points.
- Fix status: open
- Frontend SHA before change: `85964db`
- Contract request:
  - Requested upload endpoint: `POST /api/libraries/{libraryId}/documents:upload`.
  - Requested content type: `multipart/form-data`.
  - Requested file field: repeated `files` PDF fields.
  - Requested success response: `202 { tone, title, detail, action? }`, with queued/ingested rows visible through the existing document list endpoint.
  - Requested errors: `400 VALIDATION_ERROR`, `404 LIBRARY_NOT_FOUND`, `409 CONFLICT`, `413 PAYLOAD_TOO_LARGE`, `415 UNSUPPORTED_MEDIA_TYPE`, and `500 INTERNAL_ERROR`.
- Verification:
  - `pnpm typecheck`: passed.
- Backend follow-up:
  - Update OpenAPI and implement the upload endpoint, or reject the requested multipart contract with a concrete alternate transport before implementation.

## 2026-05-27 05:20 - Document retry missing-resource responses verified

- Time: 2026-05-27 05:20 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Backend handed back the document retry mutation fix on `agent/backend-integration`; frontend needed to re-test the previous missing-resource `500` mismatch from API mode and browser origin.
- Fix status: verified for missing-resource retry responses; blocked for successful retry feedback because no live failed document row exists.
- Backend SHA: `835a21d9895634236b900c82b448b10377915864`
- Frontend SHA tested before log update: `2426b8e`
- Verification:
  - `GET http://localhost:8000/healthz`: passed with `{"status":"ok","version":"0.1.0"}`.
  - `GET http://localhost:8000/api/libraries`: passed and returned `frontend-smoke-040442` and `rag-agent`.
  - `GET http://localhost:8000/api/libraries/rag-agent/documents`: passed with `200 { summary, documents: [] }`.
  - `POST http://localhost:8000/api/libraries/rag-agent/documents/not-a-doc:retry`: passed with `404 NOT_FOUND`.
  - `POST http://localhost:8000/api/libraries/missing-library/documents/not-a-doc:retry`: passed with `404 LIBRARY_NOT_FOUND`.
  - Playwright via system Chrome against `http://127.0.0.1:5174/libraries/rag-agent/docs`: passed API-backed empty document state, frontend-origin CORS for document reads, and browser-visible retry error envelopes for missing document and missing library.
- Remaining backend follow-up:
  - Provide a failed document row so frontend can verify the successful `202 { tone, title, detail, action }` retry feedback path.
  - Clarify and implement `/api/libraries/{libraryId}/documents:upload` request content type and file field names.

## 2026-05-27 05:07 - Document read API-mode verification partially blocked

- Time: 2026-05-27 05:07 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Backend handed back document read endpoints for `GET /api/libraries/{libraryId}/documents` and `GET /api/libraries/{libraryId}/documents/{documentId}`. The live backend data currently has empty document lists for available libraries, so the frontend can verify list empty/error behavior but cannot exercise a successful drawer detail response without a real document row.
- Fix status: blocked
- Backend SHA: `835a21d9895634236b900c82b448b10377915864`
- Frontend commit pushed after verification/log update: `a9f7250`
- Frontend fix:
  - Added document list empty, error, and retry states for API-backed document reads.
  - Opened the document drawer during detail loading and added detail error/retry rendering for API-backed failures.
- Verification:
  - `GET http://localhost:8000/healthz`: passed with `{"status":"ok","version":"0.1.0"}`.
  - `GET http://localhost:8000/api/libraries/rag-agent/documents`: passed with `200 { summary, documents: [] }`.
  - `GET http://localhost:8000/api/libraries/frontend-smoke-040442/documents`: passed with `200 { summary, documents: [] }`.
  - `GET http://localhost:8000/api/libraries/missing-library/documents`: passed with `404 LIBRARY_NOT_FOUND`.
  - `GET http://localhost:8000/api/libraries/rag-agent/documents/not-a-doc`: passed with `404 NOT_FOUND`.
  - Playwright via system Chrome against `http://127.0.0.1:5174/libraries/rag-agent/docs`: passed API-backed empty state, list error/retry state, and drawer detail error/retry state; observed API statuses `GET 200` and `GET 404`.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
- Backend follow-up:
  - Provide a backend-backed library with at least one document row, or complete the upload transport contract, so frontend can verify the successful document drawer detail path without test-only data.

## 2026-05-27 05:08 - Document retry missing-resource responses return 500

- Time: 2026-05-27 05:08 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Backend handed back `POST /api/libraries/{libraryId}/documents/{documentId}:retry`, but live API requests for missing library/document resolve the task queue dependency before returning the expected resource validation error.
- Fix status: open
- Backend SHA: `835a21d9895634236b900c82b448b10377915864`
- Frontend commit pushed after verification/log update: `a9f7250`
- Verification:
  - `POST http://localhost:8000/api/libraries/rag-agent/documents/not-a-doc:retry`: expected `404 NOT_FOUND`; actual delayed `500 INTERNAL_ERROR` with `details.type: TimeoutError`, request id `4e6db67589ec46b3bd8e3a5322925f63`.
  - `POST http://localhost:8000/api/libraries/missing-library/documents/not-a-doc:retry`: expected `404 LIBRARY_NOT_FOUND`; actual delayed `500 INTERNAL_ERROR` with `details.type: TimeoutError`, request id `8209b2c0bf36476a84557de198ab7a9f`.
- Backend follow-up:
  - Return resource validation errors before requiring the task queue, or make the task queue dependency available for local frontend verification.
  - Provide a failed document row so frontend can verify the successful `202 { tone, title, detail, action }` retry feedback path.

## 2026-05-27 04:38 - Library API-mode list/create verified

- Time: 2026-05-27 04:38 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Backend handed back `/api/libraries` after fixing valid create behavior to tolerate unavailable Qdrant for the frontend library dashboard/create slice.
- Fix status: verified
- Backend SHA: `7fa6a241965043415482fad09338ba13b18dc25f`
- Frontend SHA tested before log update: `410c02a`
- Verification:
  - `GET http://localhost:8000/healthz`: passed with `{"status":"ok","version":"0.1.0"}`.
  - `GET http://localhost:8000/api/libraries`: passed and returned library summaries.
  - `POST http://localhost:8000/api/libraries` with slug `frontend-smoke-043320`: passed with `201 { library, redirectTo }`.
  - Duplicate `POST http://localhost:8000/api/libraries` with slug `frontend-smoke-043320`: passed with `409 LIBRARY_ALREADY_EXISTS`.
  - Invalid `POST http://localhost:8000/api/libraries` with slug `1bad`: passed with `400 VALIDATION_ERROR`.
  - Playwright via system Chrome against `http://127.0.0.1:5174/libraries`: passed dashboard list load, top bar selector, create modal submit, duplicate error toast, and slug validation disabled submit for `1bad`; observed API statuses `GET 200`, `POST 201`, `POST 409`.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
- Remaining backend follow-up:
  - The next requested slices remain document workspace/detail, document ingestion mutations/upload, chat, review, graph, evaluation, command search, and shell metadata.

## 2026-05-27 04:18 - Library API-mode recheck blocked by unavailable backend

- Time: 2026-05-27 04:18 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Re-read the latest Supervisor Dispatch and frontend/backend issue comments before choosing new work. The latest #2 update already reports the valid `POST /api/libraries` blocker and asks backend to continue; no newer backend handoff exists.
- Fix status: blocked
- Verification:
  - `curl` equivalent via PowerShell `GET http://localhost:8000/healthz`: failed, backend API was not reachable.
  - `GET http://localhost:8000/api/libraries`: failed, backend API was not reachable.
  - `docker compose -f infra/docker-compose.yml ps` from the backend worktree: failed because Docker Desktop engine was not available.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
- Backend follow-up:
  - #2 already contains the non-duplicated backend need: make valid `POST /api/libraries` return `201 { library, redirectTo }` or fail atomically without a partial persisted library.
  - #3 already has `handoff:backend`, so no additional label change was needed.

## 2026-05-27 04:08 - Library API-mode handoff verified with backend create blocker

- Time: 2026-05-27 04:08 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Backend handed off `GET/POST /api/libraries`; frontend needed API-mode validation against the new contract.
- Fix status: blocked
- Frontend fix:
  - Aligned create-library slug validation with the OpenAPI pattern: lowercase, starts with a letter, 3-31 chars, `[a-z0-9-]`.
  - Updated `apiRequest` to surface backend error envelopes as readable messages with `code` and `request_id`.
  - Updated network failures to show the API URL instead of raw `Failed to fetch`.
- Verification:
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
  - `GET http://localhost:8000/api/libraries`: passed and returned library summaries.
  - `POST http://localhost:8000/api/libraries` with invalid slug `1bad`: passed and returned `400 VALIDATION_ERROR`.
  - Browser smoke on `127.0.0.1:5174/libraries`: passed for dashboard error state and contract-aligned slug validation. Port 5173 was already occupied by an unrelated dev server, so 5174 was used; backend CORS blocked API reads from 5174 as expected.
- Backend follow-up:
  - Valid `POST /api/libraries` returned `500 INTERNAL_ERROR` with `details.type: UnexpectedResponse` after Qdrant returned `502 Bad Gateway`.
  - The failed create still appeared in the next `GET /api/libraries`, indicating a partial write before vector index initialization failed.

## 2026-05-27 03:30 - Frontend mock default library removed

- Time: 2026-05-27 03:30 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: Frontend routing, library state, document route fallback, and create-library modal still assumed the mock `graphrag-survey` library exists. OpenAPI still has `paths: {}`, so full real API integration is blocked pending backend contracts.
- Fix status: fixed
- Verification:
  - `pnpm typecheck`: passed.
  - `pnpm build`: passed.

## 2026-05-28 06:00 - Chat API-mode verified

- Time: 2026-05-28 06:00 +08:00
- Agent: Frontend Agent
- Issue: #2
- Cause: `ChatView.vue`, `useChatStore`, `CitationPopover.vue`, and `taskStreamClient.ts` still depended on seeded mock session data and timer-driven streaming in API mode.
- Fix status: fixed
- Frontend fix:
  - Added a typed chat repository for `/api/libraries/{libraryId}/chat/session` and `/api/libraries/{libraryId}/chat/questions`.
  - Replaced the chat stream client with durable SSE parsing for token, evidence, citations, status, and done events.
  - Wired the Pinia chat store to load real sessions, submit questions, maintain pending/streaming/error states, and surface live evidence/citation updates.
  - Updated `ChatView.vue` and `CitationPopover.vue` to render real API-mode loading, empty, pending, error, streaming, and terminal states.
- Verification:
  - `GET http://localhost:8000/healthz`: passed.
  - `GET /api/libraries/rag-agent/chat/session`: passed.
  - `POST /api/libraries/rag-agent/chat/questions`: passed with `202`, `taskId`, `streamUrl`, `userMessage`, `assistantMessage`, and empty initial `evidence`.
  - Browser raw stream fetch on the returned `streamUrl`: passed and contained token, evidence, citations, status, and done frames.
  - Browser smoke on `127.0.0.1:5174`: passed empty session load, pending assistant state, streamed answer rendering, citations/evidence rendering, terminal done state, and missing-library error state.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm typecheck`: passed.
  - `VITE_DATA_SOURCE=api VITE_API_BASE_URL=http://localhost:8000 pnpm build`: passed.
- Backend follow-up:
  - None for the chat slice.
