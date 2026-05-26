"""CoordinatorRAGPlanner — adapts any RetrievalCoordinator to RetrievalPlanner.

The planner contract (L4) returns RetrievalResult with metadata.
The coordinator contract (L3) returns plain (chunk, score) tuples.
This adapter bridges the two layers.
"""

from __future__ import annotations

import time

from packages.core.models import Query
from packages.indexing.protocols import RetrievalCoordinator
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence


class CoordinatorRAGPlanner:
    """RetrievalPlanner that delegates to a RetrievalCoordinator (e.g. hybrid)."""

    def __init__(self, *, coordinator: RetrievalCoordinator, source: str = "hybrid") -> None:
        self._coordinator = coordinator
        self._source = source

    async def plan_and_retrieve(
        self,
        library_id: str,
        query: Query,
    ) -> RetrievalResult:
        if query.library_id != library_id:
            msg = (
                f"Query library_id '{query.library_id}' does not match "
                f"requested library_id '{library_id}'"
            )
            raise ValueError(msg)

        started = time.perf_counter()
        results = await self._coordinator.search(library_id, query.text, k=query.max_results)

        evidence = tuple(
            RetrievedEvidence(chunk=chunk, score=score, source=self._source)
            for chunk, score in results
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=evidence,
            duration_ms=elapsed_ms,
        )
