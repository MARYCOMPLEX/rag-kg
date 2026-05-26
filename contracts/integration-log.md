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
