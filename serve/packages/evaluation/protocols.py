"""Evaluation subsystem protocol definitions.

Evaluation is a terminal package — nothing imports it.
It calls L5 orchestration as a normal client (走正门).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.orchestration.protocols import AnsweredQuery


class EvalSample(BaseModel):
    """A single evaluation sample (one question + expected outcome)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str = Field(min_length=1)
    library_id: str = Field(min_length=1)
    suite: str = Field(min_length=1)
    suite_version: str = Field(min_length=1)
    question: str | None = None
    expected_evidence_doc_ids: tuple[str, ...] = ()
    expected_key_points: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    type: Literal["single-hop", "multi-hop", "global", "definition"] = "single-hop"
    acceptable_score_floor: float = Field(default=0.7, ge=0.0, le=1.0)
    human_validated: bool = False


class MetricScore(BaseModel):
    """Result of scoring one metric on one sample."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_name: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    judge_model: str | None = None
    cost_usd: float = Field(default=0.0, ge=0.0)
    details: Mapping[str, object] = Field(default_factory=dict)
    error: str | None = None


class SampleResult(BaseModel):
    """Per-sample full result: AnsweredQuery + all metric scores + pass flag."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str = Field(min_length=1)
    answered: AnsweredQuery | None = None
    metrics: tuple[MetricScore, ...] = ()
    composite_score: float = 0.0
    passed: bool = False
    duration_ms: int = 0
    error: str | None = None


class RunSummary(BaseModel):
    """Aggregate summary of one eval run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID
    library_id: str = Field(min_length=1)
    suite: str
    suite_version: str
    total: int = 0
    passed: int = 0
    errors: int = 0
    avg_metrics: Mapping[str, float] = Field(default_factory=dict)
    avg_composite: float = 0.0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    started_at: datetime
    finished_at: datetime | None = None


class EvalRun(BaseModel):
    """Full eval run: summary + per-sample results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: RunSummary
    results: tuple[SampleResult, ...] = ()


@runtime_checkable
class SampleLoader(Protocol):
    """Load eval samples from disk."""

    def load_suite(self, library_id: str, suite: str, version: str) -> list[EvalSample]: ...


@runtime_checkable
class Metric(Protocol):
    """A single eval metric."""

    @property
    def name(self) -> str: ...

    @property
    def requires_judge(self) -> bool: ...

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore: ...


@runtime_checkable
class EvalRunner(Protocol):
    """Top-level eval orchestrator."""

    async def run_suite(
        self,
        library_id: str,
        suite: str,
        version: str = "v1",
    ) -> EvalRun: ...
