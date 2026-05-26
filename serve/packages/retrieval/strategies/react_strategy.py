"""ReAct as a ``RetrievalStrategy`` — thin adapter over the existing planner.

The legacy ``ReActPlanner`` already implements the ReAct loop with budget
plumbing. ADR-0017 §1 introduces the unified ``RetrievalStrategy`` Protocol
so the StrategyRouter can pick uniformly across ReAct / Self-RAG / CRAG /
ToG. We wrap rather than rewrite — see ADR_REVIEW R5.

SSE event emission (ADR-0010): each ReAct iteration corresponds to one
``stage_progress`` event named ``strategy_react_step_<n>``. Emission is
done by the caller (RetrievalPlanner facade) using ``trace.steps``;
this wrapper does NOT call the EventBus directly to keep it pure.
"""

from __future__ import annotations

from typing import Literal

from packages.core.models import Query
from packages.retrieval.protocols import (
    RetrievalBudget,
    RetrievalTrace,
)
from packages.retrieval.strategies.react_rag import ReActPlanner

REACT_STRATEGY_NAME: Literal["react"] = "react"


class ReActStrategy:
    """``RetrievalStrategy`` adapter for the existing ReActPlanner."""

    name: Literal["react"] = REACT_STRATEGY_NAME

    def __init__(self, planner: ReActPlanner) -> None:
        self._planner = planner

    async def run(
        self,
        library_id: str,
        query: Query,
        budget: RetrievalBudget,
    ) -> RetrievalTrace:
        # ReActPlanner takes its budget at construction time. We rebuild
        # a per-call planner with the supplied budget injected — cheaper
        # than retrofitting the legacy planner with a per-call override.
        planner = self._planner_with_budget(budget)
        result = await planner.plan_and_retrieve(library_id, query)
        if result.trace is None:
            return RetrievalTrace(
                library_id=library_id,
                query=query.text,
                planner=REACT_STRATEGY_NAME,
                terminated_reason="answer_ready",
            )
        return result.trace

    def _planner_with_budget(self, budget: RetrievalBudget) -> ReActPlanner:
        """Clone the wrapped planner with a different budget.

        Uses the public read-only accessors on ``ReActPlanner`` so the
        strategy stays decoupled from the planner's internal field
        layout (cf. ADR_REVIEW §11.2 — closes the prior pyright
        `reportPrivateUsage` warnings).
        """
        return ReActPlanner(
            llm=self._planner.llm,
            embedder=self._planner.embedder,
            vector_index=self._planner.vector_index,
            bm25_index=self._planner.bm25_index,
            graph_index=self._planner.graph_index,
            budget=budget,
            config=self._planner.config,
        )
