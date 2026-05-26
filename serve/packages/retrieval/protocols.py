"""Retrieval planner protocol definitions.

M4 adds RetrievalBudget and RetrievalTrace to bound + observe agentic
retrieval (ReAct, Self-RAG, CRAG). The trace doubles as a debugging
artifact and a Langfuse payload.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.core.models import Chunk, Query


class RetrievedEvidence(BaseModel):
    """A retrieved chunk with score and source metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk: Chunk
    score: float
    source: str = "vector"


class StepCost(BaseModel):
    """Cost summary for a single retrieval step."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0


class RetrievalStep(BaseModel):
    """One step of an agentic retrieval loop."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_idx: int = Field(ge=0)
    thought: str = ""
    action: str = ""
    action_input: str = ""
    observation: str = ""
    cost: StepCost = StepCost()


class BudgetUsage(BaseModel):
    """Aggregated budget consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    steps: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0


class RetrievalBudget(BaseModel):
    """Hard caps on agentic retrieval — protects cost + latency."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_steps: int = Field(default=8, ge=1, le=50)
    max_llm_calls: int = Field(default=20, ge=1, le=200)
    max_input_tokens: int = Field(default=32000, ge=100)
    max_output_tokens: int = Field(default=4000, ge=100)
    timeout_s: float = Field(default=120.0, ge=1.0)


class RetrievalTrace(BaseModel):
    """Step-by-step execution record for an agentic retrieval run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    query: str
    planner: str = ""
    steps: tuple[RetrievalStep, ...] = ()
    budget_used: BudgetUsage = BudgetUsage()
    terminated_reason: Literal[
        "answer_ready", "budget_exceeded", "no_evidence", "error", "timeout"
    ] = "answer_ready"


class RetrievalResult(BaseModel):
    """Output of a retrieval plan: ranked evidence + diagnostic info.

    Optional `trace` field carries agentic-planner step history when
    populated (M4+ planners). M0-M3 planners leave it None.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    query: str
    evidence: tuple[RetrievedEvidence, ...] = ()
    duration_ms: int = 0
    trace: RetrievalTrace | None = None


@runtime_checkable
class RetrievalPlanner(Protocol):
    """Plans and executes a retrieval strategy for a query.

    Public facade — internally consults `StrategyRouter` and a chosen
    `RetrievalStrategy` (see ADR-0017 + ADR_REVIEW R5).
    """

    async def plan_and_retrieve(
        self,
        library_id: str,
        query: Query,
    ) -> RetrievalResult: ...


# ----------------------------------------------------------------------
# M7: Strategy abstraction (ADR-0017 Self-RAG / CRAG / ToG)
# ----------------------------------------------------------------------


type StrategyName = Literal["react", "self_rag", "crag", "tog"]


@runtime_checkable
class RetrievalStrategy(Protocol):
    """A single retrieval algorithm with explicit budget plumbing.

    All implementations:
    - Take `library_id` first per CODING_STANDARDS §6.5
    - Respect the supplied `RetrievalBudget` hard caps
    - Emit SSE stage events (ADR-0010) named `<name>_step_<n>`
    - Never call cross-Library data adapters
    """

    name: StrategyName

    async def run(
        self,
        library_id: str,
        query: Query,
        budget: RetrievalBudget,
    ) -> RetrievalTrace: ...


@runtime_checkable
class StrategyRouter(Protocol):
    """Picks a `RetrievalStrategy` based on query type + active budget.

    Defaults to ReAct on tight budgets / single-hop queries; upgrades to
    Self-RAG / CRAG / ToG when budget headroom + question complexity
    warrant. See ADR-0017 §auto-router heuristic.
    """

    async def choose(
        self,
        library_id: str,
        query: Query,
        budget: RetrievalBudget,
    ) -> RetrievalStrategy: ...
