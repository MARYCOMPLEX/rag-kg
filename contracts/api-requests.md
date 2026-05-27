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
- Status: implemented
- Backend seed note:
  - Time: 2026-05-27 05:41 +08:00
  - Added `serve/scripts/seed_frontend_documents.py` and ran it for `rag-agent`.
  - The local backend ingest state now has one ready document (`2210.03629`) for successful drawer verification and one failed document (`frontend-retry-failed`) for retry-state UI verification.
  - OpenAPI was unchanged because the existing document list/detail response contract did not change.

## API Request: Document ingestion retry mutation

- Page: Documents workspace and document detail drawer.
- Component: `web/src/views/DocumentsView.vue`, `web/src/components/overlays/DocumentDrawer.vue`, `web/src/services/documents/documentRepository.ts`.
- Endpoint: `/api/libraries/{libraryId}/documents/{documentId}:retry`
- Method: `POST`
- Params:
  - Path params: `libraryId`, `documentId`.
  - Request body: none.
- Required fields:
  - Mutation feedback response: `tone`, `title`, `detail`, optional `action`.
  - `tone` values required by UI: `success`, `info`, `warning`, `danger`.
  - Error contract for missing library, missing document, ingestion already running, retry conflict, queue rejection, and server failure.
- Acceptance criteria:
  - OpenAPI defines the retry request, response, and error schemas.
  - Backend queues an ingestion retry for failed documents without changing existing `/v1/libraries/{library_id}/docs/{doc_id}/retry` behavior.
  - Frontend can show real mutation feedback and preserve traceable error toasts.
- Status: implemented
- Backend fix note:
  - Time: 2026-05-27 05:18 +08:00
  - `POST /api/libraries/{libraryId}/documents/{documentId}:retry` now validates missing library and missing document before initializing the task queue, so Redis/Arq availability cannot mask contracted `404 LIBRARY_NOT_FOUND` or `404 NOT_FOUND` error envelopes.
  - OpenAPI was already correct for these responses; no contract shape change was needed.
- Backend fix note:
  - Time: 2026-05-27 05:41 +08:00
  - If Redis/Arq is unavailable while retrying a real failed document, `/api/libraries/{libraryId}/documents/{documentId}:retry` now returns the contracted `503 UPSTREAM_ERROR` envelope instead of `500 INTERNAL_ERROR`.
  - Successful `202 { tone, title, detail, action }` retry still requires the task queue dependencies to be running.

## API Request: Document upload transport

- Page: Documents workspace.
- Component: `web/src/views/DocumentsView.vue`, `web/src/services/documents/documentRepository.ts`.
- Endpoint: `/api/libraries/{libraryId}/documents:upload`
- Method: `POST`
- Params:
  - Path param: `libraryId`.
  - Upload body: `multipart/form-data`.
  - File field: one or more PDF files under repeated field name `files`.
  - No JSON request body is required in the first slice.
- Required fields:
  - Mutation feedback response: `tone`, `title`, `detail`, optional `action`.
  - Error contract for missing files, invalid file, unsupported file type, payload too large, duplicate upload, ingestion already running, missing library, queue unavailable, and server failure.
- Acceptance criteria:
  - OpenAPI defines upload content type, file field names, response schema, and error responses.
  - Backend queues accepted PDFs for ingestion and exposes pending/queued rows through `GET /api/libraries/{libraryId}/documents`.
  - Frontend can remove upload mock behavior without guessing transport details.
- Status: implemented
- Backend implementation note:
  - Time: 2026-05-27 13:16 +08:00
  - Accepted the frontend-requested multipart upload contract.
  - `POST /api/libraries/{libraryId}/documents:upload` now accepts repeated `files` PDF fields, stages uploaded PDFs under backend `data/uploads/{libraryId}/`, enqueues `ingest_document` tasks, and writes pending ingest-state rows visible in the document list endpoint.
  - Missing files return `400 VALIDATION_ERROR`; missing library returns `404 LIBRARY_NOT_FOUND`; duplicate or already-pending uploads return `409 CONFLICT`; oversized PDFs return `413 PAYLOAD_TOO_LARGE`; non-PDF uploads return `415 UNSUPPORTED_MEDIA_TYPE`; queue dependency failures return `503 UPSTREAM_ERROR`.

## API Request: Command palette search and navigation metadata

- Page: Global command palette and application shell.
- Component: `web/src/components/overlays/CommandPalette.vue`, `web/src/components/layout/SideNav.vue`, `web/src/components/layout/TopBar.vue`, `web/src/stores/search.ts`, `web/src/stores/ui.ts`.
- Endpoint:
  - `/api/libraries/{libraryId}/search`
  - `/api/libraries/{libraryId}/shell/metadata`
- Method: `GET`
- Params:
  - Search path param: `libraryId`.
  - Search query params: `q`, optional `scope` as comma-separated `documents`, `entities`, `libraries`, `actions`, optional `limit`.
  - Shell metadata path param: `libraryId`.
- Required fields:
  - Search response: `query`, `results`.
  - Search result fields: `id`, `type`, `label`, `meta`, `screen`, optional `icon`, optional `shortcut`, optional `tone`, optional `target`.
  - `type` values: `document`, `entity`, `library`, `action`.
  - `screen` values: `dashboard`, `chat`, `graph`, `docs`, `review`, `eval`.
  - `target` optional fields: `libraryId`, `documentId`, `entityId`, `sessionId`, `reviewRunId`, `query`.
  - Shell metadata response: `recentSessions`, `libraryStats`, optional `notifications`, optional `profile`.
  - Recent session fields: `id`, `title`, `time`, `screen`, optional `active`, optional `target`.
  - Library stat fields: `label`, `value`.
  - Notifications fields: `activeBackgroundStreams`, optional `label`.
  - Profile fields: `initials`, `displayName`, optional `planLabel`.
- Acceptance criteria:
  - OpenAPI defines search and dynamic shell metadata contracts.
  - Backend supports blank or one-character search queries with `200 { query, results: [] }`.
  - Backend supports empty recent session arrays and real library statistics without seeded/fake values.
  - Frontend can replace `web/src/mocks/search.ts` and dynamic `recentSessions`/`libraryStats` placeholders.
- Status: implemented
- Backend implementation note:
  - Time: 2026-05-27 13:52 +08:00
  - Added `/api/libraries/{libraryId}/search` backed by the existing cross-resource search service and mapped backend hits into frontend command result fields.
  - Added `/api/libraries/{libraryId}/shell/metadata` with recent chat sessions from the context store and document/chunk stats from ingest state.
  - Missing library returns `404 LIBRARY_NOT_FOUND`; invalid search scope returns `400 VALIDATION_ERROR`; invalid limit returns `422 VALIDATION_ERROR`.

## API Request: Knowledge graph workspace and entity detail

- Page: Knowledge Graph workspace and entity drawer.
- Component: `web/src/views/GraphView.vue`, `web/src/components/graph/GraphEntityDrawer.vue`, `web/src/stores/graph.ts`.
- Endpoint:
  - `/api/libraries/{libraryId}/graph`
  - `/api/libraries/{libraryId}/graph/entities/{entityId}`
- Method: `GET`
- Params:
  - Workspace path param: `libraryId`.
  - Workspace query params: optional `entityTypes` comma-separated entity type keys, optional `minConfidence` from `0` to `1`, optional `limit`, optional `layout` using `static`, `force`, or `webgl`.
  - Entity detail path params: `libraryId`, `entityId`.
- Required fields:
  - Workspace response: `filters`, `canvas`, and `summary`.
  - `filters.entityTypes`: `key`, `label`, `count`, `checked`, `tone`.
  - `filters.minConfidence`: current numeric confidence threshold.
  - `canvas.nodes`: `id`, `label`, `type`, `tone`, `x`, `y`, `radius`, optional `selected`, `faded`, `confidence`, `degree`, `evidenceCount`.
  - `canvas.edges`: `id`, `source`, `target`, optional `label`, `weight`, `confidence`, `muted`, `directed`.
  - `canvas.layout`: `static`, `force`, or `webgl`.
  - `canvas.largeGraph`: boolean indicating whether the frontend should simplify rendering.
  - `summary`: `entityCountLabel`, `tripleCountLabel`, `confidenceLabel`, optional `warningLabel`.
  - Entity detail response: `id`, `label`, `kind`, `stableId`, `aliases`, `summary`, `degree`, `confidence`, `incoming`, `mentions`, `evidenceCount`, `mentionsTrend`, `coOccurring`.
- Acceptance criteria:
  - OpenAPI defines graph workspace and entity detail schemas with all nested node, edge, filter, summary, trend, and co-occurrence fields.
  - Backend supports empty graphs with `200` and empty `canvas.nodes` / `canvas.edges` arrays.
  - Backend uses real KG triples/entities when available and does not seed fake graph content for the UI.
  - Frontend can replace graph mocks after API-mode verification.
- Status: implemented
- Backend implementation note:
  - Time: 2026-05-27 14:34 +08:00
  - Added `/api/libraries/{libraryId}/graph` backed by KG triples/entities when available. Empty or unavailable graph reads return a contracted empty workspace with real zero labels.
  - Added `/api/libraries/{libraryId}/graph/entities/{entityId}` for entity drawer details derived from stored entity metadata and incident triples.
  - Missing library returns `404 LIBRARY_NOT_FOUND`; missing entity returns `404 NOT_FOUND`; invalid entity type filter or unsupported layout returns `400 VALIDATION_ERROR`; invalid numeric query bounds return `422 VALIDATION_ERROR`.
