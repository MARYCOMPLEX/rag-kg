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
