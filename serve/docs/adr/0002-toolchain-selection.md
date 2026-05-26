# ADR 0002: Toolchain Selection

**Status**: Accepted
**Date**: 2026-04-27
**Deciders**: Project Owner

## Context

We need a Python toolchain that supports strict typing, fast iteration, and CI enforcement for a 21-week project targeting Python 3.12+.

## Decision

| Tool | Choice | Rationale |
|------|--------|-----------|
| Package manager | **uv** | 10-100x faster than pip/poetry; lockfile-first; workspace support |
| Linter + formatter | **ruff** | Replaces flake8, isort, black, pyupgrade in one tool; sub-second on large repos |
| Type checker | **pyright (strict)** | Best Python 3.12+ support (PEP 695 generics, `type` statement); strict mode catches more than mypy default |
| Architecture guard | **tach** | Import-level dependency enforcement; lighter than ArchUnit-style tools |
| Test framework | **pytest** + pytest-asyncio + hypothesis | Industry standard; great async support; property testing for pure functions |
| Web framework | **FastAPI** | Async-native; Pydantic v2 integration; OpenAPI auto-gen; streaming SSE |
| Task queue | **Arq** | Lightweight Redis-based; async-native; sufficient for single-machine workloads |
| ORM | **SQLAlchemy 2.0 async** | Mature; async support; Alembic for migrations |
| CLI | **Typer** | Click-based with type hints; rich output; consistent with Pydantic ecosystem |
| Logging | **structlog** | JSON structured logging; processor pipeline; easy Loki/ES integration |
| Observability | **OpenTelemetry + Langfuse** | OTel for general tracing; Langfuse specifically for LLM trace/cost tracking |
| Data validation | **Pydantic v2** | Fast; frozen models; JSON Schema export; ecosystem alignment |

## Consequences

### Positive

- Single `pyproject.toml` configures ruff, pyright, pytest, coverage — minimal config sprawl.
- All tools have first-class Python 3.12+ support including PEP 695 generics.
- uv's lockfile ensures reproducible installs across dev/CI/prod.

### Negative

- tach is relatively new — may need fallback to `import-linter` if it proves unreliable.
- Arq is less featureful than Celery — may need migration at scale (acceptable per YAGNI).
- pyright strict can be noisy with third-party stubs — mitigated by `reportMissingTypeStubs = "warning"`.

## Alternatives Considered

| Tool | Alternative | Rejected Because |
|------|-------------|-----------------|
| uv | poetry | Slower; no built-in workspace; non-standard lockfile |
| ruff | black + flake8 + isort | Three tools instead of one; slower |
| pyright | mypy | Weaker PEP 695 support; strict mode less comprehensive |
| Arq | Celery | Over-engineered for single-machine; not async-native |
| FastAPI | Django + DRF | Not async-first; heavier ORM coupling |
