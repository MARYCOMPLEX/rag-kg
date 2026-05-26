"""Library lifecycle orchestration helpers and protocols.

Thin orchestration: calls init_library / purge_library on all registered
storage adapters. Not a service — just coordination functions and the
LibraryRepository protocol for metadata persistence.

The purge flow has two surfaces:

- `purge_library(library_id, *, adapters=...)` — the existing M1 path.
  Sequential, best-effort, no audit trail. Used by the dev/local flow
  where Postgres / MinIO / Qdrant aren't always wired up.
- `purge_library(library_id, *, registries=...)` — the M7 saga path
  (ADR-0022). Delegates to
  `packages.orchestration.adapters.library_purge.LibraryPurgeSaga` so
  the cross-storage retry / partial_purged state machine kicks in.

The two overloads are picked by which kwarg the caller passes; both are
type-checked at call time.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from packages.core.models import Library


@runtime_checkable
class LibraryAware(Protocol):
    """Any adapter that manages per-library physical resources."""

    async def init_library(self, library_id: str) -> None: ...
    async def purge_library(self, library_id: str) -> None: ...


@runtime_checkable
class LibraryRepository(Protocol):
    """CRUD for library metadata."""

    async def create(self, library: Library) -> None: ...
    async def get(self, library_id: str) -> Library | None: ...
    async def list_all(self) -> list[Library]: ...
    async def delete(self, library_id: str) -> None: ...
    async def exists(self, library_id: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class LibraryAdmins:
    """Registry of every adapter the saga needs to talk to (ADR-0022 §3).

    All fields except `repo` are optional — missing adapters are treated
    as a clean no-op by the saga (idempotent contract). This lets the
    M1 dev container exercise the saga without Qdrant / Neo4j / MinIO.
    """

    repo: LibraryRepository
    qdrant: LibraryAware | None = None
    bm25: LibraryAware | None = None
    neo4j: LibraryAware | None = None
    minio: LibraryAware | None = None


async def init_library(library_id: str, *, adapters: Sequence[LibraryAware]) -> None:
    """Initialize a library across all storage adapters."""
    for adapter in adapters:
        await adapter.init_library(library_id)


async def purge_library(
    library_id: str,
    *,
    adapters: Sequence[LibraryAware] | None = None,
    registries: LibraryAdmins | None = None,
    requested_by: str | None = None,
) -> None:
    """Physically purge a library from every backend.

    Two modes:

    - When `adapters` is supplied (M1 dev path), call each adapter's
      `purge_library` sequentially. Each call is expected to be
      idempotent (ADR-0022 §2): purging a missing collection / index /
      prefix is a no-op.
    - When `registries` is supplied (M7 production path), delegate to
      `LibraryPurgeSaga.purge` so the cross-storage state machine drives
      partial-failure recovery. `requested_by` is recorded on the audit
      row.

    Exactly one of the two must be set.
    """
    if registries is not None:
        if adapters is not None:
            msg = "Pass either `adapters` or `registries`, not both."
            raise ValueError(msg)
        # Local import keeps the package boundary clean — packages/core
        # doesn't depend on packages/orchestration in the static graph.
        from packages.orchestration.adapters.library_purge import LibraryPurgeSaga

        saga = LibraryPurgeSaga(
            repo=registries.repo,
            qdrant=registries.qdrant,
            bm25=registries.bm25,
            neo4j=registries.neo4j,
            minio=registries.minio,
        )
        await saga.purge(library_id, requested_by=requested_by)
        return

    if adapters is None:
        msg = "Either `adapters` or `registries` must be provided."
        raise ValueError(msg)
    # `adapters=()` is a legitimate no-op (M1 unit tests rely on this).
    for adapter in adapters:
        await adapter.purge_library(library_id)


__all__ = [
    "LibraryAdmins",
    "LibraryAware",
    "LibraryRepository",
    "init_library",
    "purge_library",
]
