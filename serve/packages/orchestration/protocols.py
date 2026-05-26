"""Orchestration layer protocol definitions.

L5 task models: QA, Review, CrossPaperReasoning, Hypothesis.
All tasks are library-scoped, budgeted, and produce traceable artifacts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.core.models import Entity, Triple
from packages.retrieval.protocols import RetrievedEvidence


class Citation(BaseModel):
    """A claim → evidence link in an answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    page: int | None = None
    snippet: str = ""


class TokenUsage(BaseModel):
    """Token counts and estimated cost for an LLM exchange."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class AnsweredQuery(BaseModel):
    """Final QA output with answer text + citations + diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    question: str
    answer: str
    citations: tuple[Citation, ...] = ()
    retrieved: tuple[RetrievedEvidence, ...] = ()
    model: str = ""
    tokens: TokenUsage = TokenUsage()
    duration_ms: int = 0


# === M5: research task models ===


class TaskBudget(BaseModel):
    """Per-task cost and time bounds."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_subtopics: int = Field(default=8, ge=1, le=30)
    max_chunks_per_subtopic: int = Field(default=6, ge=1, le=50)
    max_llm_calls: int = Field(default=30, ge=1, le=300)
    max_total_tokens: int = Field(default=80_000, ge=1000)
    timeout_s: float = Field(default=600.0, ge=10.0)


class TaskCost(BaseModel):
    """Aggregated cost for a completed task run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0


class ReviewSection(BaseModel):
    """One section of a generated literature review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    heading: str = Field(min_length=1)
    body: str
    citations: tuple[Citation, ...] = ()
    evidence: tuple[RetrievedEvidence, ...] = ()


class ReviewResult(BaseModel):
    """Output of ReviewGenerationTask."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    abstract: str = ""
    sections: tuple[ReviewSection, ...] = ()
    cost: TaskCost = TaskCost()


class ReasoningStep(BaseModel):
    """One step in a multi-hop cross-paper reasoning trace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sub_question: str = Field(min_length=1)
    answer: str = ""
    evidence: tuple[RetrievedEvidence, ...] = ()


class ReasoningPath(BaseModel):
    """A KG multi-hop path that supports a cross-paper reasoning conclusion.

    Carries structured nodes and relations so the frontend can draw the
    path visualization (S7 Reason). Distinct from `ReasoningStep`, which
    is the LLM sub-question decomposition.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    nodes: tuple[Entity, ...] = ()
    relations: tuple[Triple, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""


class CrossPaperReasoningResult(BaseModel):
    """Output of CrossPaperReasoningTask."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    sub_steps: tuple[ReasoningStep, ...] = ()
    paths: tuple[ReasoningPath, ...] = ()  # M7: structured KG paths
    final_answer: str = ""
    citations: tuple[Citation, ...] = ()
    cost: TaskCost = TaskCost()


class Hypothesis(BaseModel):
    """One generated hypothesis with KG-grounded support and 3-axis scoring.

    Scoring axes (M7, ADR-0020):
    - confidence: geomean of supporting path confidences
    - novelty: embedding distance from existing corpus conclusions
    - verifiability: fraction of Method/Dataset nodes on supporting paths
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    statement: str = Field(min_length=1)
    rationale: str = ""
    supporting_paths: tuple[tuple[str, ...], ...] = ()
    counter_evidence: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)
    verifiability: float = Field(default=0.0, ge=0.0, le=1.0)


class HypothesisResult(BaseModel):
    """Output of HypothesisTask."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    head_entity_id: str = Field(min_length=1)
    tail_entity_id: str = Field(min_length=1)
    hypotheses: tuple[Hypothesis, ...] = ()
    cost: TaskCost = TaskCost()


@runtime_checkable
class TaskRunner(Protocol):
    """Runs a high-level research task scoped to a single library."""

    async def run(
        self,
        library_id: str,
        task_input: object,
    ) -> object: ...
