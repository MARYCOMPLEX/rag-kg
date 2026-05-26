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
