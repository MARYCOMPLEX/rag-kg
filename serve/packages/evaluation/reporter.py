"""Markdown report rendering for eval runs.

Pure rendering — no I/O, no network. Functions accept ``EvalRun`` (and
optional baseline) and return plain markdown strings suitable for stdout
display, CI logs, or PR comments.

The ``MarkdownReporter`` is intentionally stateless and exposes three
formatting entry points:

- :py:meth:`MarkdownReporter.render_summary` — full report (summary + per-sample tables)
- :py:meth:`MarkdownReporter.render_pr_comment` — concise PR comment with delta vs baseline
- :py:meth:`MarkdownReporter.render_diff` — markdown diff of two runs (per-metric arrows)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from packages.evaluation.protocols import EvalRun, SampleResult

# Symbols used in delta tables — kept ASCII to avoid encoding issues in CI logs.
_ARROW_UP: Final[str] = "^"
_ARROW_DOWN: Final[str] = "v"
_ARROW_FLAT: Final[str] = "-"

# Delta below this absolute value is treated as flat / not significant.
_DELTA_FLAT_THRESHOLD: Final[float] = 1e-4

# Truncate long question text in tables to keep markdown readable.
_QUESTION_TRUNCATE: Final[int] = 80


def _truncate(text: str | None, limit: int = _QUESTION_TRUNCATE) -> str:
    """Truncate ``text`` to ``limit`` chars (markdown-safe; pipes escaped)."""
    if text is None:
        return ""
    cleaned = text.replace("|", "\\|").replace("\n", " ").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "..."


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_score(value: float) -> str:
    return f"{value:.3f}"


def _delta_arrow(delta: float) -> str:
    if delta > _DELTA_FLAT_THRESHOLD:
        return _ARROW_UP
    if delta < -_DELTA_FLAT_THRESHOLD:
        return _ARROW_DOWN
    return _ARROW_FLAT


def _fmt_delta(delta: float) -> str:
    arrow = _delta_arrow(delta)
    if arrow == _ARROW_FLAT:
        return f"{arrow} 0.000"
    sign = "+" if delta > 0 else ""
    return f"{arrow} {sign}{delta:.3f}"


def _build_summary_rows(run: EvalRun) -> list[tuple[str, str]]:
    summary = run.summary
    pass_rate = summary.passed / summary.total if summary.total else 0.0
    rows: list[tuple[str, str]] = [
        ("Library", summary.library_id),
        ("Suite", f"{summary.suite} / {summary.suite_version}"),
        ("Run ID", str(summary.run_id)),
        ("Total samples", str(summary.total)),
        ("Passed", f"{summary.passed} ({_fmt_pct(pass_rate)})"),
        ("Errors", str(summary.errors)),
        ("Avg composite", _fmt_score(summary.avg_composite)),
        ("Total cost (USD)", f"${summary.total_cost_usd:.4f}"),
        ("Total duration", f"{summary.total_duration_ms / 1000:.1f}s"),
        ("Started", summary.started_at.isoformat()),
    ]
    if summary.finished_at is not None:
        rows.append(("Finished", summary.finished_at.isoformat()))
    return rows


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a basic GitHub-flavored markdown table."""
    if not headers:
        return ""
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    if not rows:
        return f"{head}\n{sep}"
    return f"{head}\n{sep}\n{body}"


def _metric_score_map(result: SampleResult) -> Mapping[str, float]:
    return {m.metric_name: m.score for m in result.metrics}


def _all_metric_names(run: EvalRun) -> list[str]:
    seen: dict[str, None] = {}
    for r in run.results:
        for m in r.metrics:
            seen.setdefault(m.metric_name, None)
    # Stable, deterministic ordering — alphabetical.
    return sorted(seen.keys())


def _render_per_sample_table(run: EvalRun) -> str:
    metric_names = _all_metric_names(run)
    headers = ["Sample", "Question", "Composite", "Passed", *metric_names, "Duration (ms)"]
    rows: list[list[str]] = []
    for r in run.results:
        question = r.answered.question if r.answered is not None else None
        scores = _metric_score_map(r)
        row = [
            r.sample_id,
            _truncate(question),
            _fmt_score(r.composite_score),
            "yes" if r.passed else "no",
        ]
        row.extend(_fmt_score(scores[m]) if m in scores else "-" for m in metric_names)
        row.append(str(r.duration_ms))
        rows.append(row)
    return _markdown_table(headers, rows)


def _render_summary_table(run: EvalRun) -> str:
    rows = [[k, v] for k, v in _build_summary_rows(run)]
    return _markdown_table(["Field", "Value"], rows)


def _render_metric_averages_table(run: EvalRun) -> str:
    avg = dict(run.summary.avg_metrics)
    if not avg:
        return ""
    rows = [[name, _fmt_score(score)] for name, score in sorted(avg.items())]
    return _markdown_table(["Metric", "Average"], rows)


def _render_diff_table(current: EvalRun, baseline: EvalRun) -> str:
    cur = dict(current.summary.avg_metrics)
    base = dict(baseline.summary.avg_metrics)
    metric_names = sorted(set(cur) | set(base))

    rows: list[list[str]] = []
    for name in metric_names:
        cur_score = cur.get(name)
        base_score = base.get(name)
        if cur_score is None or base_score is None:
            cur_str = _fmt_score(cur_score) if cur_score is not None else "-"
            base_str = _fmt_score(base_score) if base_score is not None else "-"
            rows.append([name, base_str, cur_str, "n/a"])
            continue
        rows.append(
            [
                name,
                _fmt_score(base_score),
                _fmt_score(cur_score),
                _fmt_delta(cur_score - base_score),
            ]
        )

    composite_delta = current.summary.avg_composite - baseline.summary.avg_composite
    rows.append(
        [
            "composite",
            _fmt_score(baseline.summary.avg_composite),
            _fmt_score(current.summary.avg_composite),
            _fmt_delta(composite_delta),
        ]
    )
    return _markdown_table(["Metric", "Baseline", "Current", "Delta"], rows)


class MarkdownReporter:
    """Render eval runs as plain markdown strings.

    Stateless — every method is a pure function of its inputs. Safe to
    construct once at module level and reuse.
    """

    def render_summary(self, run: EvalRun) -> str:
        """Full markdown report: header + summary table + per-sample table."""
        summary = run.summary
        title = f"# Eval run: {summary.library_id} / {summary.suite}@{summary.suite_version}"
        sections: list[str] = [
            title,
            "",
            "## Summary",
            "",
            _render_summary_table(run),
        ]
        metric_table = _render_metric_averages_table(run)
        if metric_table:
            sections.extend(["", "## Average metrics", "", metric_table])
        sections.extend(
            [
                "",
                "## Per-sample results",
                "",
                _render_per_sample_table(run),
                "",
            ]
        )
        return "\n".join(sections)

    def render_pr_comment(self, run: EvalRun, baseline: EvalRun | None = None) -> str:
        """Concise PR comment: headline + brief averages + delta if baseline."""
        summary = run.summary
        pass_rate = summary.passed / summary.total if summary.total else 0.0
        lines: list[str] = [
            f"### Eval: `{summary.suite}@{summary.suite_version}` on `{summary.library_id}`",
            "",
            (f"- Pass rate: **{summary.passed}/{summary.total}** ({_fmt_pct(pass_rate)})"),
            f"- Avg composite: **{_fmt_score(summary.avg_composite)}**",
            f"- Errors: {summary.errors}",
            f"- Duration: {summary.total_duration_ms / 1000:.1f}s",
            f"- Cost: ${summary.total_cost_usd:.4f}",
        ]
        if baseline is not None:
            lines.extend(
                [
                    "",
                    "#### Delta vs baseline",
                    "",
                    _render_diff_table(run, baseline),
                ]
            )
        lines.append("")
        return "\n".join(lines)

    def render_diff(self, current: EvalRun, baseline: EvalRun) -> str:
        """Markdown diff between two runs — per-metric averages with arrows."""
        cur = current.summary
        base = baseline.summary
        header = (
            f"# Eval diff: `{cur.suite}@{cur.suite_version}` "
            f"(current `{cur.run_id}` vs baseline `{base.run_id}`)"
        )
        return "\n".join(
            [
                header,
                "",
                _render_diff_table(current, baseline),
                "",
            ]
        )
