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
