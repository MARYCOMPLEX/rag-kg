"""Compare M1 (vector-only) vs M2 (hybrid + rerank) on the same eval suite.

Toggles HYBRID_ENABLED and RERANK_ENABLED for two passes, runs the same
eval set against both, and reports the delta.

Usage:
    uv run python scripts/eval_compare.py --library rag-agent --suite qa.multihop.v2.yaml
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
_CITATION_PATTERN = re.compile(r"\[[a-zA-Z0-9:_\-/.]+::p\d+::\d+\]")


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


async def run_one_mode(
    library_id: str,
    samples: list[dict[str, object]],
    *,
    mode_name: str,
    hybrid: bool,
    rerank: bool,
) -> dict[str, object]:
    """Run all samples in the given mode (hybrid on/off, rerank on/off)."""
    # Override config via env so build_container picks them up
    os.environ["HYBRID_ENABLED"] = "true" if hybrid else "false"
    os.environ["RERANK_ENABLED"] = "true" if rerank else "false"

    settings = Settings()
    container = build_container(settings=settings, library_id_for_schema=library_id)

    console.print(
        f"\n[bold cyan]Running mode: {mode_name}[/bold cyan]  (hybrid={hybrid}, rerank={rerank})"
    )

    results: list[dict[str, object]] = []
    total_in = 0
    total_out = 0
    total_ms = 0

    try:
        if not await container.library_repo.exists(library_id):
            console.print(f"[red]Library '{library_id}' does not exist.[/red]")
            return {"mode": mode_name, "results": [], "summary": {}}

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
            scores = _score(
                answer=ans.answer,
                retrieved_doc_ids=retrieved,
                expected_evidence_doc_ids=list(s.get("expected_evidence_doc_ids", []) or []),
                expected_key_points=list(s.get("expected_key_points", []) or []),
                must_not_contain=list(s.get("must_not_contain", []) or []),
            )
            floor = float(s.get("acceptable_score_floor", 0.5))
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
    summary = {
        "n": n,
        "passed": sum(1 for r in results if r.get("passed")),
        "avg_recall": sum(float(r.get("recall", 0)) for r in results) / max(n, 1),
        "avg_key_point_cov": sum(float(r.get("key_point_cov", 0)) for r in results) / max(n, 1),
        "avg_composite": sum(float(r.get("composite", 0)) for r in results) / max(n, 1),
        "citation_pct": sum(1 for r in results if r.get("citation_ok")) / max(n, 1),
        "errors": sum(1 for r in results if "error" in r),
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_latency_ms": total_ms,
    }
    return {"mode": mode_name, "results": results, "summary": summary}


def render_comparison(direct: dict[str, object], hybrid: dict[str, object]) -> None:
    ds = direct["summary"]
    hs = hybrid["summary"]

    table = Table(title="M1 (vector-only) vs M2 (hybrid + rerank)")
    table.add_column("Metric")
    table.add_column("M1 (DirectRAG)")
    table.add_column("M2 (Hybrid)")
    table.add_column("Δ")

    def _row(label: str, k: str, fmt: str = "{:.3f}", pct: bool = False) -> None:
        d = float(ds.get(k, 0))
        h = float(hs.get(k, 0))
        delta = h - d
        arrow = "↑" if delta > 0 else "↓" if delta < 0 else "·"
        if pct:
            d_str = f"{d * 100:.0f}%"
            h_str = f"{h * 100:.0f}%"
            d_str_2 = f"{delta * 100:+.1f}pp"
        else:
            d_str = fmt.format(d)
            h_str = fmt.format(h)
            d_str_2 = f"{delta:+.3f}"
        table.add_row(label, d_str, h_str, f"{arrow} {d_str_2}")

    _row("Pass rate", "passed", fmt="{:.0f}")
    _row("Avg Recall@k", "avg_recall")
    _row("Avg KeyPointCov", "avg_key_point_cov")
    _row("Avg Composite", "avg_composite")
    _row("Citation present", "citation_pct", pct=True)
    _row("Errors", "errors", fmt="{:.0f}")
    _row("Total tokens (in)", "total_input_tokens", fmt="{:.0f}")
    _row("Total tokens (out)", "total_output_tokens", fmt="{:.0f}")
    _row("Total latency (ms)", "total_latency_ms", fmt="{:.0f}")
    console.print(table)

    # PRD M2 Exit Criterion: Recall@10 +20% vs M1
    d_recall = float(ds.get("avg_recall", 0))
    h_recall = float(hs.get("avg_recall", 0))
    if d_recall > 0:
        rel_gain = (h_recall - d_recall) / d_recall * 100
        console.print(f"\n[bold]Recall improvement: {rel_gain:+.1f}%[/bold] (target ≥ +20%)")
        if rel_gain >= 20:
            console.print("[bold green]✓ M2 exit criterion MET[/bold green]")
        else:
            console.print("[bold yellow]⚠ M2 exit criterion NOT met[/bold yellow]")


async def main_async(library_id: str, suite_path: Path) -> int:
    with suite_path.open("r", encoding="utf-8") as f:
        suite = yaml.safe_load(f)
    samples = suite.get("samples", [])
    if not samples:
        console.print("[red]No samples in suite.[/red]")
        return 1

    direct_run = await run_one_mode(
        library_id, samples, mode_name="direct", hybrid=False, rerank=False
    )
    hybrid_run = await run_one_mode(
        library_id, samples, mode_name="hybrid", hybrid=True, rerank=True
    )

    render_comparison(direct_run, hybrid_run)

    runs_dir = suite_path.parent / "runs"
    runs_dir.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = runs_dir / f"compare.{ts}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump({"direct": direct_run, "hybrid": hybrid_run}, f, indent=2, ensure_ascii=False)
    console.print(f"\n[dim]Detailed results: {out}[/dim]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", default="rag-agent")
    parser.add_argument("--suite", default="qa.multihop.v2.yaml")
    args = parser.parse_args()

    suite_path = Path("data/libraries") / args.library / "evals" / args.suite
    if not suite_path.exists():
        console.print(f"[red]Suite not found: {suite_path}[/red]")
        return 1

    return asyncio.run(main_async(args.library, suite_path))


if __name__ == "__main__":
    raise SystemExit(main())
