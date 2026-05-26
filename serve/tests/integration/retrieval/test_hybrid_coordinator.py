"""Integration tests for the upgraded HybridRetrievalCoordinator.

These exercise the three-route + RRF + reranker pipeline end-to-end with
in-process fakes for vector / BM25 / graph routes and the Noop reranker.
The intent is to lock down ADR-0018 §2 wiring guarantees that the unit
tests in ``tests/unit/test_hybrid_coordinator.py`` cannot easily express
because they predate the FusedHit/RerankedHit shapes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping

import pytest

from packages.core.models import Chunk
from packages.indexing.adapters.noop_reranker import NoopReranker
from packages.indexing.protocols import RerankedHit
from packages.indexing.service import (
    DEFAULT_ROUTE_TIMEOUT_S,
    HybridRetrievalConfig,
    HybridRetrievalCoordinator,
)

LIB = "test-lib"


def _chunk(idx: int, text: str | None = None) -> Chunk:
    return Chunk(
        library_id=LIB,
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
    def __init__(
        self,
        results: list[tuple[Chunk, float]],
        *,
        delay_s: float = 0.0,
        raises: type[BaseException] | None = None,
    ) -> None:
        self._results = results
        self._delay_s = delay_s
        self._raises = raises

    async def init_library(self, library_id: str) -> None:
        return None

    async def purge_library(self, library_id: str) -> None:
        return None

    async def upsert(self, library_id: str, items: list[tuple[Chunk, list[float]]]) -> None:
        return None

    async def search(
        self,
        library_id: str,
        vector: list[float],
        k: int,
        *,
        filter: Mapping[str, object] | None = None,
    ) -> list[tuple[Chunk, float]]:
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        if self._raises:
            raise self._raises("boom")
        return self._results[:k]


class FakeBM25Index:
    def __init__(
        self,
        results: list[tuple[Chunk, float]],
        *,
        raises: type[BaseException] | None = None,
    ) -> None:
        self._results = results
        self._raises = raises

    async def init_library(self, library_id: str) -> None:
        return None

    async def purge_library(self, library_id: str) -> None:
        return None

    async def upsert(self, library_id: str, chunks: list[Chunk]) -> None:
        return None

    async def search(self, library_id: str, query: str, k: int) -> list[tuple[Chunk, float]]:
        if self._raises:
            raise self._raises("boom")
        return self._results[:k]


async def _graph_search_factory(
    results: list[tuple[Chunk, float]],
):
    async def _search(library_id: str, query: str, k: int) -> list[tuple[Chunk, float]]:
        del library_id, query
        return results[:k]

    return _search


@pytest.mark.asyncio
async def test_three_routes_fuse_with_rrf_and_noop_rerank() -> None:
    c1, c2, c3 = _chunk(1), _chunk(2), _chunk(3)
    graph_search = await _graph_search_factory([(c3, 0.99), (c1, 0.4)])
    coord = HybridRetrievalCoordinator(
        embedder=FakeEmbedder(),
        vector=FakeVectorIndex([(c1, 0.9), (c2, 0.7)]),
        bm25=FakeBM25Index([(c2, 0.8), (c3, 0.5)]),
        graph_search=graph_search,
        reranker=NoopReranker(),
        config=HybridRetrievalConfig(rerank=True, k_final=10),
    )

    out = await coord.hybrid_retrieve(LIB, "q", k=5)

    assert isinstance(out, tuple)
    assert all(isinstance(hit, RerankedHit) for hit in out)
    # All three chunks contributed; union covers c1, c2, c3.
    ids = {hit.chunk.chunk_id for hit in out}
    assert ids == {c1.chunk_id, c2.chunk_id, c3.chunk_id}
    # Sources are tracked per chunk by rrf_fuse.
    by_id = {hit.chunk.chunk_id: hit for hit in out}
    assert "graph" in by_id[c3.chunk_id].sources
    assert "vector" in by_id[c1.chunk_id].sources
    assert "bm25" in by_id[c2.chunk_id].sources


@pytest.mark.asyncio
async def test_legacy_search_signature_preserved() -> None:
    """The pre-ADR-0018 ``search`` signature returns ``list[(Chunk, float)]``."""
    c1, c2 = _chunk(1), _chunk(2)
    coord = HybridRetrievalCoordinator(
        embedder=FakeEmbedder(),
        vector=FakeVectorIndex([(c1, 0.9), (c2, 0.7)]),
        bm25=FakeBM25Index([(c1, 0.8), (c2, 0.5)]),
        reranker=None,
        config=HybridRetrievalConfig(rerank=False, k_final=10),
    )
    out = await coord.search(LIB, "q", k=2)
    assert isinstance(out, list)
    for entry in out:
        assert isinstance(entry, tuple)
        chunk, score = entry
        assert isinstance(chunk, Chunk)
        assert isinstance(score, float)


@pytest.mark.asyncio
async def test_partial_route_failure_degrades_gracefully() -> None:
    """When one route raises, the remaining routes still produce a result."""
    c1, c2 = _chunk(1), _chunk(2)
    coord = HybridRetrievalCoordinator(
        embedder=FakeEmbedder(),
        vector=FakeVectorIndex([], raises=RuntimeError),
        bm25=FakeBM25Index([(c1, 0.8), (c2, 0.5)]),
        reranker=NoopReranker(),
        config=HybridRetrievalConfig(rerank=True, k_final=10),
    )
    out = await coord.hybrid_retrieve(LIB, "q", k=5)
    ids = {hit.chunk.chunk_id for hit in out}
    assert ids == {c1.chunk_id, c2.chunk_id}


@pytest.mark.asyncio
async def test_route_timeout_is_absorbed() -> None:
    """A route that exceeds ``route_timeout_s`` is treated as a partial failure."""
    c1 = _chunk(1)
    coord = HybridRetrievalCoordinator(
        embedder=FakeEmbedder(),
        vector=FakeVectorIndex([(c1, 0.9)], delay_s=DEFAULT_ROUTE_TIMEOUT_S + 0.5),
        bm25=FakeBM25Index([(c1, 0.8)]),
        reranker=NoopReranker(),
        config=HybridRetrievalConfig(rerank=True, k_final=5, route_timeout_s=0.05),
    )
    out = await coord.hybrid_retrieve(LIB, "q", k=3)
    # BM25 result still arrived; vector timed out.
    assert any(hit.chunk.chunk_id == c1.chunk_id for hit in out)
    sources = {s for hit in out for s in hit.sources}
    assert "bm25" in sources
    assert "vector" not in sources


@pytest.mark.asyncio
async def test_empty_runs_return_empty_tuple() -> None:
    coord = HybridRetrievalCoordinator(
        embedder=FakeEmbedder(),
        vector=FakeVectorIndex([]),
        bm25=FakeBM25Index([]),
        reranker=NoopReranker(),
        config=HybridRetrievalConfig(rerank=True),
    )
    out = await coord.hybrid_retrieve(LIB, "q", k=5)
    assert out == ()


@pytest.mark.asyncio
async def test_rrf_top_fused_capped_then_rerank_top_k() -> None:
    """RRF intermediate set is capped at ``top_fused``, rerank trims to k."""
    chunks = [_chunk(i) for i in range(50)]
    coord = HybridRetrievalCoordinator(
        embedder=FakeEmbedder(),
        vector=FakeVectorIndex([(c, 0.5) for c in chunks]),
        bm25=FakeBM25Index([(c, 0.4) for c in chunks]),
        reranker=NoopReranker(),
        config=HybridRetrievalConfig(
            rerank=True,
            k_vector=50,
            k_bm25=50,
            top_fused=10,
            k_final=4,
        ),
    )
    out = await coord.hybrid_retrieve(LIB, "q", k=4)
    assert len(out) == 4
    # Post-rerank ranks are dense 1..k.
    ranks = sorted(hit.post_rerank_rank for hit in out)
    assert ranks == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_hybrid_retrieve_default_k_is_ten() -> None:
    """Documented contract: ``hybrid_retrieve(library_id, query)`` defaults k=10."""
    chunks = [_chunk(i) for i in range(20)]
    coord = HybridRetrievalCoordinator(
        embedder=FakeEmbedder(),
        vector=FakeVectorIndex([(c, 0.5) for c in chunks]),
        bm25=FakeBM25Index([(c, 0.4) for c in chunks]),
        reranker=NoopReranker(),
        config=HybridRetrievalConfig(rerank=True, k_vector=20, k_bm25=20, top_fused=20),
    )
    out = await coord.hybrid_retrieve(LIB, "q")
    assert len(out) == 10
