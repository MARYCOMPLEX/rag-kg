"""Compare retrieval planners on the same eval suite.

Runs the same eval suite under multiple PLANNER values (e.g. routed, react)
and reports per-planner metrics + side-by-side delta.

Usage:
    uv run python scripts/eval_compare_planners.py \\
        --library rag-agent --suite qa.multihop.v2.yaml \\
        --planners routed,react
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from apps._shared.factories import build_container
from packages.core.config import Settings

console = Console()
_CITATION_PATTERN = re.compile(r"\[[a-zA-Z0-9:_\-/.]+\]")


def _score(
    answer: str,
    retrieved_doc_ids: list[str],
    expected_evidence_doc_ids: list[str],
    expected_key_points: list[str],
    must_not_contain: list[str],
) -> dict[str, float | bool | int]:
    answer_lower = answer.lower()
    if expected_evidence_doc_ids:
        hit = sum(1 for d in expected_evidence_doc_ids if d in retrieved_doc_ids)
        recall = hit / len(expected_evidence_doc_ids)
    else:
        recall = 1.0
    if expected_key_points:
        kp_hit = sum(1 for kp in expected_key_points if kp.lower() in answer_lower)
        key_point_cov = kp_hit / len(expected_key_points)
    else:
        key_point_cov = 1.0
    citation_ok = bool(_CITATION_PATTERN.search(answer))
    forbidden_violations = sum(1 for f in must_not_contain if f.lower() in answer_lower)
    return {
        "recall": recall,
        "key_point_cov": key_point_cov,
        "citation_ok": citation_ok,
        "forbidden_violations": forbidden_violations,
    }


async def run_one_planner(
    library_id: str,
    samples: list[dict[str, object]],
    planner_name: str,
) -> dict[str, object]:
    """Run all samples with the given planner."""
    os.environ["PLANNER"] = planner_name
    settings = Settings()
    container = build_container(settings=settings, library_id_for_schema=library_id)

    console.print(f"\n[bold cyan]Planner: {planner_name}[/bold cyan]")

    results: list[dict[str, object]] = []
    total_in = 0
    total_out = 0
    total_ms = 0

    try:
        if not await container.library_repo.exists(library_id):
            console.print(f"[red]Library '{library_id}' does not exist.[/red]")
            return {"planner": planner_name, "results": [], "summary": {}}

        for i, s in enumerate(samples, 1):
            sample_id = s["sample_id"]
            question = str(s["question"])
            print(f"  ({i}/{len(samples)}) {sample_id}", flush=True)

            try:
                ans = await container.qa_task.answer(library_id, question)
            except Exception as e:
                results.append(
                    {
                        "sample_id": sample_id,
                        "error": f"{type(e).__name__}: {e}",
                        "recall": 0.0,
                        "key_point_cov": 0.0,
                        "citation_ok": False,
                        "passed": False,
                        "composite": 0.0,
                    }
                )
                continue

            retrieved = list({ev.chunk.doc_id for ev in ans.retrieved})

            def _str_list(key: str, sample: dict[str, object] = s) -> list[str]:
                raw = sample.get(key, [])
                if not isinstance(raw, list):
                    return []
                return [str(x) for x in raw]  # type: ignore[reportUnknownVariableType,reportUnknownArgumentType]

            scores = _score(
                answer=ans.answer,
                retrieved_doc_ids=retrieved,
                expected_evidence_doc_ids=_str_list("expected_evidence_doc_ids"),
                expected_key_points=_str_list("expected_key_points"),
                must_not_contain=_str_list("must_not_contain"),
            )
            floor_raw = s.get("acceptable_score_floor", 0.5)
            floor = float(floor_raw) if isinstance(floor_raw, (int, float)) else 0.5
            composite = 0.4 * float(scores["recall"]) + 0.6 * float(scores["key_point_cov"])
            passed = (
                composite >= floor
                and bool(scores["citation_ok"])
                and int(scores["forbidden_violations"]) == 0
            )
            total_in += ans.tokens.input_tokens
            total_out += ans.tokens.output_tokens
            total_ms += ans.duration_ms

            results.append(
                {
                    "sample_id": sample_id,
                    "recall": scores["recall"],
                    "key_point_cov": scores["key_point_cov"],
                    "citation_ok": scores["citation_ok"],
                    "composite": composite,
                    "passed": passed,
                    "input_tokens": ans.tokens.input_tokens,
                    "output_tokens": ans.tokens.output_tokens,
                    "duration_ms": ans.duration_ms,
                }
            )
    finally:
        await container.aclose()

    n = len(results)

    def _avg(key: str) -> float:
        total = 0.0
        for r in results:
            v = r.get(key, 0)
            if isinstance(v, (int, float)):
                total += float(v)
        return total / max(n, 1)

    summary: dict[str, object] = {
        "n": n,
        "passed": sum(1 for r in results if r.get("passed")),
        "avg_recall": _avg("recall"),
        "avg_key_point_cov": _avg("key_point_cov"),
        "avg_composite": _avg("composite"),
        "citation_pct": sum(1 for r in results if r.get("citation_ok")) / max(n, 1),
        "errors": sum(1 for r in results if "error" in r),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_latency_ms": total_ms,
    }
    return {"planner": planner_name, "results": results, "summary": summary}


def render_comparison(runs: list[dict[str, object]]) -> None:
    table = Table(title="Planner comparison")
    table.add_column("Metric")
    for r in runs:
        table.add_column(str(r["planner"]))

    summaries = [r["summary"] for r in runs]

    def _row(label: str, k: str, fmt: str = "{:.3f}", pct: bool = False) -> None:
        row = [label]
        for s in summaries:
            v = float(s.get(k, 0))  # type: ignore[union-attr]
            row.append(f"{v * 100:.0f}%" if pct else fmt.format(v))
        table.add_row(*row)

    _row("Pass rate", "passed", fmt="{:.0f}")
    _row("Avg Recall@k", "avg_recall")
    _row("Avg KeyPointCov", "avg_key_point_cov")
    _row("Avg Composite", "avg_composite")
    _row("Citation present", "citation_pct", pct=True)
    _row("Errors", "errors", fmt="{:.0f}")
    _row("Total tokens (in)", "total_input_tokens", fmt="{:.0f}")
    _row("Total tokens (out)", "total_output_tokens", fmt="{:.0f}")
    _row("Total latency (s)", "total_latency_ms", fmt="{:.0f}")
    console.print(table)


async def main_async(library_id: str, suite_path: Path, planners: list[str]) -> int:
    with suite_path.open("r", encoding="utf-8") as f:
        suite = yaml.safe_load(f)
    samples = suite.get("samples", [])
    if not samples:
        console.print("[red]No samples in suite.[/red]")
        return 1

    runs: list[dict[str, object]] = []
    for p in planners:
        runs.append(await run_one_planner(library_id, samples, p))

    render_comparison(runs)

    runs_dir = suite_path.parent / "runs"
    runs_dir.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = runs_dir / f"compare_planners.{ts}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump({"planners": runs}, f, indent=2, ensure_ascii=False)
    console.print(f"\n[dim]Detailed results: {out}[/dim]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", default="rag-agent")
    parser.add_argument("--suite", default="qa.multihop.v2.yaml")
    parser.add_argument(
        "--planners",
        default="routed,react",
        help="Comma-separated planner names to compare",
    )
    args = parser.parse_args()

    suite_path = Path("data/libraries") / args.library / "evals" / args.suite
    if not suite_path.exists():
        console.print(f"[red]Suite not found: {suite_path}[/red]")
        return 1

    planners = [p.strip() for p in args.planners.split(",") if p.strip()]
    return asyncio.run(main_async(args.library, suite_path, planners))


if __name__ == "__main__":
    raise SystemExit(main())
