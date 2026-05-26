"""Tests for RoutedRAGPlanner dispatch logic."""

from __future__ import annotations

import pytest

from packages.core.models import Chunk, Query
from packages.retrieval.protocols import RetrievalResult, RetrievedEvidence
from packages.retrieval.router import QueryRouter, RouteDecision
from packages.retrieval.strategies.routed_rag import RoutedRAGPlanner


def _evidence(label: str, library_id: str = "test-lib") -> RetrievedEvidence:
    chunk = Chunk(
        library_id=library_id,
        chunk_id=f"d::p1::{label}",
        doc_id="d",
        text=f"text-{label}",
    )
    return RetrievedEvidence(chunk=chunk, score=0.9, source=label)


class FakePlanner:
    def __init__(self, label: str) -> None:
        self.label = label
        self.calls: list[tuple[str, str]] = []

    async def plan_and_retrieve(self, library_id: str, query: Query) -> RetrievalResult:
        self.calls.append((library_id, query.text))
        return RetrievalResult(
            library_id=library_id,
            query=query.text,
            evidence=(_evidence(self.label, library_id=library_id),),
        )


class StubRouter(QueryRouter):
    """Forces a fixed routing decision regardless of input."""

    def __init__(self, route: str) -> None:
        super().__init__()
        self._forced_route = route

    def classify(self, query_text: str) -> RouteDecision:  # type: ignore[override]
        # Both score values keep within validation bounds.
        score = 0.9 if self._forced_route == "global" else 0.1
        return RouteDecision(
            route="global" if self._forced_route == "global" else "local",
            reason=f"stub forced {self._forced_route}",
            score=score,
        )


class TestRoutedRAGPlanner:
    @pytest.mark.asyncio
    async def test_global_query_routes_to_global_planner(self) -> None:
        local = FakePlanner("local")
        global_p = FakePlanner("community")
        planner = RoutedRAGPlanner(
            router=StubRouter("global"),
            local_planner=local,
            global_planner=global_p,
        )

        query = Query(library_id="test-lib", text="summary of corpus")
        result = await planner.plan_and_retrieve("test-lib", query)

        assert global_p.calls == [("test-lib", "summary of corpus")]
        assert local.calls == []
        assert result.evidence[0].source == "community"

    @pytest.mark.asyncio
    async def test_local_query_routes_to_local_planner(self) -> None:
        local = FakePlanner("local")
        global_p = FakePlanner("community")
        planner = RoutedRAGPlanner(
            router=StubRouter("local"),
            local_planner=local,
            global_planner=global_p,
        )

        query = Query(library_id="test-lib", text="What is HippoRAG?")
        result = await planner.plan_and_retrieve("test-lib", query)

        assert local.calls == [("test-lib", "What is HippoRAG?")]
        assert global_p.calls == []
        assert result.evidence[0].source == "local"

    @pytest.mark.asyncio
    async def test_real_router_dispatch_end_to_end(self) -> None:
        local = FakePlanner("local")
        global_p = FakePlanner("community")
        planner = RoutedRAGPlanner(
            router=QueryRouter(),
            local_planner=local,
            global_planner=global_p,
        )

        await planner.plan_and_retrieve(
            "test-lib", Query(library_id="test-lib", text="What is HippoRAG?")
        )
        await planner.plan_and_retrieve(
            "test-lib",
            Query(library_id="test-lib", text="Give me an overall summary of themes."),
        )

        assert len(local.calls) == 1
        assert len(global_p.calls) == 1
