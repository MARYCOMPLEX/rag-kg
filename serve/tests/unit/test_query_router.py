"""Tests for QueryRouter heuristic classification."""

from __future__ import annotations

import pytest

from packages.retrieval.router import QueryRouter, RouteDecision


@pytest.fixture
def router() -> QueryRouter:
    return QueryRouter()


class TestQueryRouterGlobalSignals:
    def test_main_themes_routes_global(self, router: QueryRouter) -> None:
        decision = router.classify("What are the main themes in this corpus?")
        assert decision.route == "global"
        assert decision.score >= 0.5
        assert decision.reason

    def test_summary_query_routes_global(self, router: QueryRouter) -> None:
        decision = router.classify("Give me a summary of the recent literature.")
        assert decision.route == "global"
        assert "global_signals" in decision.reason

    def test_categories_query_routes_global(self, router: QueryRouter) -> None:
        decision = router.classify("What categories of methods exist?")
        assert decision.route == "global"

    def test_chinese_global_signal_routes_global(self, router: QueryRouter) -> None:
        decision = router.classify("请给我一个整体的概览")
        assert decision.route == "global"

    def test_long_query_with_global_word_routes_global(self, router: QueryRouter) -> None:
        decision = router.classify(
            "Please give me an overall picture of the trends and "
            "categories of retrieval augmented generation methods discussed."
        )
        assert decision.route == "global"
        assert decision.score >= 0.5


class TestQueryRouterLocalSignals:
    def test_what_is_specific_entity_routes_local(self, router: QueryRouter) -> None:
        decision = router.classify("What is HippoRAG?")
        assert decision.route == "local"
        assert "local_signals" in decision.reason

    def test_how_does_x_work_routes_local(self, router: QueryRouter) -> None:
        decision = router.classify("How does ReAct's loop work?")
        assert decision.route == "local"

    def test_who_is_routes_local(self, router: QueryRouter) -> None:
        decision = router.classify("Who is Gao?")
        assert decision.route == "local"

    def test_short_unmarked_query_defaults_local(self, router: QueryRouter) -> None:
        decision = router.classify("retrieval augmented generation")
        assert decision.route == "local"
        assert decision.score < 0.5


class TestQueryRouterLengthHeuristic:
    def test_very_long_query_alone_does_not_force_global(self, router: QueryRouter) -> None:
        # 13+ words but no global signal words → still under threshold
        decision = router.classify(
            "this question has many words but no specific global signal words at all"
        )
        # Length alone (0.25) is below the 0.5 threshold → local
        assert decision.route == "local"
        assert "long_query" in decision.reason

    def test_local_signal_overrides_global_word(self, router: QueryRouter) -> None:
        # "what is" is a local pattern; even with "main" present, local should win
        decision = router.classify("What is the main contribution of HippoRAG?")
        assert decision.route == "local"


class TestRouteDecisionShape:
    def test_decision_is_frozen(self, router: QueryRouter) -> None:
        decision = router.classify("What is X?")
        assert isinstance(decision, RouteDecision)
        with pytest.raises(Exception):  # noqa: PT011, B017
            decision.route = "global"  # type: ignore[misc]

    def test_decision_score_in_range(self, router: QueryRouter) -> None:
        for q in ["What is X?", "Give me an overall summary", "hello world"]:
            decision = router.classify(q)
            assert 0.0 <= decision.score <= 1.0
            assert decision.reason

    def test_empty_query_defaults_local(self, router: QueryRouter) -> None:
        decision = router.classify("   ")
        assert decision.route == "local"
        assert decision.score == 0.0
