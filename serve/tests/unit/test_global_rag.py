"""Tests for GlobalRAGPlanner."""

from __future__ import annotations

import pytest

from packages.core.models import Community, Query
from packages.retrieval.strategies.global_rag import GlobalRAGPlanner


def _community(idx: int, library_id: str = "test-lib", title: str = "") -> Community:
    return Community(
        library_id=library_id,
        community_id=f"c{idx}",
        level=0,
        member_entity_ids=("e1", "e2"),
        title=title or f"Topic {idx}",
        summary=f"Summary text for community {idx}.",
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


class FakeCommunityIndex:
    def __init__(self, results: list[tuple[Community, float]] | None = None) -> None:
        self._results = results or []
        self.last_search_lib: str | None = None
        self.last_k: int | None = None

    async def init_library(self, library_id: str) -> None:
        pass

    async def purge_library(self, library_id: str) -> None:
        pass

    async def upsert(
        self,
        library_id: str,
        items: list[tuple[Community, list[float]]],
    ) -> None:
        pass

    async def search(
        self,
        library_id: str,
        vector: list[float],
        k: int,
    ) -> list[tuple[Community, float]]:
        self.last_search_lib = library_id
        self.last_k = k
        return self._results[:k]

    async def list_all(
        self,
        library_id: str,
        *,
        level: int | None = None,
    ) -> list[Community]:
        return [c for c, _ in self._results]


class TestGlobalRAGPlanner:
    @pytest.mark.asyncio
    async def test_builds_synthetic_chunks_with_community_id_format(self) -> None:
        results = [(_community(0, title="ToolUse"), 0.9), (_community(1), 0.7)]
        embedder = FakeEmbedder()
        index = FakeCommunityIndex(results=results)
        planner = GlobalRAGPlanner(embedder=embedder, community_index=index, k=5)

        query = Query(library_id="test-lib", text="overall themes?", type="global")
        result = await planner.plan_and_retrieve("test-lib", query)

        assert len(result.evidence) == 2
        first = result.evidence[0]
        assert first.chunk.chunk_id == "community::c0"
        assert first.chunk.doc_id == "community"
        assert "ToolUse" in first.chunk.text
        assert "Summary text for community 0." in first.chunk.text
        assert first.score == 0.9

    @pytest.mark.asyncio
    async def test_propagates_library_id(self) -> None:
        results = [(_community(0, library_id="other-lib"), 0.5)]
        # Note: synthetic chunk should carry the requested library_id, not the
        # community's stored one (which could lag behind in test fixtures).
        embedder = FakeEmbedder()
        index = FakeCommunityIndex(results=results)
        planner = GlobalRAGPlanner(embedder=embedder, community_index=index)

        query = Query(library_id="test-lib", text="summary please")
        result = await planner.plan_and_retrieve("test-lib", query)

        assert result.library_id == "test-lib"
        assert result.evidence[0].chunk.library_id == "test-lib"
        assert index.last_search_lib == "test-lib"

    @pytest.mark.asyncio
    async def test_source_is_community(self) -> None:
        results = [(_community(0), 0.5)]
        planner = GlobalRAGPlanner(
            embedder=FakeEmbedder(), community_index=FakeCommunityIndex(results=results)
        )
        query = Query(library_id="test-lib", text="overview")
        result = await planner.plan_and_retrieve("test-lib", query)
        assert result.evidence[0].source == "community"

    @pytest.mark.asyncio
    async def test_uses_planner_k_not_query_max_results(self) -> None:
        results = [(_community(i), 1.0 - 0.1 * i) for i in range(10)]
        index = FakeCommunityIndex(results=results)
        planner = GlobalRAGPlanner(embedder=FakeEmbedder(), community_index=index, k=3)
        query = Query(library_id="test-lib", text="summary", max_results=10)
        result = await planner.plan_and_retrieve("test-lib", query)
        assert index.last_k == 3
        assert len(result.evidence) == 3

    @pytest.mark.asyncio
    async def test_query_library_mismatch_raises(self) -> None:
        planner = GlobalRAGPlanner(embedder=FakeEmbedder(), community_index=FakeCommunityIndex())
        query = Query(library_id="other-lib", text="q")
        with pytest.raises(ValueError, match="does not match"):
            await planner.plan_and_retrieve("test-lib", query)

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        planner = GlobalRAGPlanner(
            embedder=FakeEmbedder(), community_index=FakeCommunityIndex(results=[])
        )
        query = Query(library_id="test-lib", text="q")
        result = await planner.plan_and_retrieve("test-lib", query)
        assert result.evidence == ()
