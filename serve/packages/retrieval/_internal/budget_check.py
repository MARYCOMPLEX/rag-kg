"""Budget headroom helpers for ADR-0017 strategies + StrategyRouter.

Each strategy threads a ``RetrievalBudget`` through its loop. Before any
LLM / embed / index call we ask: does the budget have enough headroom to
afford this step? If not, the strategy short-circuits with
``terminated_reason="budget_exceeded"`` (PRD §11.4).

Headroom is computed against the *current* ``BudgetUsage`` snapshot, not
just the cap, so partial work is honoured. The router consults the same
helpers when it downshifts to a cheaper strategy on near-cap budgets
(ADR-0017 §auto-router).

All helpers are pure: deterministic, no I/O, no logging. Callers wrap them
with structlog at decision points.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from packages.retrieval.protocols import BudgetUsage, RetrievalBudget

# Minimum headroom for a single LLM call. Reflection rounds in Self-RAG
# are LLM-heavy (4 reflection roles × ~600 tokens each). Routers refuse
# to pick Self-RAG when fewer than ``MIN_SELF_RAG_LLM_CALLS_HEADROOM``
# calls remain.
MIN_REACT_LLM_CALLS_HEADROOM: int = 1
MIN_CRAG_LLM_CALLS_HEADROOM: int = 3
MIN_SELF_RAG_LLM_CALLS_HEADROOM: int = 6
MIN_TOG_LLM_CALLS_HEADROOM: int = 4
TIGHT_BUDGET_LLM_CALLS_THRESHOLD: int = 10


@dataclass(frozen=True, slots=True)
class BudgetSnapshot:
    """Inputs for headroom decisions — caller-managed counters."""

    budget: RetrievalBudget
    usage: BudgetUsage
    started_at_monotonic: float

    def llm_calls_remaining(self) -> int:
        return max(0, self.budget.max_llm_calls - self.usage.llm_calls)

    def steps_remaining(self) -> int:
        return max(0, self.budget.max_steps - self.usage.steps)

    def input_tokens_remaining(self) -> int:
        return max(0, self.budget.max_input_tokens - self.usage.input_tokens)

    def output_tokens_remaining(self) -> int:
        return max(0, self.budget.max_output_tokens - self.usage.output_tokens)

    def time_remaining_s(self) -> float:
        elapsed = time.perf_counter() - self.started_at_monotonic
        return max(0.0, self.budget.timeout_s - elapsed)

    def is_exhausted(self) -> bool:
        return (
            self.llm_calls_remaining() <= 0
            or self.steps_remaining() <= 0
            or self.time_remaining_s() <= 0.0
        )


def has_headroom_for(snapshot: BudgetSnapshot, *, llm_calls: int = 1) -> bool:
    """Return True iff the snapshot has at least ``llm_calls`` headroom AND
    one step AND non-zero time remaining.
    """
    if snapshot.is_exhausted():
        return False
    return snapshot.llm_calls_remaining() >= llm_calls


def is_tight_budget(budget: RetrievalBudget) -> bool:
    """Coarse signal used by the auto-router (ADR-0017 §auto-router).

    A "tight" budget is one where Self-RAG's reflection cost would not
    fit comfortably; the router downshifts to ReAct in that case.
    """
    return budget.max_llm_calls < TIGHT_BUDGET_LLM_CALLS_THRESHOLD
