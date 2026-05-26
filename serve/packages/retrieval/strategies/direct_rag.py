"""DirectRAGPlanner — single-shot vector retrieval, no agent loop.

This is the M1 baseline planner: embed the query, search the vector
index, return top-k. No reflection, no rewrite, no multi-hop.
Upgrades (Self-RAG, CRAG, ToG) come in M4.
"""

from __future__ import annotations

import time

from packages.core.models import Query
from packages.embedding.protocols import Embedder
from packages.indexing.protocols import VectorIndex
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence


class DirectRAGPlanner:
    """Single-shot retrieval: embed query → vector search → top-k chunks."""

    def __init__(self, *, embedder: Embedder, vector_index: VectorIndex) -> None:
        self._embedder = embedder
        self._vector_index = vector_index

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
        vectors = await self._embedder.embed([query.text])
        if not vectors:
            return RetrievalResult(library_id=library_id, query=query.text)

        results = await self._vector_index.search(library_id, vectors[0], k=query.max_results)

        evidence = tuple(
            RetrievedEvidence(chunk=chunk, score=score, source="vector") for chunk, score in results
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=evidence,
            duration_ms=elapsed_ms,
        )
