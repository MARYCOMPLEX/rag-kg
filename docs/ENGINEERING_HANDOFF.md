# Engineering Handoff

Updated: 2026-05-29 Asia/Shanghai

## Current Baseline

The frontend and backend integration slices have been merged into `master`.

- Frontend source branch: `agent/frontend-integration`
- Frontend verified commit: `e984523eec5a9697964460a3d5e4b709db796f79`
- Backend source branch: `agent/backend-integration`
- Backend verified commit: `b7eeeebbc19d036c0a7f938ca75635ab5d4f42bf`
- Final integration issue: <https://github.com/MARYCOMPLEX/rag-kg/issues/4>
- Final verification comment: <https://github.com/MARYCOMPLEX/rag-kg/issues/4#issuecomment-4567426819>

The verified local pairing was:

- Backend API: `http://127.0.0.1:8013`
- Frontend dev server: `http://127.0.0.1:5181`
- Frontend mode: `VITE_DATA_SOURCE=api`
- Frontend API proxy: `VITE_API_PROXY_TARGET=http://127.0.0.1:8013`

## Verified Capabilities

The final integration pass verified real API-mode behavior, not mock or process-local success paths.

- Library list and create contracts.
- Document list/detail surfaces.
- Document retry and invalid upload error envelopes.
- Shell metadata.
- Command/search.
- Knowledge graph workspace.
- Evaluation dashboard.
- Durable chat question lifecycle and SSE stream.
- Review current/create/SSE/regenerate/cancel lifecycle.
- `frontend-smoke-040442` review create after task-store library materialization.
- Vite `/api/*` proxy from frontend dev server to backend.
- Browser smoke for Review and Chat without page errors.
- `pnpm typecheck`.
- `pnpm build`.

## Local Startup

From the repository root:

```powershell
.\scripts\start-local.ps1 -BackendPort 8013 -FrontendPort 5181
```

If Docker infrastructure is not already running:

```powershell
.\scripts\start-local.ps1 -StartInfra -BackendPort 8013 -FrontendPort 5181
```

Run a lightweight smoke check:

```powershell
.\scripts\verify-local.ps1 -BackendPort 8013 -FrontendPort 5181
```

Stop the locally launched API, worker, and frontend:

```powershell
.\scripts\stop-local.ps1
```

To also stop specific stale dev ports:

```powershell
.\scripts\stop-local.ps1 -Ports 8000,8010,8013,5173,5174,5175,5176,5180
```

The stop script only stops explicit local PID files and optional port listeners. It does not stop Docker containers unless you do so separately.

## Collaboration Model

GitHub Issues are the authoritative coordination channel.

- `#1`: Supervisor protocol.
- `#2`: Frontend worker queue.
- `#3`: Backend worker queue.
- `#4`: Integration verification.

Labels drive worker dispatch:

- `handoff:backend`: frontend has a concrete backend/API need.
- `handoff:frontend`: backend is ready for frontend integration or retest.
- `status:blocked`: integration verification is blocked.

The supervisor should dispatch and verify. Frontend and backend workers should own code changes in their respective domains.

## Known Local Residue

These items were intentionally left untouched during final verification:

- Frontend worktree had a pre-existing unstaged edit in `web/src/stores/graph.ts`.
- Backend worktree had local verification data under `serve/data/libraries/frontend-smoke-040442/`.
- Multiple old dev server processes may still exist on previous test ports. Use `scripts/stop-local.ps1 -Ports ...` to clean them.

## Remaining Engineering Work

- Push merged `master` after final local checks.
- Decide whether the pre-existing `web/src/stores/graph.ts` edit should be kept, committed separately, or discarded by its owner.
- Keep runtime data out of Git.
- Resolve the known unrelated backend `make typecheck` failures in `apps/cli/main.py`.
- Convert the local verification flow into CI when the Docker/data-layer requirements are stable.
