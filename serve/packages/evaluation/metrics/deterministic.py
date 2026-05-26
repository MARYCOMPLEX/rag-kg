"""Deterministic, LLM-free evaluation metrics.

These metrics are fast, cheap, and reproducible. They check surface-level
properties of an answer without needing a judge model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from packages.evaluation.protocols import EvalSample, MetricScore
from packages.orchestration.protocols import AnsweredQuery

_CITATION_RE = re.compile(r"\[[a-zA-Z0-9:_\-/.]+\]")

_DEFAULT_LATENCY_TARGET_MS = 30_000
_LATENCY_DECAY_FACTOR = 3


def _retrieved_doc_ids(answered: AnsweredQuery) -> set[str]:
    """Collect doc_ids of retrieved evidence (chunk-level)."""
    return {ev.chunk.doc_id for ev in answered.retrieved}


class RecallAtKMetric:
    """Fraction of expected evidence doc_ids present in retrieved set."""

    @property
    def name(self) -> str:
        return "recall_at_k"

    @property
    def requires_judge(self) -> bool:
        return False

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        expected = sample.expected_evidence_doc_ids
        if not expected:
            return MetricScore(
                metric_name=self.name,
                score=1.0,
                details={"expected": 0, "matched": 0},
            )
        retrieved = _retrieved_doc_ids(answered)
        matched = sum(1 for d in expected if d in retrieved)
        score_value = matched / len(expected)
        return MetricScore(
            metric_name=self.name,
            score=score_value,
            details={
                "expected": len(expected),
                "matched": matched,
                "retrieved_count": len(retrieved),
            },
        )


class KeyPointCoverageMetric:
    """Fraction of expected key-point substrings appearing in the answer."""

    @property
    def name(self) -> str:
        return "key_point_coverage"

    @property
    def requires_judge(self) -> bool:
        return False

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        expected = sample.expected_key_points
        if not expected:
            return MetricScore(
                metric_name=self.name,
                score=1.0,
                details={"expected": 0, "matched": 0},
            )
        answer_lower = answered.answer.lower()
        matched_terms = [kp for kp in expected if kp.lower() in answer_lower]
        score_value = len(matched_terms) / len(expected)
        return MetricScore(
            metric_name=self.name,
            score=score_value,
            details={
                "expected": len(expected),
                "matched": len(matched_terms),
                "missing": tuple(kp for kp in expected if kp not in matched_terms),
            },
        )


class CitationPresentMetric:
    """1.0 if the answer contains at least one [chunk_id]-style marker."""

    @property
    def name(self) -> str:
        return "citation_present"

    @property
    def requires_judge(self) -> bool:
        return False

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        del sample
        matches = _CITATION_RE.findall(answered.answer)
        present = len(matches) > 0
        return MetricScore(
            metric_name=self.name,
            score=1.0 if present else 0.0,
            details={"citation_count": len(matches)},
        )


class MustNotContainMetric:
    """1.0 if no forbidden substring is present in the answer."""

    @property
    def name(self) -> str:
        return "must_not_contain"

    @property
    def requires_judge(self) -> bool:
        return False

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        forbidden = sample.must_not_contain
        if not forbidden:
            return MetricScore(
                metric_name=self.name,
                score=1.0,
                details={"forbidden_count": 0, "violations": ()},
            )
        answer_lower = answered.answer.lower()
        violations = tuple(p for p in forbidden if p.lower() in answer_lower)
        return MetricScore(
            metric_name=self.name,
            score=0.0 if violations else 1.0,
            details={
                "forbidden_count": len(forbidden),
                "violations": violations,
            },
        )


@dataclass(frozen=True, slots=True)
class LatencyConfig:
    """Configuration for the LatencyMetric."""

    target_ms: int = _DEFAULT_LATENCY_TARGET_MS
    decay_factor: int = _LATENCY_DECAY_FACTOR


class LatencyMetric:
    """1.0 if duration <= target_ms, linearly decays to 0 by decay_factor*target.

    Score formula:
        d = answered.duration_ms
        if d <= target_ms: 1.0
        if d >= decay_factor * target_ms: 0.0
        else: linear interpolation in between.
    """

    def __init__(
        self,
        target_ms: int = _DEFAULT_LATENCY_TARGET_MS,
        config: LatencyConfig | None = None,
    ) -> None:
        if config is not None:
            self._config = config
        else:
            self._config = LatencyConfig(target_ms=target_ms)

    @property
    def name(self) -> str:
        return "latency"

    @property
    def requires_judge(self) -> bool:
        return False

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        del sample
        target = self._config.target_ms
        decay = self._config.decay_factor
        duration = answered.duration_ms
        upper = target * decay
        if duration <= target:
            score_value = 1.0
        elif duration >= upper:
            score_value = 0.0
        else:
            # linear decay from 1 at target_ms to 0 at decay*target_ms
            score_value = 1.0 - (duration - target) / max(1, upper - target)
            score_value = max(0.0, min(1.0, score_value))
        return MetricScore(
            metric_name=self.name,
            score=score_value,
            details={
                "duration_ms": duration,
                "target_ms": target,
                "upper_ms": upper,
            },
        )
