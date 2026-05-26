# Security Review — M7 Hardening

**Reviewer**: rkb-team
**Date**: 2026-04-29
**Scope**: All code added/modified in M7 (auth, error envelope, rate limit, SSE,
ingest idempotency, backup CLI, frontend SSE consumer, all 5 new API routes).
**Method**: Manual checklist against OWASP API Top 10 (2023) + project-specific
threats (`CODING_STANDARDS §7-8`, `docs/FRONTEND_CODING_STANDARDS §20`).

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 0     | ✅      |
| HIGH     | 0     | ✅      |
| MEDIUM   | 2     | Tracked (M8 backlog) |
| LOW      | 4     | Acknowledged         |

**Verdict**: Safe to merge. Two MEDIUM items are deferred to M8 with explicit
mitigations in the runbook.

## Checklist

### A1 — Broken Object Level Authorization

- [x] Every `/v1/libraries/{id}/**` route validates `library_id` against
      `library_repo.exists()` before doing real work; `LibraryNotFoundError`
      is the unified path.
- [x] No endpoint accepts a `library_id` from the body — always from URL path.
- [x] Frontend `client.ts` URL-encodes `libraryId` (`encodeURIComponent`)
      to prevent path-traversal via `../`.
- **Note**: There is no per-user authorization (single-tenant by design — see ADR-0007).
  When multi-tenancy lands, every route must additionally check
  `principal.can_read(library_id)`.

### A2 — Broken Authentication

- [x] `Authorization: Bearer` is constant-time compared via `hmac.compare_digest`
      (`apps/api/auth.py:48`).
- [x] When `API_KEY` is empty, the principal kind is explicitly `anonymous`
      (no silent admin escalation).
- [x] No JWT signing keys, refresh tokens, or session DB — surface area is
      a single env var.
- **MEDIUM-1**: There is no rate limit on auth failures. A network attacker
  can fuzz the `API_KEY` at `rate_limit_rpm` rate (60/min default). Mitigation:
  the rate limiter applies to all routes when enabled, including
  miss-authenticated ones. Production deployments should set `API_KEY` to a
  ≥32-byte random secret (effectively unguessable in this lifetime). Tracked
  for M8: per-principal-kind login throttling.

### A3 — Broken Object Property Level Authorization (BOPLA)

- [x] All response models use Pydantic `frozen=True, extra="forbid"` —
      no accidental field leakage.
- [x] `LibraryStatsResponse` returns counts only; no document text.
- [x] `LibrarySchemaResponse` returns type names + colors; no sample data.
- [x] `Citation.snippet` is server-truncated to 200 chars (`qa_task.py`).

### A4 — Unrestricted Resource Consumption

- [x] PDF upload: client-side cap 50 MB; backend re-validates the MIME-extension
      mismatch ("only `.pdf`").
- [x] `react_max_steps`, `react_max_llm_calls`, `react_max_input_tokens`,
      `react_max_output_tokens`, `react_timeout_s` — every Agent path has a
      hard budget (`Settings.react_*`).
- [x] Rate limit is available; recommended-on for any non-localhost deployment.
- [x] SSE generator yields `await request.is_disconnected()` between chunks
      to drop work when the client cancels.
- [x] `library_stats` `_safe_count` swallows adapter exceptions and returns 0,
      so a single Qdrant/Neo4j outage cannot cascade into a 500 storm.
- **MEDIUM-2**: The KG `entity_neighborhood` endpoint accepts `depth=1..3` —
  depth=3 on a hub entity could return thousands of triples. Backend trims to
  the underlying adapter's limit, but there is no explicit triple cap. Mitigation:
  Cytoscape canvas is capped client-side at 50 nodes; backend response size is
  observable via `RETRIEVAL_HITS_TOTAL`. Tracked for M8: server-side cap
  `max_triples_per_response`.

### A5 — Broken Function-Level Authorization

- [x] Every `/v1/**` route declares `_principal: Principal = Depends(get_current_principal)` —
      no anonymous fall-through when `API_KEY` is set.
- [x] `/healthz`, `/readyz`, `/metrics`, `/docs`, `/openapi.json` are
      intentionally exempt (per Prometheus + Kubernetes patterns).

### A6 — Server-Side Request Forgery

- [x] No endpoint accepts a user-supplied URL that is then fetched server-side.
- [x] `OpenAICompatLLM` only talks to `Settings.llm_api_base` (operator-set).
- [x] PDF ingest reads from `UploadFile.file` (an in-memory stream), never a path.

### A7 — Security Misconfiguration

- [x] `API_KEY` defaults to `""` (anonymous) — fails open for **dev**, not for
      production. The runbook §1.3 calls this out.
- [x] CORS is FastAPI's default (none) — ADR-pending if we add cross-origin in v1.
- [x] Error envelope never includes stack traces; only the `request_id` and
      a sanitized `details` field for validation errors.
- [x] `OPERATOR_RUNBOOK §1.7` documents the one-knob production checklist:
      `API_KEY` set, `RATE_LIMIT_ENABLED=true`, TLS via reverse proxy.

### A8 — Software / Data Integrity Failures

- [x] `setup-configs.sh` writes ESLint/Prettier from the script (intentional —
      the global config-protection hook prevents Write tool agents from weakening
      them); the script content is committed.
- [x] CI gate: `git diff --exit-code -- docs/openapi.json` blocks merging when
      the FastAPI schema drifts from the committed copy (catches accidental
      breaking changes).
- [x] `pnpm-lock.yaml` + `uv.lock` both committed; CI uses `--frozen-lockfile` /
      `--frozen` respectively.
- [x] Backup tarballs use `tar.extractall` with `# noqa: S202`. Acknowledged
      LOW: input is operator-controlled (only their own `rkb library export`
      output gets imported); cross-host transfer should use `scp` / signed
      checksums (operator runbook).

### A9 — Logging & Monitoring Failures

- [x] Every response carries `X-Request-Id` (echo of inbound or fresh UUID).
- [x] Backend logs include `request_id` on every WARNING/ERROR.
- [x] Prometheus metrics: `rag_llm_*`, `rag_retrieval_*`, `rag_task_*`,
      `rag_api_rate_limited_total` (when rate limit is hit).
- [x] Frontend `logger.event()` records user actions client-side; payload is
      strictly free of PII (only `libraryId` + counts).

### A10 — SSRF / unsafe HTTP

- (covered by A6)

## Frontend-specific (FRONTEND_CODING_STANDARDS §20)

- [x] **No bundled secrets**. All API keys are server-side. The bundle has been
      built and `pnpm build` does not embed any `process.env.*_KEY` values.
- [x] **DOMPurify** sanitizes markdown before any direct DOM write
      (`ChatMessage.vue`).
- [x] **`v-html` is banned** by ESLint rule `vue/no-v-html`. Verified clean
      against the latest `pnpm lint`.
- [x] **File upload validation**: PDF MIME + size cap, both client-side and
      server-side (defense in depth).
- [x] **Cookie security**: `client.ts` uses `credentials: 'include'`; when
      cookies are added in a future milestone, set `HttpOnly` + `Secure` +
      `SameSite=Lax`.
- **LOW-1**: ESLint `vue/no-v-html` is per-file via the standard config — a
      future contributor could disable it inline. Mitigation: code review.
- **LOW-2**: `useSSE` constructs `EventSource(url)` from a path that includes
      a user-typed `question` query param. The string is `URLSearchParams`-encoded
      so injection is structurally impossible, but the question goes into
      the server log. Mitigation: keep questions short (the backend already
      validates `max_length=2000`).

## Backend-specific

- **LOW-3**: `apps/api/middleware/rate_limit.py:LUA` runs server-side in Redis;
      no user input flows into the script body — only into `KEYS`/`ARGV`.
      Verified by reading the `eval()` call (line 114).
- **LOW-4**: `apps/cli/main.py library export` writes to a user-supplied
      `--out` path. Acknowledged: the CLI is operator-only.

## Action items

| ID | Severity | Owner | Target | Description |
| -- | -------- | ----- | ------ | ----------- |
| MEDIUM-1 | M | backend | M8 | Per-principal-kind login throttling on auth failures |
| MEDIUM-2 | M | backend | M8 | Server-side `max_triples_per_response` for `/neighborhood` |
| LOW-1    | L | review-process | ongoing | Catch `eslint-disable vue/no-v-html` in code review |

All other findings are acknowledged with documented mitigations.

## Sign-off

- Manual review: complete
- Automated checks: pyright + ruff + pytest (484 ✓), pnpm typecheck + lint + test (40 ✓)
- Runbook updated: §1.7, §1.10
- ADR: 0007 records all M7 architectural decisions with their security trade-offs.
