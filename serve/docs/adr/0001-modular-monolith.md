# ADR 0001: Modular Monolith Architecture

**Status**: Accepted
**Date**: 2026-04-27
**Deciders**: Project Owner

## Context

We are building a research-oriented knowledge base + LLM Agent system (RAG-KG Copilot) from scratch. The system needs to span ingestion, structuring (KG), multi-index retrieval, agent orchestration, and evaluation — touching 6+ storage backends.

Two main architectural options exist:

1. **Microservices from day one** — each concern as an independent deployable.
2. **Modular monolith** — single deployable with strict internal module boundaries that can be split later.

The team is one person. The product scope is research-grade, not enterprise SaaS. Iteration speed matters more than independent scaling of subsystems.

## Decision

We adopt a **modular monolith** architecture:

- All code lives in one repository under `packages/` (domain modules) and `apps/` (entry points).
- Each package has a well-defined `protocols.py` (interface) and `service.py` (facade).
- Dependencies flow strictly one-way: `apps → orchestration → retrieval → {indexing, structuring, ingestion} → {llm, embedding} → eventbus → core`.
- `tach` enforces dependency direction at CI time.
- Three processes: API server, async worker, and LLM backend — all from the same codebase.

## Consequences

### Positive

- **Fast iteration**: one `uv sync`, one test suite, one deploy.
- **Refactoring safety**: rename/move across modules in a single commit.
- **Future-proof**: each package is designed to be extractable as a microservice when scaling demands it (see `CODING_STANDARDS §21`).

### Negative

- All modules share one Python process — a CPU-heavy embedding job can starve the API. Mitigated by the worker process split.
- Must be disciplined about import boundaries; without tach enforcement, the monolith degrades into a ball of mud.

### Risks

- If the project grows to 2+ parallel dev tracks, module boundaries may not suffice — trigger for microservice extraction (see `CODING_STANDARDS §21`).

## Alternatives Considered

| Option | Rejected Because |
|--------|-----------------|
| Microservices | Operational overhead too high for solo dev; premature optimization |
| Django monolith | Not async-native; FastAPI better fits streaming LLM responses |
| No structure (scripts) | Unacceptable for a 21-week project with 9 milestones |
