"""CI gate — fail non-zero when an eval run regresses vs a baseline.

Loads two eval-run JSON files (current + baseline), computes per-metric
deltas, and exits ``1`` if any of the gated metrics drops by more than
``--max-regression``. Prints a markdown diff via :class:`MarkdownReporter`.

Usage::

    uv run python scripts/eval_gate.py \\
        --library rag-agent --suite qa.smoke \\
        --current-run runs/current.json \\
        --baseline-run runs/baseline.json \\
        --max-regression 0.05 \\
        --fail-on composite,faithfulness
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

from rich.console import Console

from packages.evaluation.protocols import EvalRun
from packages.evaluation.reporter import MarkdownReporter

_console: Final[Console] = Console()

_DEFAULT_MAX_REGRESSION: Final[float] = 0.05
_DEFAULT_FAIL_ON: Final[str] = "composite"

_EXIT_OK: Final[int] = 0
_EXIT_REGRESSION: Final[int] = 1
_EXIT_BAD_INPUT: Final[int] = 2


def _load_run(path: Path) -> EvalRun:
    if not path.exists():
        msg = f"Run JSON not found: {path}"
        raise FileNotFoundError(msg)
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return EvalRun.model_validate(payload)


def _metric_value(run: EvalRun, name: str) -> float | None:
    if name == "composite":
        return run.summary.avg_composite
    return run.summary.avg_metrics.get(name)


def _parse_fail_on(raw: str) -> list[str]:
    metrics = [m.strip() for m in raw.split(",") if m.strip()]
    if not metrics:
        msg = "--fail-on must list at least one metric name"
        raise ValueError(msg)
    return metrics


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gate a PR on eval regressions.")
    parser.add_argument("--library", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument(
        "--current-run",
        required=True,
        type=Path,
        help="Path to the current eval-run JSON.",
    )
    parser.add_argument(
        "--baseline-run",
        required=True,
        type=Path,
        help="Path to the baseline eval-run JSON.",
    )
    parser.add_argument(
        "--max-regression",
        type=float,
        default=_DEFAULT_MAX_REGRESSION,
        help="Allowed drop per gated metric (absolute, e.g. 0.05).",
    )
    parser.add_argument(
        "--fail-on",
        default=_DEFAULT_FAIL_ON,
        help="Comma-separated metric names that block on regression.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        current = _load_run(args.current_run)
        baseline = _load_run(args.baseline_run)
        gated_metrics = _parse_fail_on(args.fail_on)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        _console.print(f"[red]Bad input: {exc}[/red]")
        return _EXIT_BAD_INPUT

    if current.summary.library_id != args.library or baseline.summary.library_id != args.library:
        _console.print(
            f"[red]Library mismatch: current={current.summary.library_id}, "
            f"baseline={baseline.summary.library_id}, expected={args.library}[/red]"
        )
        return _EXIT_BAD_INPUT
    if current.summary.suite != args.suite or baseline.summary.suite != args.suite:
        _console.print(
            f"[red]Suite mismatch: current={current.summary.suite}, "
            f"baseline={baseline.summary.suite}, expected={args.suite}[/red]"
        )
        return _EXIT_BAD_INPUT

    reporter = MarkdownReporter()
    diff_md = reporter.render_diff(current, baseline)

    regressions: list[tuple[str, float, float, float]] = []
    for metric in gated_metrics:
        cur_score = _metric_value(current, metric)
        base_score = _metric_value(baseline, metric)
        if cur_score is None or base_score is None:
            _console.print(
                f"[yellow]Skipping unknown metric '{metric}' "
                f"(current={cur_score}, baseline={base_score})[/yellow]"
            )
            continue
        delta = cur_score - base_score
        if delta < -args.max_regression:
            regressions.append((metric, base_score, cur_score, delta))

    if regressions:
        _console.print("[red]REGRESSION detected[/red]")
        _console.print(diff_md)
        for name, base_score, cur_score, delta in regressions:
            _console.print(
                f"[red] - {name}: {base_score:.3f} -> {cur_score:.3f} "
                f"(delta {delta:+.3f}, max allowed {-args.max_regression:+.3f})[/red]"
            )
        return _EXIT_REGRESSION

    _console.print("[green]No regression detected[/green]")
    _console.print(diff_md)
    return _EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
