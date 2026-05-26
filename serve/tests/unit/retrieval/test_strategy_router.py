"""Unit tests for the HeuristicStrategyRouter (ADR-0017 §auto-router)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import pytest

from packages.core.models import Query
from packages.retrieval.protocols import (
    RetrievalBudget,
    RetrievalStrategy,
    RetrievalTrace,
    StrategyName,
)
from packages.retrieval.strategy_router import (
    COMFORTABLE_LLM_CALLS,
    HeuristicStrategyRouter,
    StrategyFactories,
)

LIB = "test-lib"
QueryType = Literal["single-hop", "multi-hop", "global", "definition"]


class _StubStrategy:
    """Implements ``RetrievalStrategy`` without doing real work."""

    def __init__(self, name: StrategyName) -> None:
        self.name: StrategyName = name

    async def run(
        self,
        library_id: str,
        query: Query,
        budget: RetrievalBudget,
    ) -> RetrievalTrace:
        del query, budget
        return RetrievalTrace(library_id=library_id, query="", planner=self.name)


def _factory(name: StrategyName) -> Callable[[], RetrievalStrategy]:
    def _build() -> RetrievalStrategy:
        return _StubStrategy(name)

    return _build


def _factories() -> StrategyFactories:
    return StrategyFactories(
        react=_factory("react"),
        self_rag=_factory("self_rag"),
        crag=_factory("crag"),
        tog=_factory("tog"),
    )


def _query(qtype: QueryType, text: str = "q") -> Query:
    return Query(library_id=LIB, text=text, type=qtype)


COMFORTABLE_BUDGET = RetrievalBudget(max_llm_calls=COMFORTABLE_LLM_CALLS * 2)
MODERATE_BUDGET = RetrievalBudget(
    max_llm_calls=int(COMFORTABLE_LLM_CALLS * 0.5)  # exactly headroom = 0.5
)
TIGHT_BUDGET = RetrievalBudget(max_llm_calls=5)


@pytest.mark.parametrize(
    ("query_type", "budget", "expected"),
    [
        # Single-hop / definition always go to ReAct.
        ("single-hop", COMFORTABLE_BUDGET, "react"),
        ("definition", COMFORTABLE_BUDGET, "react"),
        ("single-hop", TIGHT_BUDGET, "react"),
        # Multi-hop: ToG when budget is comfortable, Self-RAG otherwise.
        ("multi-hop", COMFORTABLE_BUDGET, "tog"),
        ("multi-hop", MODERATE_BUDGET, "self_rag"),
        # Global → Self-RAG (community search via critic).
        ("global", COMFORTABLE_BUDGET, "self_rag"),
        # Tight budget always downshifts to ReAct, regardless of type.
        ("multi-hop", TIGHT_BUDGET, "react"),
        ("global", TIGHT_BUDGET, "react"),
    ],
)
@pytest.mark.asyncio
async def test_choose_matches_decision_table(
    query_type: QueryType,
    budget: RetrievalBudget,
    expected: StrategyName,
) -> None:
    router = HeuristicStrategyRouter(_factories())
    chosen = await router.choose(LIB, _query(query_type), budget)
    assert chosen.name == expected


@pytest.mark.asyncio
async def test_decide_records_reason_and_headroom() -> None:
    router = HeuristicStrategyRouter(_factories())
    decision = router._decide(_query("multi-hop"), COMFORTABLE_BUDGET)
    assert decision.chosen == "tog"
    assert decision.headroom_fraction == 1.0
    assert "comfortable" in decision.reason


@pytest.mark.asyncio
async def test_choose_returns_fresh_strategy_each_call() -> None:
    """Factories produce a new instance per call (no shared state)."""
    router = HeuristicStrategyRouter(_factories())
    a = await router.choose(LIB, _query("multi-hop"), COMFORTABLE_BUDGET)
    b = await router.choose(LIB, _query("multi-hop"), COMFORTABLE_BUDGET)
    assert a is not b


@pytest.mark.asyncio
async def test_unknown_query_type_falls_back_to_crag() -> None:
    """Defensive: when ``query.type`` is something the router does not know,
    the safety-net is CRAG.

    The Query model uses a Literal today, so we simulate this by mutating
    the dumped payload before re-parsing — which is what would happen if
    the API surface broadened in M8+.
    """
    router = HeuristicStrategyRouter(_factories())
    # Build a query then bypass validation by passing a known type but
    # tricking the router via direct ``_decide`` call with an unrecognised
    # string. Use object.__setattr__ since the model is frozen.
    q = _query("single-hop")
    object.__setattr__(q, "type", "exotic-future-type")
    decision = router._decide(q, COMFORTABLE_BUDGET)
    assert decision.chosen == "crag"


@pytest.mark.parametrize(
    "qtype",
    ["single-hop", "multi-hop", "global", "definition"],
)
@pytest.mark.asyncio
async def test_tight_budget_overrides_query_type(qtype: QueryType) -> None:
    router = HeuristicStrategyRouter(_factories())
    chosen = await router.choose(LIB, _query(qtype), TIGHT_BUDGET)
    assert chosen.name == "react"
