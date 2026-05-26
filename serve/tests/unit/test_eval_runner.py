"""Tests for DefaultEvalRunner + JSONFileRunsStore (M6.1)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from packages.evaluation.protocols import (
    EvalSample,
    Metric,
    MetricScore,
    SampleLoader,
)
from packages.evaluation.runner import DefaultEvalRunner, EvalRunnerConfig
from packages.evaluation.runs_store import JSONFileRunsStore
from packages.orchestration.protocols import AnsweredQuery, TokenUsage
from packages.orchestration.tasks.qa_task import QATask


def _sample(sample_id: str = "q-1", floor: float = 0.5) -> EvalSample:
    return EvalSample(
        sample_id=sample_id,
        library_id="lib-x",
        suite="qa.smoke",
        suite_version="v1",
        question=f"question for {sample_id}",
        expected_evidence_doc_ids=("doc-001",),
        acceptable_score_floor=floor,
    )


def _answered(library_id: str = "lib-x", question: str = "q") -> AnsweredQuery:
    return AnsweredQuery(
        library_id=library_id,
        question=question,
        answer="some answer",
        tokens=TokenUsage(input_tokens=5, output_tokens=2, cost_usd=0.001),
    )


class StaticLoader:
    def __init__(self, samples: list[EvalSample]) -> None:
        self._samples = samples
        self.calls: list[tuple[str, str, str]] = []

    def load_suite(self, library_id: str, suite: str, version: str) -> list[EvalSample]:
        self.calls.append((library_id, suite, version))
        return list(self._samples)


class FakeQATask:
    """Minimal QA task substitute. Returns canned answers or raises."""

    def __init__(
        self,
        *,
        canned: AnsweredQuery | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._canned = canned
        self._raise = raise_exc
        self.calls: list[tuple[str, str]] = []

    async def answer(self, library_id: str, question: str) -> AnsweredQuery:
        self.calls.append((library_id, question))
        if self._raise is not None:
            raise self._raise
        if self._canned is not None:
            return self._canned
        return _answered(library_id, question)


class FixedScoreMetric:
    def __init__(
        self,
        *,
        name: str,
        score: float,
        cost_usd: float = 0.0,
        requires_judge: bool = False,
    ) -> None:
        self._name = name
        self._score = score
        self._cost = cost_usd
        self._requires_judge = requires_judge

    @property
    def name(self) -> str:
        return self._name

    @property
    def requires_judge(self) -> bool:
        return self._requires_judge

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        return MetricScore(
            metric_name=self._name,
            score=self._score,
            cost_usd=self._cost,
        )


class ExplodingMetric:
    @property
    def name(self) -> str:
        return "explodes"

    @property
    def requires_judge(self) -> bool:
        return False

    async def score(self, sample: EvalSample, answered: AnsweredQuery) -> MetricScore:
        raise RuntimeError("kaboom")


def _runner(
    *,
    qa_task: FakeQATask,
    samples: list[EvalSample],
    metrics: list[Metric],
    config: EvalRunnerConfig | None = None,
) -> DefaultEvalRunner:
    loader: SampleLoader = StaticLoader(samples)
    return DefaultEvalRunner(
        qa_task=cast(QATask, qa_task),
        loader=loader,
        metrics=metrics,
        config=config,
    )


class TestDefaultEvalRunnerHappyPath:
    @pytest.mark.asyncio
    async def test_aggregates_metric_averages_and_pass_count(self) -> None:
        # Arrange
        samples = [_sample("q-1", floor=0.5), _sample("q-2", floor=0.9)]
        qa = FakeQATask()
        metrics: list[Metric] = [
            FixedScoreMetric(name="faithfulness", score=0.8, cost_usd=0.01),
            FixedScoreMetric(name="recall", score=0.6),
        ]
        runner = _runner(qa_task=qa, samples=samples, metrics=metrics)

        # Act
        run = await runner.run_suite("lib-x", "qa.smoke", "v1")

        # Assert
        assert run.summary.total == 2
        # composite = (0.8 + 0.6) / 2 = 0.7
        # q-1 floor 0.5 → passed; q-2 floor 0.9 → failed
        assert run.summary.passed == 1
        assert run.summary.errors == 0
        assert run.summary.avg_metrics["faithfulness"] == pytest.approx(0.8)
        assert run.summary.avg_metrics["recall"] == pytest.approx(0.6)
        assert run.summary.avg_composite == pytest.approx(0.7)
        # 2 samples * 0.01 metric cost + 2 * 0.001 answer cost = 0.022
        assert run.summary.total_cost_usd == pytest.approx(0.022)
        assert len(run.results) == 2
        assert qa.calls == [
            ("lib-x", "question for q-1"),
            ("lib-x", "question for q-2"),
        ]

    @pytest.mark.asyncio
    async def test_fail_on_floor_disabled_passes_all(self) -> None:
        samples = [_sample("q-1", floor=0.99)]
        qa = FakeQATask()
        metrics: list[Metric] = [FixedScoreMetric(name="m", score=0.1)]
        runner = _runner(
            qa_task=qa,
            samples=samples,
            metrics=metrics,
            config=EvalRunnerConfig(fail_on_floor=False),
        )

        run = await runner.run_suite("lib-x", "qa.smoke", "v1")

        assert run.summary.passed == 1
        assert run.results[0].passed is True

    @pytest.mark.asyncio
    async def test_judge_metrics_skipped_when_disabled(self) -> None:
        samples = [_sample("q-1")]
        qa = FakeQATask()
        metrics: list[Metric] = [
            FixedScoreMetric(name="judge", score=1.0, requires_judge=True),
            FixedScoreMetric(name="det", score=0.5),
        ]
        runner = _runner(
            qa_task=qa,
            samples=samples,
            metrics=metrics,
            config=EvalRunnerConfig(llm_judge_enabled=False),
        )

        run = await runner.run_suite("lib-x", "qa.smoke", "v1")

        applied = {m.metric_name for m in run.results[0].metrics}
        assert applied == {"det"}


class TestDefaultEvalRunnerErrorHandling:
    @pytest.mark.asyncio
    async def test_qa_failure_records_sample_error(self) -> None:
        samples = [_sample("q-1")]
        qa = FakeQATask(raise_exc=RuntimeError("LLM down"))
        metrics: list[Metric] = [FixedScoreMetric(name="m", score=1.0)]
        runner = _runner(qa_task=qa, samples=samples, metrics=metrics)

        run = await runner.run_suite("lib-x", "qa.smoke", "v1")

        assert run.summary.total == 1
        assert run.summary.errors == 1
        assert run.summary.passed == 0
        result = run.results[0]
        assert result.answered is None
        assert result.composite_score == 0.0
        assert result.passed is False
        assert result.error is not None
        assert "LLM down" in result.error
        assert result.metrics == ()

    @pytest.mark.asyncio
    async def test_metric_failure_recorded_run_continues(self) -> None:
        samples = [_sample("q-1", floor=0.4)]
        qa = FakeQATask()
        metrics: list[Metric] = [
            FixedScoreMetric(name="ok", score=1.0),
            ExplodingMetric(),
        ]
        runner = _runner(qa_task=qa, samples=samples, metrics=metrics)

        run = await runner.run_suite("lib-x", "qa.smoke", "v1")

        result = run.results[0]
        assert result.error is None  # whole sample didn't fail
        scores = {m.metric_name: m for m in result.metrics}
        assert scores["ok"].score == 1.0
        assert scores["ok"].error is None
        assert scores["explodes"].score == 0.0
        assert scores["explodes"].error is not None
        # composite = (1.0 + 0.0) / 2 = 0.5 >= 0.4 floor
        assert result.composite_score == pytest.approx(0.5)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_no_metrics_yields_zero_composite(self) -> None:
        samples = [_sample("q-1", floor=0.0)]
        qa = FakeQATask()
        runner = _runner(qa_task=qa, samples=samples, metrics=[])

        run = await runner.run_suite("lib-x", "qa.smoke", "v1")

        assert run.results[0].composite_score == 0.0
        # floor=0.0, composite=0.0 → passes (0.0 >= 0.0)
        assert run.results[0].passed is True


class TestJSONFileRunsStore:
    @pytest.mark.asyncio
    async def test_save_then_list_recent_round_trip(self, tmp_path: Path) -> None:
        samples = [_sample("q-1"), _sample("q-2")]
        qa = FakeQATask()
        metrics: list[Metric] = [FixedScoreMetric(name="m", score=0.9)]
        runner = _runner(qa_task=qa, samples=samples, metrics=metrics)
        run = await runner.run_suite("lib-x", "qa.smoke", "v1")
        store = JSONFileRunsStore(data_dir=tmp_path)

        # Act
        path = await store.save(run)
        recent = await store.list_recent("lib-x", limit=10)

        # Assert
        assert path.exists()
        assert path.name == "eval_runs.jsonl"
        assert len(recent) == 1
        assert recent[0].run_id == run.summary.run_id
        assert recent[0].avg_composite == pytest.approx(0.9)

    @pytest.mark.asyncio
    async def test_list_recent_limit_returns_tail(self, tmp_path: Path) -> None:
        store = JSONFileRunsStore(data_dir=tmp_path)
        qa = FakeQATask()
        metrics: list[Metric] = [FixedScoreMetric(name="m", score=0.5)]

        for sid in ("q-1", "q-2", "q-3"):
            runner = _runner(qa_task=qa, samples=[_sample(sid)], metrics=metrics)
            run = await runner.run_suite("lib-x", "qa.smoke", "v1")
            await store.save(run)

        recent = await store.list_recent("lib-x", limit=2)

        assert len(recent) == 2  # only the last 2 runs

    @pytest.mark.asyncio
    async def test_list_recent_missing_file_returns_empty(self, tmp_path: Path) -> None:
        store = JSONFileRunsStore(data_dir=tmp_path)

        recent = await store.list_recent("never-existed", limit=5)

        assert recent == []
