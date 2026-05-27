# API Requests

This file is the shared queue for Frontend Agent requests when a page or component requires a backend API that is missing, incomplete, or unclear.

OpenAPI remains the single source of truth. Entries here are requests only; once accepted and implemented, the Backend Agent must update `openapi.yaml`.

## Status Values

| Status | Meaning |
| --- | --- |
| `requested` | Frontend Agent has identified a missing or unclear API. |
| `accepted` | Backend Agent has accepted the request and will update OpenAPI. |
| `blocked` | More information is required before implementation. |
| `implemented` | Backend Agent has implemented the API and updated OpenAPI. |
| `verified` | Frontend Agent has integrated and tested the real API. |

## Request Template

```markdown
## API Request: <short endpoint or capability name>

- Page:
- Component:
- Endpoint:
- Method:
- Params:
- Required fields:
- Acceptance criteria:
- Status: requested
```

## Requests

## API Request: Library list and create

- Page: Library dashboard, create library modal, top bar library selector.
- Component: `web/src/views/LibraryDashboardView.vue`, `web/src/components/overlays/CreateLibraryModal.vue`, `web/src/components/layout/TopBar.vue`.
- Endpoint: `/api/libraries`
- Method: `GET`, `POST`
- Params:
  - `GET`: no frontend query params currently required.
  - `POST` body: `name`, `slug`, `description`, `language`, `template`.
- Required fields:
  - `GET` response: array of library summaries with `id`, `name`, `documentCountLabel`, `chunkCountLabel`, `entityCountLabel`, `activityLabel`, `statusLabel`, `status`, `accent`, optional `featured`.
  - `POST` response: `library` with the same summary shape plus `redirectTo`.
  - Error contract for duplicate slug, invalid slug, validation failure, and server failure.
- Acceptance criteria:
  - OpenAPI defines request, response, and error schemas for both methods.
  - Backend implements list and create without requiring frontend mock data.
  - Frontend can run with `VITE_DATA_SOURCE=api` and `VITE_API_BASE_URL=http://localhost:8000`.
  - Dashboard covers loading, empty, error, and retry states from the real API.
- Status: verified
- Frontend verification note:
  - Time: 2026-05-27 04:38 +08:00
  - Backend SHA: `7fa6a241965043415482fad09338ba13b18dc25f`.
  - Frontend SHA tested before log update: `410c02a`.
  - `GET /api/libraries`: verified with real backend and returned library summaries.
  - Valid `POST /api/libraries` slug `frontend-smoke-043320`: verified `201` with `library.id` matching the slug and `redirectTo` pointing to the library docs route.
  - Duplicate `POST /api/libraries` slug `frontend-smoke-043320`: verified `409 LIBRARY_ALREADY_EXISTS` error envelope.
  - Invalid `POST /api/libraries` slug `1bad`: verified `400 VALIDATION_ERROR` error envelope.
  - Playwright browser smoke at `http://127.0.0.1:5174/libraries`: verified dashboard list load, top bar selector, create modal success path, duplicate error toast, and slug validation disabled submit for `1bad`.
- Frontend verification note:
  - Time: 2026-05-27 04:08 +08:00
  - `GET /api/libraries`: verified with backend branch and returned library summaries.
  - Invalid `POST /api/libraries` slug `1bad`: verified `400 VALIDATION_ERROR` envelope.
  - Valid `POST /api/libraries`: blocked by backend `500 INTERNAL_ERROR` with `details.type: UnexpectedResponse` after Qdrant returned `502 Bad Gateway`.
  - Follow-up `GET /api/libraries` included the failed create slug, so backend should make create atomic or avoid persisting the library before vector initialization succeeds.

## API Request: Library documents workspace and document detail

- Page: Documents workspace and document detail drawer.
- Component: `web/src/views/DocumentsView.vue`, `web/src/components/overlays/DocumentDrawer.vue`, `web/src/services/documents/documentRepository.ts`.
- Endpoint:
  - `/api/libraries/{libraryId}/documents`
  - `/api/libraries/{libraryId}/documents/{documentId}`
- Method: `GET`
- Params:
  - Path params: `libraryId`, `documentId`.
- Required fields:
  - Documents workspace response: `summary` and `documents`.
  - `summary`: `libraryId`, `documentCountLabel`, `chunkCountLabel`, `lastSyncLabel`.
  - Each document: `id`, `libraryId`, `title`, `authors`, `source`, `year`, `status`, `chunks`, `entities`, `ingestedLabel`.
  - `status`: `kind`, `label`, `title`, `message`, `meta`, optional `progress`, optional `progressText`, optional `actionLabel`.
  - Document detail response extends the document shape with `fileFormat`, `fileSizeLabel`, `ingestedAtLabel`, `pageCount`, `selectedPage`, `statistics`, `sections`, `chunksPreview`.
  - `statistics`: `label`, `value`.
  - `sections`: `id`, `orderLabel`, `title`, `pageLabel`.
  - `chunksPreview`: `id`, `locationLabel`, `text`.
  - Error contract for missing library, missing document, unauthorized access, and backend failure.
- Acceptance criteria:
  - OpenAPI defines both document read endpoints and all nested response schemas.
  - Backend response supports empty document lists without treating them as errors.
  - Frontend can remove mock-backed document reads when API mode is enabled.
  - Document list and drawer retain loading, empty, error, and retry behavior against the real API.
- Status: verified
- Frontend verification note:
  - Time: 2026-05-27 05:53 +08:00
  - Backend SHA tested: `ee96a8226e1ace1602e60c48e8582a5f0e74a9af`.
  - Frontend SHA tested before log update: `7ed4092`.
  - `GET /api/libraries/rag-agent/documents`: verified `200` with seeded ready row `2210.03629` and failed row `frontend-retry-failed`.
  - `GET /api/libraries/rag-agent/documents/2210.03629`: verified `200` with the contracted document detail shape and drawer-rendered statistics/actions.
  - Browser smoke at `http://127.0.0.1:5174/libraries/rag-agent/docs`: verified API-backed list rendering, ready document row open, `DocumentDrawer` successful detail rendering, drawer close, failed document row rendering, and failed-row retry UI feedback.
  - `POST /api/libraries/rag-agent/documents/frontend-retry-failed:retry`: verified frontend sends the retry request and shows traceable failure feedback when local Redis/Arq is unavailable; live backend returned `503 UPSTREAM_ERROR`.
  - Successful retry `202 { tone, title, detail, action }` remains pending a local run with Redis/Arq available.
- Frontend verification note:
  - Time: 2026-05-27 05:07 +08:00
  - Backend SHA tested: `835a21d9895634236b900c82b448b10377915864`.
  - Frontend commit pushed after verification/log update: `a9f7250`.
  - `GET /api/libraries/rag-agent/documents`: verified `200` with the contracted `{ summary, documents }` shape and an empty `documents` array.
  - `GET /api/libraries/frontend-smoke-040442/documents`: verified `200` with the contracted empty workspace shape.
  - `GET /api/libraries/missing-library/documents`: verified `404 LIBRARY_NOT_FOUND` error envelope.
  - `GET /api/libraries/rag-agent/documents/not-a-doc`: verified `404 NOT_FOUND` error envelope and frontend drawer error/retry rendering.
  - Playwright browser smoke at `http://127.0.0.1:5174/libraries/rag-agent/docs`: verified API-backed empty state, list error/retry state, and drawer detail error/retry state.
  - Full `verified` status is pending a backend-backed library with at least one document row, or completed upload transport, so the frontend can exercise a successful `GET /api/libraries/{libraryId}/documents/{documentId}` drawer response without test-only data.

## API Request: Document ingestion mutations and upload transport

- Page: Documents workspace and document detail drawer.
- Component: `web/src/views/DocumentsView.vue`, `web/src/components/overlays/DocumentDrawer.vue`, `web/src/services/documents/documentRepository.ts`.
- Endpoint:
  - `/api/libraries/{libraryId}/documents/{documentId}:retry`
  - `/api/libraries/{libraryId}/documents:upload`
- Method: `POST`
- Params:
  - Retry path params: `libraryId`, `documentId`.
  - Upload path param: `libraryId`.
  - Upload request body requested by frontend: `multipart/form-data`.
  - Upload file field requested by frontend: one or more PDF files under repeated field name `files`.
  - Upload request does not require a JSON body in the first slice; `libraryId` path param supplies the library context.
  - Frontend will update `documentRepository.queueUpload()` to send `FormData` after OpenAPI defines this transport and will refresh the document list after successful feedback.
- Required fields:
  - Mutation feedback response: `tone`, `title`, `detail`, optional `action`.
  - `tone` values required by UI: `success`, `info`, `warning`, `danger`.
  - Upload success response requested by frontend: `202` mutation feedback with `tone`, `title`, `detail`, optional `action`.
  - Retry success response expected from the existing backend handoff: `202` mutation feedback with `tone`, `title`, `detail`, optional `action`.
  - Error contract for missing files, invalid multipart body, invalid file, unsupported file type, payload too large, duplicate upload, ingestion already running, missing document, missing library, and server failure.
  - Error status expectations: `400 VALIDATION_ERROR` for missing files or invalid multipart body, `404 LIBRARY_NOT_FOUND` for unknown library, `404 NOT_FOUND` for unknown retry document, `409 CONFLICT` for duplicate upload or ingestion already running, `413 PAYLOAD_TOO_LARGE` for oversized uploads, `415 UNSUPPORTED_MEDIA_TYPE` for non-PDF files, and `500 INTERNAL_ERROR` for server failure.
- Acceptance criteria:
  - OpenAPI defines retry and upload request/response schemas.
  - OpenAPI defines `/api/libraries/{libraryId}/documents:upload` as `multipart/form-data` with repeated `files` PDF upload fields, or explicitly rejects this frontend request with an alternate contract before implementation.
  - Frontend can show real mutation feedback and preserve traceable error toasts.
- Status: requested
- Frontend clarification note:
  - Time: 2026-05-27 05:32 +08:00
  - Issue: #2
  - Frontend route and components: `/libraries/:libraryId/docs`, `web/src/views/DocumentsView.vue`, `web/src/stores/documents.ts`, `web/src/services/documents/documentRepository.ts`.
  - Current frontend behavior: Upload buttons and the drop zone call `queueUpload()`; API mode currently sends `POST /api/libraries/{libraryId}/documents:upload` with no body because the upload transport is not yet in OpenAPI.
  - Requested backend contract: accept `multipart/form-data` with one or more PDF files in repeated field `files`, return `202 { tone, title, detail, action? }`, and expose the queued/ingested document rows through the existing document list endpoint.
  - Frontend follow-up after OpenAPI update: add the file input/drop handling, send `FormData` without JSON `Content-Type`, refresh the document list after success, and verify browser upload feedback in API mode.
- Frontend verification note:
  - Time: 2026-05-27 05:20 +08:00
  - Backend SHA tested: `835a21d9895634236b900c82b448b10377915864`.
  - Frontend SHA tested before log update: `2426b8e`.
  - `POST /api/libraries/rag-agent/documents/not-a-doc:retry`: verified `404 NOT_FOUND` error envelope, request id `fc17d253cd3d4023ba2a18f71f3635eb`.
  - `POST /api/libraries/missing-library/documents/not-a-doc:retry`: verified `404 LIBRARY_NOT_FOUND` error envelope, request id `3e483f4dbe75455299a72b37389e90e5`.
  - Playwright browser smoke at `http://127.0.0.1:5174/libraries/rag-agent/docs`: verified API-backed empty document state, frontend-origin CORS for document reads, and browser-visible retry error envelopes for missing document and missing library.
  - A successful `202 { tone, title, detail, action }` retry feedback path is still blocked because the live backend document lists are empty and no failed document row is available.
  - Upload remains blocked because `/api/libraries/{libraryId}/documents:upload` request content type and file field names are still undefined.
- Frontend verification note:
  - Time: 2026-05-27 05:08 +08:00
  - Backend SHA tested: `835a21d9895634236b900c82b448b10377915864`.
  - `POST /api/libraries/rag-agent/documents/not-a-doc:retry`: expected `404 NOT_FOUND` error envelope for a missing document; actual response was delayed and returned `500 INTERNAL_ERROR` with `details.type: TimeoutError`, request id `4e6db67589ec46b3bd8e3a5322925f63`.
  - `POST /api/libraries/missing-library/documents/not-a-doc:retry`: expected `404 LIBRARY_NOT_FOUND`; actual response was delayed and returned `500 INTERNAL_ERROR` with `details.type: TimeoutError`, request id `8209b2c0bf36476a84557de198ab7a9f`.
  - Impacted frontend surfaces: `web/src/services/documents/documentRepository.ts`, `web/src/views/DocumentsView.vue`, and `web/src/components/overlays/DocumentDrawer.vue`.
  - A successful retry feedback path still needs a backend-backed failed document row; current live libraries returned empty document lists.
  - Upload remains blocked because `/api/libraries/{libraryId}/documents:upload` request content type and file field names are still undefined.

## API Request: Chat question lifecycle and grounded answer stream

- Page: Chat workspace, citation popover, evidence panel.
- Component: `web/src/views/ChatView.vue`, `web/src/stores/chat.ts`, `web/src/components/overlays/CitationPopover.vue`, `web/src/services/api/taskStreamClient.ts`.
- Endpoint:
  - Requested current session endpoint: `/api/libraries/{libraryId}/chat/session`
  - Requested question creation endpoint: `/api/libraries/{libraryId}/chat/questions`
  - Existing frontend stream helper points to `/v1/tasks/{taskId}/events`; backend can either contract that path or provide a replacement `streamUrl` returned by the question creation endpoint.
- Method:
  - `GET` current session.
  - `POST` question creation.
  - Existing stream helper uses `GET` SSE for `/v1/tasks/{taskId}/events`.
- Params:
  - Current session path param: `libraryId`.
  - Question creation path param: `libraryId`.
  - Question creation body requested by frontend: `question`, optional `sessionId`, optional `context`.
  - `context` may contain selected `evidenceIds` and `entityIds` when the user cites graph/evidence context from another screen.
  - Stream path param: `taskId`.
- Required fields:
  - Current session response: `sessionId`, `title`, `createdAtLabel`, `messages`, `evidence`.
  - Question creation success response requested by frontend: `202` with `taskId`, `streamUrl`, `userMessage`, `assistantMessage`, and optional initial `evidence`.
  - Message fields required by UI: `id`, `role`, `text`, optional `status`, optional `citations`.
  - Message `role` values required by UI: `user`, `assistant`.
  - Message `status` values required by UI: `idle`, `streaming`, `done`, `interrupted`, `unsubstantiated`.
  - Evidence fields required by UI: `id`, `label`, `type`, `title`, `meta`, `score`, `snippet`.
  - SSE events required by UI:
    - `token`: plain text token or JSON `{ token }`.
    - `citations`: JSON array of citation IDs matching `evidence[].id`.
    - `evidence`: JSON array of evidence records if evidence arrives after question creation.
    - `status`: JSON `{ status }` using the message status values above.
    - `done`: terminal event after final text/citations are available.
    - `error`: backend error envelope or JSON `{ code, message, request_id }`.
  - Error contract for budget exceeded, no evidence, invalid session/library, stream interruption, task not found, unauthorized access, and server failure.
- Acceptance criteria:
  - OpenAPI defines current session, question creation, and SSE event payloads.
  - Backend exposes a task/event stream that the frontend can consume without seeded messages, evidence, or answer tokens.
  - Empty sessions return `200` with an empty `messages` array and an empty `evidence` array.
  - Question creation returns a pending assistant message immediately so the frontend can render loading/streaming state before the first token.
  - Frontend can replace `web/src/mocks/chat.ts` with repository/service-backed state.
- Status: requested
- Frontend clarification note:
  - Time: 2026-05-27 10:32 +08:00
  - Issue: #2
  - Current frontend behavior: `web/src/stores/chat.ts` seeds `messages`, `evidence`, and `groundedAnswerTokens` from `web/src/mocks/chat.ts`, then simulates streaming with `window.setInterval`.
  - Requested backend contract: provide a current session loader plus a question creation endpoint that returns a stream task and message placeholders; define the SSE event payloads before frontend removes mock answer tokens.
  - Frontend follow-up after OpenAPI update: add a chat repository, load session state through the store, connect `sendQuestion()` to the real creation endpoint, and replace timer-based token generation with `taskStreamClient`.

## API Request: Review generation run lifecycle

- Page: Review workspace.
- Component: `web/src/views/ReviewView.vue`, `web/src/stores/review.ts`, `web/src/components/review/*`.
- Endpoint:
  - Review run creation/current run endpoint is missing from OpenAPI.
  - Review section regeneration endpoint is missing from OpenAPI.
  - Existing UI copy references task cancellation through `/v1/tasks/{taskId}/cancel`.
  - Existing stream helper points to `/v1/tasks/{taskId}/events`.
- Method:
  - Start/current run and regenerate methods are unclear.
  - Cancellation is expected to be `POST` if `/v1/tasks/{taskId}/cancel` is accepted.
  - Existing stream helper uses `GET` SSE for `/v1/tasks/{taskId}/events`.
- Params:
  - Needs library ID, review task/run ID, section ID or label for regeneration, and task ID for cancellation/streaming.
- Required fields:
  - Pipeline step fields: `id`, `label`, `status`, optional `details`.
  - Pipeline detail fields: `label`, `status`.
  - Citation fields: `id`, `type`, `author`, optional `isNew`.
  - Run stat fields: `label`, `value`, optional `accent`.
  - Draft stream fields and event ordering need contract definition.
  - Error contract for missing run, stale task, cancellation conflict, regeneration validation failure, and server failure.
- Acceptance criteria:
  - OpenAPI defines review run, regenerate, cancel, and SSE contracts.
  - Backend provides current run state so the review page can load without mock timers.
  - Frontend can replace `web/src/mocks/review.ts` with service-backed state and preserve cancel/regenerate feedback.
- Status: requested

## API Request: Knowledge graph workspace and entity detail

- Page: Knowledge Graph workspace and entity drawer.
- Component: `web/src/views/GraphView.vue`, `web/src/components/graph/GraphEntityDrawer.vue`, `web/src/stores/graph.ts`.
- Endpoint:
  - Graph workspace endpoint is missing from OpenAPI.
  - Entity detail endpoint is missing from OpenAPI.
  - Entity filter metadata endpoint is missing from OpenAPI.
- Method: `GET`
- Params:
  - Needs library ID.
  - Graph filters required by UI: entity type selection and minimum confidence.
  - Entity detail requires entity ID or stable entity key.
- Required fields:
  - Entity type filters: `label`, `count`, `checked`, `tone`.
  - Graph canvas data needs contracted nodes and edges before frontend can replace hardcoded SVG nodes.
  - Entity detail fields currently displayed: entity label/name, kind, stable ID, aliases, summary, degree, confidence, incoming, mentions, mention trend, co-occurring entities, evidence count.
  - Error contract for missing library, missing entity, invalid filter, and large graph fallback behavior.
- Acceptance criteria:
  - OpenAPI defines graph summary, filters, canvas data, and entity detail schemas.
  - Backend supports empty graphs and large graphs predictably.
  - Frontend can replace `web/src/mocks/graph.ts` and hardcoded entity drawer values without guessing shape.
- Status: requested

## API Request: Evaluation dashboard data

- Page: Evaluation dashboard.
- Component: `web/src/views/EvaluationView.vue`, `web/src/components/evaluation/*`, `web/src/stores/evaluation.ts`.
- Endpoint: Evaluation dashboard endpoint is missing from OpenAPI.
- Method: `GET`
- Params:
  - Needs library ID.
  - UI filter dimensions currently shown: dataset/task family and time range.
- Required fields:
  - KPI fields: `title`, `value`, `threshold`, `tone`, `points`, optional `icon`.
  - Trend fields: day labels plus metric arrays for EM@1, faithfulness, citation, and latency p95.
  - Trend legend fields used by UI.
  - Failure case fields: `id`, `dataset`, `question`, `failure`, `tone`, `em`, `faithfulness`, `citation`, `latency`.
  - Error contract for missing library, invalid date range/filter, no evaluation runs, and server failure.
- Acceptance criteria:
  - OpenAPI defines the evaluation dashboard request and response schemas.
  - Backend supports empty KPI/trend/failure-case states.
  - Frontend can replace `web/src/mocks/evaluation.ts` with service-backed state.
- Status: requested

## API Request: Command palette search and navigation metadata

- Page: Global command palette and application shell.
- Component: `web/src/components/overlays/CommandPalette.vue`, `web/src/stores/search.ts`, `web/src/stores/ui.ts`.
- Endpoint:
  - Command/search endpoint is missing from OpenAPI.
  - Navigation/library stat/session metadata endpoint is missing from OpenAPI.
- Method: `GET`
- Params:
  - Search query.
  - Library ID or active workspace context.
  - Optional result type scope for commands, documents, entities, libraries, and actions.
- Required fields:
  - Command/search result fields: `label`, `meta`, `screen`, optional `icon`, optional `shortcut`, optional `tone`.
  - Navigation item fields: `key`, `id`, `label`, `icon`, `activeOn`.
  - Recent session fields: `title`, `time`, optional `active`.
  - Library stat fields: `label`, `value`.
  - Error contract for invalid query/scope and server failure.
- Acceptance criteria:
  - OpenAPI defines search and shell metadata contracts or explicitly marks shell metadata as frontend-static.
  - Backend supports empty search results without errors.
  - Frontend can replace `web/src/mocks/search.ts` and clarify which `web/src/mocks/navigation.ts` data should remain static.
- Status: requested

## Frontend Audit Note: OpenAPI still blocks real API integration

- Time: 2026-05-27 03:30 +08:00
- Issue: #2
- Finding:
  - `contracts/openapi.yaml` currently has `paths: {}` and no schemas.
  - Existing frontend HTTP repositories already target `/api/libraries`, `/api/libraries/{libraryId}/documents`, `/api/libraries/{libraryId}/documents/{documentId}`, `/api/libraries/{libraryId}/documents/{documentId}:retry`, and `/api/libraries/{libraryId}/documents:upload`, but these endpoints are not yet contracted.
  - Chat, review, graph, evaluation, command search, and shell metadata are still mock-backed because no OpenAPI contract exists for their request/response fields or error shapes.
- Frontend change made:
  - Removed hardcoded `graphrag-survey` as the default active library and root redirect target.
  - Added library dashboard loading/empty/error/retry behavior so API mode can surface real failures or empty responses.
  - Removed fake create-library slug availability for `graphrag-survey`; slug validity is now local format validation only, with duplicate/availability left to the backend contract.
- Needs backend:
  - Add OpenAPI paths/schemas for the requested endpoints above before frontend can remove remaining mock-backed stores without guessing fields.
- Status: requested
