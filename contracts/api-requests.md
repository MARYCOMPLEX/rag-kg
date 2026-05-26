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
- Status: requested
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
- Status: requested

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
  - Upload body is unclear: frontend needs the contract to specify whether this is multipart file upload, queued picker initialization, or another transport.
- Required fields:
  - Mutation feedback response: `tone`, `title`, `detail`, optional `action`.
  - `tone` values required by UI: `success`, `info`, `warning`, `danger`.
  - Error contract for invalid file, unsupported file type, duplicate upload, ingestion already running, missing document, missing library, and server failure.
- Acceptance criteria:
  - OpenAPI defines retry and upload request/response schemas.
  - Backend clarifies upload request content type and file field names before frontend removes upload mock behavior.
  - Frontend can show real mutation feedback and preserve traceable error toasts.
- Status: requested

## API Request: Chat question lifecycle and grounded answer stream

- Page: Chat workspace, citation popover, evidence panel.
- Component: `web/src/views/ChatView.vue`, `web/src/stores/chat.ts`, `web/src/components/overlays/CitationPopover.vue`, `web/src/services/api/taskStreamClient.ts`.
- Endpoint:
  - Chat question creation endpoint is missing from OpenAPI.
  - Existing frontend stream helper points to `/v1/tasks/{taskId}/events`.
- Method:
  - Question creation method is unclear.
  - Existing stream helper uses `GET` SSE for `/v1/tasks/{taskId}/events`.
- Params:
  - Question creation must identify library/session context and prompt text.
  - Stream path param: `taskId`.
- Required fields:
  - Message fields required by UI: `id`, `role`, `text`, optional `status`, optional `citations`.
  - Evidence fields required by UI: `id`, `label`, `type`, `title`, `meta`, `score`, `snippet`.
  - SSE event contract for token delivery, citation IDs, terminal status, interruption, unsubstantiated answer, and errors.
  - Error contract for budget exceeded, no evidence, invalid session/library, stream interruption, and server failure.
- Acceptance criteria:
  - OpenAPI defines the chat request endpoint and SSE event payloads.
  - Backend exposes a task/event stream that the frontend can consume without seeded answer tokens.
  - Frontend can replace `web/src/mocks/chat.ts` with repository/service-backed state.
- Status: requested

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
