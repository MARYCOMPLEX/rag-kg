# ADR 0003: Library as Data Partition (Not Architecture Layer)

**Status**: Accepted
**Date**: 2026-04-27
**Deciders**: Project Owner

## Context

The system supports multiple independent research corpora (Libraries). Each Library represents one research domain — the user manually collects papers for a topic and ingests them into a Library. Queries are always scoped to a single Library.

The key design question: **should Library be a module/package in the architecture, or a data dimension?**

## Decision

**Library is a data partition key, not an architecture layer.**

Concretely:

1. **No `packages/library/`** — Library does not get its own package.
2. **`library_id` is a field**, not a module boundary. Every cross-library domain model (`Document`, `Chunk`, `Entity`, `Triple`, etc.) has `library_id` as its **first field**.
3. **Protocol methods** that touch data take `library_id: str` as their first positional parameter.
4. **Physical isolation** is handled by storage adapters, not by architecture:

| Storage Backend | Isolation Strategy | Naming Convention |
|----------------|-------------------|-------------------|
| Qdrant | One collection per Library | `chunks_<library_id>` |
| Neo4j | One composite database per Library | `lib_<library_id>` |
| PostgreSQL | `library_id` column + composite index | `(library_id, *)` |
| OpenSearch | One index per Library | `bm25_<library_id>` |
| MinIO / S3 | Prefix isolation | `s3://kb/<library_id>/...` |
| Redis | Key prefix | `<library_id>:...` |

5. **Lifecycle helpers** (`init_library` / `purge_library`) live in `packages/core/library_admin.py` — a thin orchestration file, not a service or package.
6. **No cross-Library queries** — Protocol methods never accept `library_ids: list[str]`. Multi-library comparison is done at the CLI/task level by issuing multiple single-library calls.

## Consequences

### Positive

- **Simplicity**: No architectural overhead for what is fundamentally a data concern.
- **Clean deletion**: Purging a Library = dropping collections/databases/prefixes. No orphan cleanup.
- **Natural sharding**: When scaling out, Library partitions map directly to physical shards.
- **No scope creep**: Without a dedicated package, there's no temptation to add "Library business logic" that doesn't belong.

### Negative

- Every new model/protocol requires discipline to include `library_id`. Mitigated by: code review checklist, test assertions that `library_id` is the first field, and this ADR as reference.
- No built-in cross-Library analytics (by design — deferred to v2).

### Why Not a Package?

Creating `packages/library/` would:
- Give a data dimension false architectural status, inviting "LibraryService" with business logic that should live elsewhere.
- Create an unnecessary dependency node in the import graph.
- Confuse Library (data namespace) with Library (behavior module).

The correct mental model: **the system doesn't know how many Libraries exist. It just knows every piece of data has a `library_id`, and all reads/writes filter by it.**

## Alternatives Considered

| Option | Rejected Because |
|--------|-----------------|
| `packages/library/` as a full module | Gives data a false architectural role; invites scope creep |
| Schema-per-library in Postgres | Overly complex for v1; composite indexes suffice |
| Multi-tenant architecture | Library is data partitioning, not identity/auth — multi-tenancy is out of scope for v1 |
| Query-time filtering only (no physical isolation) | Risky for data leaks; hard to purge cleanly; poor ANN recall isolation in vector DBs |
