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
