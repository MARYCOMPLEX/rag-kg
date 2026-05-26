"""HeuristicStrategyRouter — pick a ``RetrievalStrategy`` per query.

ADR-0017 §auto-router decision matrix:

    +---------------------+------------------------------------------+
    | Query.type          | Strategy (ample budget)                  |
    +---------------------+------------------------------------------+
    | single-hop          | ReAct                                    |
    | definition          | ReAct                                    |
    | multi-hop           | ToG  (entity-rich) → fallback Self-RAG   |
    | global              | Self-RAG (community search via critic)   |
    | (other / unknown)   | CRAG  (long-tail safety net)             |
    +---------------------+------------------------------------------+

Budget downshift (ADR-0017 §auto-router + ADR_REVIEW R5):

- ``headroom < 0.30`` (less than 30% of LLM-call budget left)
  → force ReAct (cheapest planner).
- ``headroom < 0.50`` on a multi-hop query
  → prefer Self-RAG over ToG (ToG burns LLM calls per beam round).

Headroom is computed against ``budget.max_llm_calls`` only — it's the
single dimension every strategy spends linearly. ``BudgetUsage`` is
*always* zero at router-time (no work has been done yet); the router
uses ``budget`` directly to decide whether the cap itself is comfortable.

Design notes:

- The router is **stateless and pure** other than the strategy
  factories injected at construction. Each call returns a fresh strategy
  instance so per-call configuration is honoured.
- All adapters live behind ``RetrievalStrategy`` so the orchestration
  layer never branches on planner internals.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import structlog

from packages.core.models import Query
from packages.retrieval._internal.budget_check import (
    TIGHT_BUDGET_LLM_CALLS_THRESHOLD,
    is_tight_budget,
)
from packages.retrieval.protocols import (
    RetrievalBudget,
    RetrievalStrategy,
    StrategyName,
)

# Headroom thresholds (fraction of LLM-call cap that must be available).
TIGHT_HEADROOM_FRACTION: float = 0.30
COMFORTABLE_HEADROOM_FRACTION: float = 0.50

# "Comfortable" budget — when ``max_llm_calls`` >= this number, headroom
# is reported as 1.0 (no derating). Below it, headroom decays linearly
# down to 0.0 at zero. Sized to match Self-RAG's worst-case 6 reflection
# rounds + a 4-call ToG beam search + slack — see ADR-0017 §auto-router
# and ``budget_check.MIN_SELF_RAG_LLM_CALLS_HEADROOM``.
COMFORTABLE_LLM_CALLS: int = 20

# Mypy/pyright-friendly factory aliases. Each factory returns a strategy
# wired with shared deps (LLM, indices, critic, etc.) — composition is
# pinned at app-startup time, see apps/api/deps.py.
StrategyFactory = Callable[[], RetrievalStrategy]


@dataclass(frozen=True, slots=True)
class StrategyFactories:
    """Per-strategy factory bundle (CODING_STANDARDS §6.5: dataclasses)."""

    react: StrategyFactory
    self_rag: StrategyFactory
    crag: StrategyFactory
    tog: StrategyFactory


@dataclass(frozen=True, slots=True)
class RouterDecision:
    """Diagnostic record of why a strategy was chosen."""

    chosen: StrategyName
    reason: str
    headroom_fraction: float


_logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class HeuristicStrategyRouter:
    """Implements the ``StrategyRouter`` Protocol per ADR-0017 §auto-router."""

    def __init__(self, factories: StrategyFactories) -> None:
        self._factories = factories

    async def choose(
        self,
        library_id: str,
        query: Query,
        budget: RetrievalBudget,
    ) -> RetrievalStrategy:
        decision = self._decide(query, budget)
        await _logger.ainfo(
            "strategy_router.choose",
            library_id=library_id,
            query_type=query.type,
            chosen=decision.chosen,
            reason=decision.reason,
            headroom_fraction=decision.headroom_fraction,
        )
        return self._build(decision.chosen)

    # ----- pure decision logic (kept testable independently of factories) ---

    def _decide(self, query: Query, budget: RetrievalBudget) -> RouterDecision:
        headroom = _headroom_fraction(budget)

        # Hard floor: tight budgets always go to ReAct.
        if headroom < TIGHT_HEADROOM_FRACTION or is_tight_budget(budget):
            return RouterDecision(
                chosen="react",
                reason=(
                    f"tight budget headroom={headroom:.2f} or "
                    f"max_llm_calls<{TIGHT_BUDGET_LLM_CALLS_THRESHOLD}"
                ),
                headroom_fraction=headroom,
            )

        if query.type in ("single-hop", "definition"):
            return RouterDecision(
                chosen="react",
                reason=f"{query.type} query → cheap planner",
                headroom_fraction=headroom,
            )
        if query.type == "multi-hop":
            if headroom > COMFORTABLE_HEADROOM_FRACTION:
                return RouterDecision(
                    chosen="tog",
                    reason="multi-hop with comfortable budget → ToG beam search",
                    headroom_fraction=headroom,
                )
            return RouterDecision(
                chosen="self_rag",
                reason="multi-hop with moderate budget → Self-RAG reflection",
                headroom_fraction=headroom,
            )
        if query.type == "global":
            return RouterDecision(
                chosen="self_rag",
                reason="global query → Self-RAG (community-summary path)",
                headroom_fraction=headroom,
            )
        # Defensive fallback — Query.type is a Literal today, but the
        # API surface accepts upcoming sources (M8+). CRAG is the
        # designated long-tail safety net (ADR-0017 §auto-router).
        return RouterDecision(
            chosen="crag",
            reason="unknown / long-tail query → CRAG safety net",
            headroom_fraction=headroom,
        )

    def _build(self, name: StrategyName) -> RetrievalStrategy:
        if name == "react":
            return self._factories.react()
        if name == "self_rag":
            return self._factories.self_rag()
        if name == "crag":
            return self._factories.crag()
        # Exhaustive: only "tog" remains in the StrategyName Literal.
        return self._factories.tog()


def _headroom_fraction(budget: RetrievalBudget) -> float:
    """Map ``budget.max_llm_calls`` onto a [0.0, 1.0] headroom signal.

    The router is invoked *before* any work runs, so the actual usage is
    always zero. Instead we treat ``COMFORTABLE_LLM_CALLS`` as the
    saturation point: a budget that meets it has 100% headroom; smaller
    caps decay linearly. This lets the router downshift to a cheaper
    planner when the per-task budget is already tight, even though we
    have not spent anything yet (see ADR-0017 §auto-router downshift).
    """
    cap = max(0, budget.max_llm_calls)
    if cap >= COMFORTABLE_LLM_CALLS:
        return 1.0
    return cap / COMFORTABLE_LLM_CALLS


# Re-export so callers don't have to chase the import.
__all__ = [
    "COMFORTABLE_HEADROOM_FRACTION",
    "COMFORTABLE_LLM_CALLS",
    "TIGHT_HEADROOM_FRACTION",
    "HeuristicStrategyRouter",
    "RouterDecision",
    "StrategyFactories",
    "StrategyFactory",
]
