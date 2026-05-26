"""Tests for the HybridRetrievalCoordinator."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from packages.core.models import Chunk
from packages.indexing.service import (
    HybridRetrievalConfig,
    HybridRetrievalCoordinator,
    _rrf_fuse,
)


def _chunk(idx: int, text: str | None = None) -> Chunk:
    return Chunk(
        library_id="test-lib",
        chunk_id=f"d::p1::{idx}",
        doc_id="d",
        text=text or f"chunk {idx}",
    )


class FakeEmbedder:
    @property
    def dim(self) -> int:
        return 4

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


class FakeVectorIndex:
    def __init__(self, results: list[tuple[Chunk, float]]) -> None:
        self._results = results

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
        return self._results[:k]


class FakeBM25Index:
    def __init__(self, results: list[tuple[Chunk, float]]) -> None:
        self._results = results

    async def init_library(self, library_id: str) -> None:
        pass

    async def purge_library(self, library_id: str) -> None:
        pass

    async def upsert(self, library_id: str, chunks: list[Chunk]) -> None:
        pass

    async def search(self, library_id: str, query: str, k: int) -> list[tuple[Chunk, float]]:
        return self._results[:k]


class FakeReranker:
    def __init__(self, scores: dict[int, float]) -> None:
        self._scores = scores

    async def rerank(self, query: str, passages: list[str], k: int) -> list[tuple[int, float]]:
        # Return passages reordered by score, top-k
        ranked = sorted(self._scores.items(), key=lambda kv: kv[1], reverse=True)
        return [(idx, score) for idx, score in ranked if idx < len(passages)][:k]


class TestRRFFuse:
    def test_empty_lists(self) -> None:
        assert _rrf_fuse(ranked_lists=[]) == []

    def test_single_list_passes_through(self) -> None:
        c1 = _chunk(1)
        c2 = _chunk(2)
        result = _rrf_fuse(ranked_lists=[[(c1, 0.9), (c2, 0.7)]])
        assert len(result) == 2
        assert result[0][0].chunk_id == c1.chunk_id

    def test_two_lists_overlap_boosted(self) -> None:
        c1 = _chunk(1)
        c2 = _chunk(2)
        c3 = _chunk(3)
        list_a = [(c1, 0.9), (c2, 0.7)]
        list_b = [(c2, 0.9), (c3, 0.7)]
        result = _rrf_fuse(ranked_lists=[list_a, list_b])
        # c2 appears in both → highest fused score
        assert result[0][0].chunk_id == c2.chunk_id


class TestHybridCoordinator:
    @pytest.mark.asyncio
    async def test_returns_top_k_after_fusion(self) -> None:
        c1 = _chunk(1)
        c2 = _chunk(2)
        c3 = _chunk(3)
        coord = HybridRetrievalCoordinator(
            embedder=FakeEmbedder(),
            vector=FakeVectorIndex([(c1, 0.9), (c2, 0.7)]),
            bm25=FakeBM25Index([(c2, 0.8), (c3, 0.5)]),
            reranker=None,
            config=HybridRetrievalConfig(rerank=False, k_final=10),
        )
        result = await coord.search("test-lib", "q", k=3)
        assert len(result) == 3
        ids = {c.chunk_id for c, _ in result}
        assert ids == {c1.chunk_id, c2.chunk_id, c3.chunk_id}

    @pytest.mark.asyncio
    async def test_reranker_reorders_results(self) -> None:
        c1 = _chunk(1, text="alpha")
        c2 = _chunk(2, text="beta")
        coord = HybridRetrievalCoordinator(
            embedder=FakeEmbedder(),
            vector=FakeVectorIndex([(c1, 0.9), (c2, 0.7)]),
            bm25=FakeBM25Index([(c1, 0.8), (c2, 0.5)]),
            reranker=FakeReranker(scores={0: 0.1, 1: 0.99}),
            config=HybridRetrievalConfig(rerank=True),
        )
        result = await coord.search("test-lib", "q", k=2)
        # Reranker says index 1 (c2) is best
        assert result[0][0].chunk_id == c2.chunk_id

    @pytest.mark.asyncio
    async def test_no_results_returns_empty(self) -> None:
        coord = HybridRetrievalCoordinator(
            embedder=FakeEmbedder(),
            vector=FakeVectorIndex([]),
            bm25=FakeBM25Index([]),
            reranker=None,
        )
        result = await coord.search("test-lib", "q", k=5)
        assert result == []
