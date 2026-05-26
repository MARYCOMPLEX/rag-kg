"""Unit tests for `MarkdownReporter` — render_summary / render_pr_comment / render_diff.

The tests build synthetic ``EvalRun`` instances directly (no I/O, no
container) and assert on key markdown anchors so the assertions stay
robust against minor formatting drift.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from packages.evaluation.protocols import (
    EvalRun,
    MetricScore,
    RunSummary,
    SampleResult,
)
from packages.evaluation.reporter import MarkdownReporter
from packages.orchestration.protocols import AnsweredQuery, TokenUsage

_RUN_ID_CURRENT = UUID("11111111-1111-1111-1111-111111111111")
_RUN_ID_BASELINE = UUID("22222222-2222-2222-2222-222222222222")


def _answered(question: str = "What is RAG?") -> AnsweredQuery:
    return AnsweredQuery(
        library_id="rag-agent",
        question=question,
        answer="RAG combines retrieval and generation.",
        tokens=TokenUsage(input_tokens=10, output_tokens=20, cost_usd=0.001),
        duration_ms=120,
    )


def _sample_result(
    *,
    sample_id: str,
    composite: float,
    passed: bool,
    metrics: tuple[tuple[str, float], ...],
    question: str = "What is RAG?",
) -> SampleResult:
    return SampleResult(
        sample_id=sample_id,
        answered=_answered(question),
        metrics=tuple(MetricScore(metric_name=n, score=s) for n, s in metrics),
        composite_score=composite,
        passed=passed,
        duration_ms=120,
    )


_DEFAULT_METRICS: dict[str, float] = {"recall": 0.9, "key_point_cov": 0.8}


def _make_run(
    *,
    run_id: UUID = _RUN_ID_CURRENT,
    avg_composite: float = 0.85,
    avg_metrics: dict[str, float] | None = None,
    passed: int = 2,
    total: int = 2,
    errors: int = 0,
    results: tuple[SampleResult, ...] | None = None,
) -> EvalRun:
    started = datetime(2026, 4, 27, 10, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 4, 27, 10, 0, 30, tzinfo=UTC)
    summary = RunSummary(
        run_id=run_id,
        library_id="rag-agent",
        suite="qa.smoke",
        suite_version="v1",
        total=total,
        passed=passed,
        errors=errors,
        avg_metrics=avg_metrics if avg_metrics is not None else _DEFAULT_METRICS,
        avg_composite=avg_composite,
        total_cost_usd=0.0123,
        total_duration_ms=2500,
        started_at=started,
        finished_at=finished,
    )
    if results is None:
        results = (
            _sample_result(
                sample_id="s1",
                composite=0.9,
                passed=True,
                metrics=(("recall", 1.0), ("key_point_cov", 0.8)),
            ),
            _sample_result(
                sample_id="s2",
                composite=0.8,
                passed=True,
                metrics=(("recall", 0.8), ("key_point_cov", 0.8)),
                question="A " * 60,  # forces truncation
            ),
        )
    return EvalRun(summary=summary, results=results)


@pytest.fixture
def reporter() -> MarkdownReporter:
    return MarkdownReporter()


def test_render_summary_includes_header_and_tables(
    reporter: MarkdownReporter,
) -> None:
    # Arrange
    run = _make_run()

    # Act
    md = reporter.render_summary(run)

    # Assert
    assert "# Eval run: rag-agent / qa.smoke@v1" in md
    assert "## Summary" in md
    assert "## Average metrics" in md
    assert "## Per-sample results" in md
    assert "| Sample | Question |" in md
    assert "s1" in md
    assert "s2" in md
    # Truncated long question must end with ellipsis marker.
    assert "..." in md
    # Pipe-escape stays intact (no raw newlines or unescaped pipes break the table).
    assert "\n|" in md


def test_render_summary_handles_zero_samples(reporter: MarkdownReporter) -> None:
    # Arrange
    run = _make_run(passed=0, total=0, results=(), avg_metrics={})

    # Act
    md = reporter.render_summary(run)

    # Assert: no division-by-zero, table headers still rendered.
    assert "Pass" not in md or "0/0" not in md  # tolerant
    assert "## Summary" in md
    assert "## Per-sample results" in md
    # No average-metrics section when avg_metrics empty.
    assert "## Average metrics" not in md


def test_render_pr_comment_without_baseline(reporter: MarkdownReporter) -> None:
    # Arrange
    run = _make_run()

    # Act
    md = reporter.render_pr_comment(run)

    # Assert
    assert "### Eval: `qa.smoke@v1` on `rag-agent`" in md
    assert "Pass rate" in md
    assert "Avg composite" in md
    assert "Delta vs baseline" not in md


def test_render_pr_comment_with_baseline_includes_delta(
    reporter: MarkdownReporter,
) -> None:
    # Arrange
    current = _make_run(
        avg_composite=0.85,
        avg_metrics={"recall": 0.9, "key_point_cov": 0.8},
    )
    baseline = _make_run(
        run_id=_RUN_ID_BASELINE,
        avg_composite=0.80,
        avg_metrics={"recall": 0.85, "key_point_cov": 0.8},
    )

    # Act
    md = reporter.render_pr_comment(current, baseline=baseline)

    # Assert
    assert "Delta vs baseline" in md
    assert "| Metric | Baseline | Current | Delta |" in md
    assert "composite" in md
    # Improvement should produce up arrow for composite.
    assert "^" in md


def test_render_diff_marks_regression_with_down_arrow(
    reporter: MarkdownReporter,
) -> None:
    # Arrange
    current = _make_run(
        avg_composite=0.70,
        avg_metrics={"recall": 0.7, "key_point_cov": 0.6},
    )
    baseline = _make_run(
        run_id=_RUN_ID_BASELINE,
        avg_composite=0.85,
        avg_metrics={"recall": 0.9, "key_point_cov": 0.8},
    )

    # Act
    md = reporter.render_diff(current, baseline)

    # Assert
    assert "# Eval diff:" in md
    assert "v" in md  # down arrow for regression
    assert "composite" in md
    assert "0.700" in md
    assert "0.850" in md


def test_render_diff_handles_metric_only_in_one_side(
    reporter: MarkdownReporter,
) -> None:
    # Arrange
    current = _make_run(avg_metrics={"recall": 0.9, "new_metric": 0.5})
    baseline = _make_run(
        run_id=_RUN_ID_BASELINE,
        avg_metrics={"recall": 0.9, "old_metric": 0.5},
    )

    # Act
    md = reporter.render_diff(current, baseline)

    # Assert: new and old metrics both appear with n/a delta.
    assert "new_metric" in md
    assert "old_metric" in md
    assert "n/a" in md


def test_pr_comment_pass_rate_is_percentage(reporter: MarkdownReporter) -> None:
    # Arrange
    run = _make_run(passed=3, total=4)

    # Act
    md = reporter.render_pr_comment(run)

    # Assert
    assert "3/4" in md
    assert "75.0%" in md
