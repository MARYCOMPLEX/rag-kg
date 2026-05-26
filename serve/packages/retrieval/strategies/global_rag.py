"""GlobalRAGPlanner — community-summary retrieval for corpus-wide questions.

Pipeline: embed query → CommunityIndex.search → wrap each Community as a
synthetic Chunk so downstream consumers can treat global evidence
uniformly with chunk-level evidence.
"""

from __future__ import annotations

import time

from packages.core.models import Chunk, Community, Query
from packages.embedding.protocols import Embedder
from packages.indexing.protocols import CommunityIndex
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence

DEFAULT_K: int = 5
COMMUNITY_DOC_ID: str = "community"
COMMUNITY_CHUNK_PREFIX: str = "community::"
COMMUNITY_SOURCE: str = "community"


class GlobalRAGPlanner:
    """Retrieves community summaries via vector search for global queries."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        community_index: CommunityIndex,
        k: int = DEFAULT_K,
    ) -> None:
        self._embedder = embedder
        self._community_index = community_index
        self._k = k

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

        results = await self._community_index.search(library_id, vectors[0], k=self._k)

        evidence = tuple(
            RetrievedEvidence(
                chunk=_community_to_chunk(community, library_id),
                score=score,
                source=COMMUNITY_SOURCE,
            )
            for community, score in results
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=evidence,
            duration_ms=elapsed_ms,
        )


def _community_to_chunk(community: Community, library_id: str) -> Chunk:
    """Wrap a Community summary as a synthetic Chunk for uniform downstream use."""
    title = community.title or community.community_id
    text = f"{title}\n\n{community.summary}"
    return Chunk(
        library_id=library_id,
        chunk_id=f"{COMMUNITY_CHUNK_PREFIX}{community.community_id}",
        doc_id=COMMUNITY_DOC_ID,
        text=text,
    )
