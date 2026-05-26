# Changelog

All notable changes to RAG-KG Copilot are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added — M7 Hardening (2026-04-29)

#### API surface
- `GET /v1/libraries/{id}/stats` — library counts (documents/chunks/entities/triples/communities)
- `GET /v1/libraries/{id}/schema` — entity + relation type list with deterministic colors
- `GET /v1/libraries/{id}/qa/stream` — SSE QA endpoint (events: `meta` → `token*` → `citations` → `done` / `error`)
- `POST /v1/libraries/{id}/review` — generate literature review (wraps `ReviewGenerationTask`)
- `POST /v1/libraries/{id}/hypothesis` — generate hypotheses (wraps `HypothesisTask`)
- `?force=true` query param on ingest to bypass SHA-256 idempotency

#### Cross-cutting middleware
- **Unified error envelope**: every non-2xx response returns `{code, message, request_id, details?}`. Wire-stable `ErrorCode` enum (`packages/core/api_errors.py`).
- **Request-id propagation**: ASGI middleware reads/generates `X-Request-Id` and echoes it on every response.
- **Bearer-token auth** (optional): set `API_KEY` env var to require `Authorization: Bearer <token>`; empty string keeps anonymous (dev) mode.
- **Rate limit** (optional): Redis-backed token bucket per (principal, route); fail-open if Redis is down. Disabled by default.

#### Ingestion
- **Idempotent ingest**: SHA-256 → sqlite state store; same file twice = no work
- CLI `rkb ingest --force / --report-only` flags
- API `?force=true` query param
- New `packages/ingestion/{state,idempotency}.py` modules

#### Per-Library backup
- `rkb library export <id> --out <dir>` — bundles meta + corpus + qdrant scroll + graph + community summaries + ingest state into a `<id>.tar.gz`
- `rkb library import <archive> --as <new-id>` — restores meta + corpus (re-run `ingest` to repopulate indices; embedding cache hits 100%)
- `scripts/snapshot_all.sh` — cron-friendly global snapshot with `RETENTION_DAYS` (default 30)

#### Frontend (`apps/web`)
- Vue 3.5 + Vite 5 + TypeScript-strict scaffold (Pinia, Vue Router, Naive UI, UnoCSS, vue-i18n, Cytoscape.js, ECharts, MSW)
- 5 route-level views: Home / Libraries / QA / Upload / KG / Stats / Review / Hypothesis (Library-scoped routes carry `:libraryId`)
- `useSSE` + `useChunkedReveal` composables; `qaStore.submitStream` uses the new SSE endpoint
- `KGBrowser` consumes `/schema` for type colors (with fallback palette)
- 5 Playwright E2E specs covering the PRD §14.4 user flows
- `pnpm i18n:check` script — enforces zh-CN / en-US key parity (CI-gated)
- `pnpm a11y:check` script — axe-core smoke against the 5 main routes

#### Docs
- `docs/USER_GUIDE.md` — researcher-facing 15-minute onboarding
- `docs/OPERATOR_RUNBOOK.md` — operator runbook with 10 common-failure recipes
- `docs/API_REFERENCE.md` — hand-written summary backed by `docs/openapi.json` (auto-exported by `scripts/export_openapi.py`)
- `docs/examples/{01,02,03}.ipynb` — create-library / ingest / qa-with-kg
- `docs/FRONTEND_CODING_STANDARDS.md` — full style guide for `apps/web`
- ADR-0007: M7 architecture decisions (error envelope, auth, SSE, idempotency, backup)

#### CI
- Backend: ruff / pyright / pytest (unit + integration) / OpenAPI sync check
- Frontend: typecheck / lint / format / i18n-parity / vitest with coverage / build
- Healthz smoke job

### Changed
- All `/v1/**` routes now apply `Depends(get_current_principal)` (no-op when `API_KEY` empty)
- `LibraryNotFoundError` is raised instead of `HTTPException(404)` everywhere; the unified handler maps to envelope
- `apps/api/main.py` switched to `create_app()` factory + module-level route handlers (works around pyright `reportUnusedFunction`)
- `Settings`: added `api_key`, `rate_limit_*`, `ingest_state_dir` fields

### Fixed
- 7+ pre-existing TypeScript-strict errors in agent-generated frontend code (signal types, exact-optional props, readonly-array variance, `paths`→`pick` for pinia-plugin-persistedstate v4)
- 4 frontend test failures (DOM selector flakiness + off-by-one assertion in chunked-reveal)

### Deprecated
- (none)

### Removed
- The pre-M7 `LibraryAlreadyExistsError`-as-HTTPException-409 hand-mapping in `libraries.py` (now handled by the unified exception_handler).

### Security
- `API_KEY` constant-time comparison via `hmac.compare_digest`
- `credentials: 'include'` on the frontend `fetch` wrapper for cookie auth (when added)
- DOMPurify guards `markdown-it` output before any `innerHTML` write
- Markdown rendering uses `h()` render function — `v-html` is banned by ESLint
- Documents are PDF-only; size capped client-side at 50 MB; backend re-validates

## Earlier milestones

See `docs/PRD.md §6` for the M0–M6 milestone summary; per-milestone commits
are recorded in `git log`.
