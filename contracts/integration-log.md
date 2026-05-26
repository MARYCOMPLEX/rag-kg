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
