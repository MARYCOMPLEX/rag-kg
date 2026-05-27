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
