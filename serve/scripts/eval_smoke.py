"""Smoke evaluation runner — runs the qa.smoke.v1 set against a library.

Usage:
    uv run python scripts/eval_smoke.py --library rag-agent

Deterministic scoring only (no LLM judge):
- Recall@k:       fraction of expected_evidence_doc_ids covered by retrieved chunks
- KeyPointCov:    fraction of expected_key_points appearing in the answer (case-insensitive)
- CitationOk:     answer contains at least one citation marker
- MustNotContain: forbidden phrases not present

Outputs a markdown table to stdout and saves details to data/libraries/<lib>/evals/runs/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from apps._shared.factories import build_container

console = Console()
_CITATION_PATTERN = re.compile(r"\[[a-zA-Z0-9:_\-/.]+::p\d+::\d+\]")


def _score_sample(
    answer: str,
    retrieved_doc_ids: list[str],
    expected_evidence_doc_ids: list[str],
    expected_key_points: list[str],
    must_not_contain: list[str],
) -> dict[str, float | bool | int]:
    """Compute deterministic per-sample scores."""
    answer_lower = answer.lower()

    # Recall@k on doc_id level
    if expected_evidence_doc_ids:
        hit = sum(1 for d in expected_evidence_doc_ids if d in retrieved_doc_ids)
        recall = hit / len(expected_evidence_doc_ids)
    else:
        recall = 1.0

    # Key point coverage
    if expected_key_points:
        kp_hit = sum(1 for kp in expected_key_points if kp.lower() in answer_lower)
        key_point_cov = kp_hit / len(expected_key_points)
    else:
        key_point_cov = 1.0

    # Citation present
    citation_ok = bool(_CITATION_PATTERN.search(answer))

    # Forbidden phrases
    forbidden_violations = sum(1 for f in must_not_contain if f.lower() in answer_lower)

    return {
        "recall": recall,
        "key_point_cov": key_point_cov,
        "citation_ok": citation_ok,
        "forbidden_violations": forbidden_violations,
    }


async def run_eval(library_id: str, suite_path: Path) -> int:
    with suite_path.open("r", encoding="utf-8") as f:
        suite = yaml.safe_load(f)

    samples = suite.get("samples", [])
    if not samples:
        console.print("[red]No samples in suite.[/red]")
        return 1

    console.print(f"[cyan]Running {len(samples)} samples on library '{library_id}'...[/cyan]\n")

    container = build_container()
    results: list[dict[str, object]] = []
    total_in_tokens = 0
    total_out_tokens = 0
    total_latency = 0

    try:
        if not await container.library_repo.exists(library_id):
            console.print(f"[red]Library '{library_id}' does not exist.[/red]")
            return 1

        for i, s in enumerate(samples, 1):
            sample_id = s["sample_id"]
            question = s["question"]
            console.print(f"[dim]({i}/{len(samples)})[/dim] [bold]{sample_id}[/bold]: {question}")

            try:
                ans = await container.qa_task.answer(library_id, question)
            except Exception as e:
                console.print(f"  [red]Error: {type(e).__name__}: {e}[/red]")
                results.append(
                    {
                        "sample_id": sample_id,
                        "question": question,
                        "error": str(e),
                        "recall": 0.0,
                        "key_point_cov": 0.0,
                        "citation_ok": False,
                        "forbidden_violations": 0,
                        "passed": False,
                    }
                )
                continue

            retrieved_doc_ids = list({ev.chunk.doc_id for ev in ans.retrieved})
            scores = _score_sample(
                answer=ans.answer,
                retrieved_doc_ids=retrieved_doc_ids,
                expected_evidence_doc_ids=s.get("expected_evidence_doc_ids", []),
                expected_key_points=s.get("expected_key_points", []),
                must_not_contain=s.get("must_not_contain", []),
            )
            floor = float(s.get("acceptable_score_floor", 0.7))
            composite = 0.4 * float(scores["recall"]) + 0.6 * float(scores["key_point_cov"])
            passed = (
                composite >= floor
                and bool(scores["citation_ok"])
                and int(scores["forbidden_violations"]) == 0
            )

            total_in_tokens += ans.tokens.input_tokens
            total_out_tokens += ans.tokens.output_tokens
            total_latency += ans.duration_ms

            results.append(
                {
                    "sample_id": sample_id,
                    "question": question,
                    "answer": ans.answer,
                    "retrieved_docs": retrieved_doc_ids,
                    "expected_docs": s.get("expected_evidence_doc_ids", []),
                    "recall": scores["recall"],
                    "key_point_cov": scores["key_point_cov"],
                    "citation_ok": scores["citation_ok"],
                    "forbidden_violations": scores["forbidden_violations"],
                    "composite": composite,
                    "floor": floor,
                    "passed": passed,
                    "input_tokens": ans.tokens.input_tokens,
                    "output_tokens": ans.tokens.output_tokens,
                    "duration_ms": ans.duration_ms,
                }
            )

            mark = "[green]✓[/green]" if passed else "[red]✗[/red]"
            console.print(
                f"  {mark} recall={scores['recall']:.2f} "
                f"kp={scores['key_point_cov']:.2f} "
                f"cite={'✓' if scores['citation_ok'] else '✗'} "
                f"composite={composite:.2f} "
                f"({ans.duration_ms}ms, {ans.tokens.input_tokens}+{ans.tokens.output_tokens} tok)"
            )
    finally:
        await container.aclose()

    # Summary
    total = len(results)
    passed_n = sum(1 for r in results if r.get("passed"))
    avg_recall = sum(float(r.get("recall", 0)) for r in results) / max(total, 1)
    avg_kp = sum(float(r.get("key_point_cov", 0)) for r in results) / max(total, 1)
    avg_composite = sum(float(r.get("composite", 0)) for r in results) / max(total, 1)
    cite_pct = sum(1 for r in results if r.get("citation_ok")) / max(total, 1)

    console.print("\n[bold cyan]=== Summary ===[/bold cyan]")
    table = Table(title=f"qa.smoke.v1 on {library_id}")
    for col in ["Metric", "Value"]:
        table.add_column(col)
    table.add_row("Pass rate", f"{passed_n}/{total} ({passed_n / total * 100:.0f}%)")
    table.add_row("Avg Recall@k (doc-level)", f"{avg_recall:.3f}")
    table.add_row("Avg KeyPointCov", f"{avg_kp:.3f}")
    table.add_row("Avg Composite", f"{avg_composite:.3f}")
    table.add_row("Citation present", f"{cite_pct * 100:.0f}%")
    table.add_row("Total tokens (in/out)", f"{total_in_tokens} / {total_out_tokens}")
    table.add_row("Total latency", f"{total_latency / 1000:.1f}s")
    console.print(table)

    # Save artifacts
    runs_dir = suite_path.parent / "runs"
    runs_dir.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = runs_dir / f"qa.smoke.v1.{ts}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "library_id": library_id,
                "suite": "qa.smoke",
                "suite_version": "v1",
                "ran_at": ts,
                "summary": {
                    "passed": passed_n,
                    "total": total,
                    "pass_rate": passed_n / max(total, 1),
                    "avg_recall": avg_recall,
                    "avg_key_point_cov": avg_kp,
                    "avg_composite": avg_composite,
                    "citation_pct": cite_pct,
                    "total_input_tokens": total_in_tokens,
                    "total_output_tokens": total_out_tokens,
                    "total_latency_ms": total_latency,
                },
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    console.print(f"\n[dim]Detailed results saved to: {out}[/dim]")

    return 0 if passed_n == total else 0  # exit 0 always for smoke; gate logic comes in M6


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", default="rag-agent")
    parser.add_argument("--suite", default="qa.smoke.v1.yaml")
    args = parser.parse_args()

    suite_path = Path("data/libraries") / args.library / "evals" / args.suite
    if not suite_path.exists():
        console.print(f"[red]Eval suite not found: {suite_path}[/red]")
        return 1

    return asyncio.run(run_eval(args.library, suite_path))


if __name__ == "__main__":
    raise SystemExit(main())
