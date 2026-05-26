"""Tests for DirectRAGPlanner."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from packages.core.models import Chunk, Query
from packages.retrieval.strategies.direct_rag import DirectRAGPlanner


def _chunk(idx: int, library_id: str = "test-lib") -> Chunk:
    return Chunk(
        library_id=library_id,
        chunk_id=f"d::p1::{idx}",
        doc_id="d",
        text=f"chunk text {idx}",
    )


class FakeEmbedder:
    def __init__(self) -> None:
        self.last_texts: list[str] = []

    @property
    def dim(self) -> int:
        return 4

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.last_texts = list(texts)
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class FakeVectorIndex:
    def __init__(self, results: list[tuple[Chunk, float]] | None = None) -> None:
        self._results = results or []
        self.last_search_lib: str | None = None
        self.last_k: int | None = None

    async def init_library(self, library_id: str) -> None:
        pass

    async def purge_library(self, library_id: str) -> None:
        pass

    async def upsert(self, library_id: str, items: list[tuple[Chunk, list[float]]]) -> None:
        pass

    async def search(
        self,
        library_id: str,
        vector: list[float],
        k: int,
        *,
        filter: Mapping[str, object] | None = None,
    ) -> list[tuple[Chunk, float]]:
        self.last_search_lib = library_id
        self.last_k = k
        return self._results[:k]


class TestDirectRAGPlanner:
    @pytest.mark.asyncio
    async def test_returns_evidence_in_score_order(self) -> None:
        results = [(_chunk(0), 0.9), (_chunk(1), 0.7), (_chunk(2), 0.5)]
        embedder = FakeEmbedder()
        idx = FakeVectorIndex(results=results)
        planner = DirectRAGPlanner(embedder=embedder, vector_index=idx)

        query = Query(library_id="test-lib", text="What is X?", max_results=10)
        result = await planner.plan_and_retrieve("test-lib", query)

        assert result.library_id == "test-lib"
        assert result.query == "What is X?"
        assert len(result.evidence) == 3
        assert result.evidence[0].score == 0.9
        assert result.evidence[0].chunk.chunk_id == "d::p1::0"

    @pytest.mark.asyncio
    async def test_passes_library_id_to_index(self) -> None:
        embedder = FakeEmbedder()
        idx = FakeVectorIndex()
        planner = DirectRAGPlanner(embedder=embedder, vector_index=idx)
        query = Query(library_id="test-lib", text="q", max_results=5)
        await planner.plan_and_retrieve("test-lib", query)
        assert idx.last_search_lib == "test-lib"
        assert idx.last_k == 5

    @pytest.mark.asyncio
    async def test_query_library_mismatch_raises(self) -> None:
        embedder = FakeEmbedder()
        idx = FakeVectorIndex()
        planner = DirectRAGPlanner(embedder=embedder, vector_index=idx)
        query = Query(library_id="other-lib", text="q")
        with pytest.raises(ValueError, match="does not match"):
            await planner.plan_and_retrieve("test-lib", query)

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        embedder = FakeEmbedder()
        idx = FakeVectorIndex(results=[])
        planner = DirectRAGPlanner(embedder=embedder, vector_index=idx)
        query = Query(library_id="test-lib", text="q")
        result = await planner.plan_and_retrieve("test-lib", query)
        assert result.evidence == ()
