"""Default eval runner — orchestrates sample loading, QA, and metric scoring.

The runner depends on QATask (L5 orchestration), a SampleLoader, and an
ordered list of Metric implementations. It produces an immutable EvalRun
that downstream consumers (CLI, runs store) can serialize.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final
from uuid import UUID, uuid4

from packages.evaluation.protocols import (
    EvalRun,
    EvalSample,
    Metric,
    MetricScore,
    RunSummary,
    SampleLoader,
    SampleResult,
)
from packages.orchestration.protocols import AnsweredQuery
from packages.orchestration.tasks.qa_task import QATask

_ZERO_SCORE: Final[float] = 0.0


@dataclass(frozen=True)
class EvalRunnerConfig:
    """Tunable knobs for the default runner."""

    parallelism: int = 4
    llm_judge_enabled: bool = True
    fail_on_floor: bool = True


class DefaultEvalRunner:
    """`EvalRunner` Protocol impl with bounded concurrency and metric isolation."""

    def __init__(
        self,
        *,
        qa_task: QATask,
        loader: SampleLoader,
        metrics: list[Metric],
        config: EvalRunnerConfig | None = None,
    ) -> None:
        self._qa_task = qa_task
        self._loader = loader
        self._metrics = tuple(metrics)
        self._config = config if config is not None else EvalRunnerConfig()

    async def run_suite(self, library_id: str, suite: str, version: str = "v1") -> EvalRun:
        run_id = uuid4()
        started_at = datetime.now(UTC)
        run_started_perf = time.perf_counter()

        samples = self._loader.load_suite(library_id, suite, version)
        results = await self._evaluate_samples(samples)

        finished_at = datetime.now(UTC)
        total_duration_ms = int((time.perf_counter() - run_started_perf) * 1000)

        summary = self._summarize(
            run_id=run_id,
            library_id=library_id,
            suite=suite,
            suite_version=version,
            results=results,
            started_at=started_at,
            finished_at=finished_at,
            total_duration_ms=total_duration_ms,
        )

        return EvalRun(summary=summary, results=tuple(results))

    # --- internals ---------------------------------------------------------

    async def _evaluate_samples(self, samples: Sequence[EvalSample]) -> list[SampleResult]:
        if not samples:
            return []
        semaphore = asyncio.Semaphore(max(1, self._config.parallelism))

        async def _bounded(sample: EvalSample) -> SampleResult:
            async with semaphore:
                return await self._evaluate_single(sample)

        return list(await asyncio.gather(*(_bounded(s) for s in samples)))

    async def _evaluate_single(self, sample: EvalSample) -> SampleResult:
        sample_started = time.perf_counter()
        question = sample.question or ""

        try:
            answered = await self._qa_task.answer(sample.library_id, question)
        except Exception as exc:  # convert any QA failure into a recorded result
            duration_ms = int((time.perf_counter() - sample_started) * 1000)
            return SampleResult(
                sample_id=sample.sample_id,
                answered=None,
                metrics=(),
                composite_score=_ZERO_SCORE,
                passed=False,
                duration_ms=duration_ms,
                error=f"qa_task failed: {exc}",
            )

        metric_scores = await self._score_metrics(sample, answered)
        composite = _composite_score(metric_scores)
        passed = self._is_passing(composite, sample.acceptable_score_floor)
        duration_ms = int((time.perf_counter() - sample_started) * 1000)

        return SampleResult(
            sample_id=sample.sample_id,
            answered=answered,
            metrics=tuple(metric_scores),
            composite_score=composite,
            passed=passed,
            duration_ms=duration_ms,
            error=None,
        )

    async def _score_metrics(
        self, sample: EvalSample, answered: AnsweredQuery
    ) -> list[MetricScore]:
        scores: list[MetricScore] = []
        for metric in self._metrics:
            if metric.requires_judge and not self._config.llm_judge_enabled:
                continue
            scores.append(await _run_one_metric(metric, sample, answered))
        return scores

    def _is_passing(self, composite: float, floor: float) -> bool:
        if not self._config.fail_on_floor:
            return True
        return composite >= floor

    def _summarize(
        self,
        *,
        run_id: UUID,
        library_id: str,
        suite: str,
        suite_version: str,
        results: Sequence[SampleResult],
        started_at: datetime,
        finished_at: datetime,
        total_duration_ms: int,
    ) -> RunSummary:
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        errors = sum(1 for r in results if r.error is not None)
        avg_metrics = _average_per_metric(results)
        avg_composite = sum(r.composite_score for r in results) / total if total else _ZERO_SCORE
        total_cost_usd = _sum_metric_cost(results) + _sum_answer_cost(results)

        return RunSummary(
            run_id=run_id,
            library_id=library_id,
            suite=suite,
            suite_version=suite_version,
            total=total,
            passed=passed,
            errors=errors,
            avg_metrics=avg_metrics,
            avg_composite=avg_composite,
            total_cost_usd=total_cost_usd,
            total_duration_ms=total_duration_ms,
            started_at=started_at,
            finished_at=finished_at,
        )


async def _run_one_metric(
    metric: Metric, sample: EvalSample, answered: AnsweredQuery
) -> MetricScore:
    try:
        return await metric.score(sample, answered)
    except Exception as exc:  # record metric failure, do not crash whole run
        return MetricScore(
            metric_name=metric.name,
            score=_ZERO_SCORE,
            error=f"metric failed: {exc}",
        )


def _composite_score(metric_scores: Sequence[MetricScore]) -> float:
    if not metric_scores:
        return _ZERO_SCORE
    return sum(m.score for m in metric_scores) / len(metric_scores)


def _average_per_metric(results: Sequence[SampleResult]) -> dict[str, float]:
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for result in results:
        for metric in result.metrics:
            sums[metric.metric_name] = sums.get(metric.metric_name, 0.0) + metric.score
            counts[metric.metric_name] = counts.get(metric.metric_name, 0) + 1
    return {name: sums[name] / counts[name] for name in sums}


def _sum_metric_cost(results: Sequence[SampleResult]) -> float:
    return sum(metric.cost_usd for r in results for metric in r.metrics)


def _sum_answer_cost(results: Sequence[SampleResult]) -> float:
    return sum(r.answered.tokens.cost_usd for r in results if r.answered is not None)


__all__ = ["DefaultEvalRunner", "EvalRunnerConfig"]
