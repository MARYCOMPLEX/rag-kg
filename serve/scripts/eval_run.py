"""Run a single eval suite using the M6 framework.

Wires :class:`packages.evaluation.runner.DefaultEvalRunner` (when
available) with deterministic + LLM-judge metrics, executes the suite,
prints a markdown report via :class:`MarkdownReporter`, and optionally
persists the run JSON via the runs store.

Usage::

    uv run python scripts/eval_run.py --library rag-agent --suite qa.smoke
    uv run python scripts/eval_run.py --library rag-agent --suite qa.multihop \\
        --version v3 --no-judge --no-save

The script imports the runner / runs-store / metric classes lazily so it
remains usable while sibling agents are still landing those modules:
missing components produce a warning and are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import sys
from typing import Any, Final, Protocol

from rich.console import Console

from apps._shared.factories import build_container
from packages.evaluation.protocols import EvalRun, Metric
from packages.evaluation.reporter import MarkdownReporter

_console: Final[Console] = Console()
_DEFAULT_VERSION: Final[str] = "v1"

# Defensive metric registry: (module path, class name, requires_judge).
_DETERMINISTIC_METRICS: Final[tuple[tuple[str, str], ...]] = (
    ("packages.evaluation.metrics.recall", "RecallAtKMetric"),
    ("packages.evaluation.metrics.key_point_coverage", "KeyPointCoverageMetric"),
    ("packages.evaluation.metrics.citation", "CitationMetric"),
    ("packages.evaluation.metrics.must_not_contain", "MustNotContainMetric"),
)

_JUDGE_METRICS: Final[tuple[tuple[str, str], ...]] = (
    ("packages.evaluation.metrics.llm_judge", "FaithfulnessJudge"),
    ("packages.evaluation.metrics.llm_judge", "AnswerRelevanceJudge"),
)


class _RunnerLike(Protocol):
    async def run_suite(self, library_id: str, suite: str, version: str = ...) -> EvalRun: ...


def _try_import(module_path: str, attr: str) -> Any | None:
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        _console.print(f"[yellow]skip {module_path}.{attr}: {exc}[/yellow]")
        return None
    obj = getattr(module, attr, None)
    if obj is None:
        _console.print(f"[yellow]skip {module_path}.{attr}: not defined yet[/yellow]")
    return obj


def _build_metrics(*, with_judge: bool, container: Any) -> list[Metric]:
    metrics: list[Metric] = []
    for module_path, class_name in _DETERMINISTIC_METRICS:
        cls = _try_import(module_path, class_name)
        if cls is None:
            continue
        try:
            metrics.append(cls())
        except TypeError as exc:
            _console.print(f"[yellow]skip {class_name}: {exc}[/yellow]")
    if not with_judge:
        return metrics
    for module_path, class_name in _JUDGE_METRICS:
        cls = _try_import(module_path, class_name)
        if cls is None:
            continue
        try:
            metrics.append(cls(llm=container.llm))
        except TypeError:
            try:
                metrics.append(cls())
            except TypeError as exc:
                _console.print(f"[yellow]skip {class_name}: {exc}[/yellow]")
    return metrics


def _build_runner(*, container: Any, metrics: list[Metric]) -> _RunnerLike | None:
    runner_cls = _try_import("packages.evaluation.runner", "DefaultEvalRunner")
    if runner_cls is None:
        return None
    loader_cls = _try_import("packages.evaluation.loader", "FilesystemSampleLoader")
    if loader_cls is None:
        return None
    try:
        return runner_cls(  # type: ignore[no-any-return]
            loader=loader_cls(),
            metrics=tuple(metrics),
            qa_task=container.qa_task,
        )
    except TypeError as exc:
        _console.print(f"[red]Failed to construct DefaultEvalRunner: {exc}[/red]")
        return None


def _maybe_save(run: EvalRun) -> None:
    store_cls = _try_import("packages.evaluation.runs_store", "FilesystemRunsStore")
    if store_cls is None:
        _console.print("[yellow]runs_store not available; skipping save[/yellow]")
        return
    try:
        store = store_cls()
        path = store.save(run)
        _console.print(f"[dim]Run saved to: {path}[/dim]")
    except (TypeError, AttributeError, OSError) as exc:
        _console.print(f"[yellow]Save failed: {exc}[/yellow]")


def _print_report(run: EvalRun) -> None:
    reporter = MarkdownReporter()
    _console.print(reporter.render_summary(run))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an eval suite (M6 framework).")
    parser.add_argument("--library", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--version", default=_DEFAULT_VERSION)
    parser.add_argument(
        "--judge",
        dest="judge",
        action="store_true",
        default=True,
        help="Enable LLM-judge metrics (default).",
    )
    parser.add_argument(
        "--no-judge",
        dest="judge",
        action="store_false",
        help="Disable LLM-judge metrics.",
    )
    parser.add_argument(
        "--save",
        dest="save",
        action="store_true",
        default=True,
        help="Persist the run JSON via runs_store (default).",
    )
    parser.add_argument(
        "--no-save",
        dest="save",
        action="store_false",
        help="Do not persist the run JSON.",
    )
    return parser.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    container = build_container()
    try:
        if not await container.library_repo.exists(args.library):
            _console.print(f"[red]Library '{args.library}' does not exist.[/red]")
            return 1

        metrics = _build_metrics(with_judge=args.judge, container=container)
        if not metrics:
            _console.print("[red]No metrics available; cannot run eval.[/red]")
            return 1

        runner = _build_runner(container=container, metrics=metrics)
        if runner is None:
            _console.print("[red]DefaultEvalRunner unavailable; cannot run eval.[/red]")
            return 1

        _console.print(
            f"[cyan]Running {args.suite}.{args.version} on {args.library} "
            f"({len(metrics)} metric(s), judge={'on' if args.judge else 'off'})...[/cyan]"
        )
        run = await runner.run_suite(args.library, args.suite, args.version)
        _print_report(run)

        if args.save:
            _maybe_save(run)
        return 0
    finally:
        await container.aclose()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
