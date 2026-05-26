"""Async library purge job (ADR-0022).

Triggered by `DELETE /v1/libraries/{id}?purge=1` once the API handler has
re-validated the slug. The job orchestrates `LibraryPurgeSaga` and
records the result on the `tasks` row.

A second entry point — `resume_partial_purges` — is wired into the
worker startup hook so any library left in `purging` / `partial_purged` /
`pg_pending` after a crash is automatically retried (ADR-0022 §4).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from packages.core.errors import LibraryNotFoundError
from packages.core.library_admin import LibraryRepository
from packages.orchestration.adapters.library_purge import (
    LibraryPurgeResult,
    LibraryPurgeSaga,
)


async def run_library_purge(
    ctx: dict[str, Any],
    *,
    library_id: str,
    requested_by: str | None = None,
) -> dict[str, Any]:
    """Run the saga inside an Arq worker.

    Adapter dependencies are pulled from `ctx` (filled by the worker
    startup hook). Returns the saga result as a JSON-friendly dict so
    Arq can persist it without extra coercion.
    """
    saga = _saga_from_ctx(ctx)
    result = await saga.purge(library_id, requested_by=requested_by)
    return result.model_dump(mode="json")


async def resume_partial_purges(ctx: dict[str, Any]) -> list[LibraryPurgeResult]:
    """Worker startup hook — replays the saga for any non-terminal library.

    The candidate set is given to the worker by the API container at boot
    time via `ctx["partial_purge_resume_ids"]` so the worker doesn't have
    to crack open the libraries repo itself. Empty/missing keys are no-ops.
    """
    candidates = cast(Iterable[str] | None, ctx.get("partial_purge_resume_ids"))
    if not candidates:
        return []
    saga = _saga_from_ctx(ctx)
    results: list[LibraryPurgeResult] = []
    for library_id in candidates:
        try:
            results.append(await saga.purge(library_id, requested_by="worker_resume"))
        except LibraryNotFoundError:
            continue
    return results


def _saga_from_ctx(ctx: dict[str, Any]) -> LibraryPurgeSaga:
    """Resolve the saga from worker `ctx`. Missing adapters degrade to None."""
    repo = cast(LibraryRepository, ctx["library_repo"])
    return LibraryPurgeSaga(
        repo=repo,
        qdrant=ctx.get("vector_index"),
        bm25=ctx.get("bm25_index"),
        neo4j=ctx.get("graph_index"),
        minio=ctx.get("minio_index"),
        postgres_adapter=ctx.get("postgres_purge_adapter"),
        audit_writer=ctx.get("audit_writer"),
    )


__all__ = ["resume_partial_purges", "run_library_purge"]
