"""Score Claude-generated answers from agent output JSONs.

Reads `retrieval.<planner>.<ts>.json` (input) + all `answers_batch_*.json`
files written by sub-agents. Computes the same metrics as eval_compare.

Usage:
    uv run python scripts/eval_score_claude.py \
        --input data/libraries/rag-agent/evals/claude_eval/retrieval.routed.<ts>.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from rich.console import Console
from rich.table import Table

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        required=True,
        help="Path to retrieval.<planner>.<ts>.json",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    with in_path.open("r", encoding="utf-8") as f:
        retrieval_data = json.load(f)

    records = retrieval_data["records"]
    by_id: dict[str, dict[str, object]] = {r["sample_id"]: r for r in records}

    # Find all answer files in the same dir
    answers_dir = in_path.parent
    answer_files = sorted(answers_dir.glob("answers_batch_*.json"))
    if not answer_files:
        console.print(
            f"[red]No answer files matching 'answers_batch_*.json' in {answers_dir}[/red]"
        )
        return 1

    answers_by_id: dict[str, dict[str, object]] = {}
    for f_path in answer_files:
        with f_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        for sample_id, payload in data.items():
            answers_by_id[sample_id] = payload
        console.print(f"[dim]Loaded {len(data)} answers from {f_path.name}[/dim]")

    results: list[dict[str, object]] = []
    for sample_id, rec in by_id.items():
        ans_payload = answers_by_id.get(sample_id)
        if ans_payload is None:
            results.append({"sample_id": sample_id, "error": "no answer", "passed": False})
            continue

        answer = str(ans_payload.get("answer", ""))
        retrieved_doc_ids: list[str] = []
        ev = rec.get("evidence", [])
        if isinstance(ev, list):
            seen: set[str] = set()
            for e in ev:  # type: ignore[reportUnknownVariableType]
                if isinstance(e, dict):
                    doc_id_obj = e.get("doc_id")  # type: ignore[reportUnknownArgumentType]
                    if isinstance(doc_id_obj, str) and doc_id_obj not in seen:
                        retrieved_doc_ids.append(doc_id_obj)
                        seen.add(doc_id_obj)

        expected_e = rec.get("expected_evidence_doc_ids", [])
        expected_k = rec.get("expected_key_points", [])
        forbidden = rec.get("must_not_contain", [])
        floor_raw = rec.get("acceptable_score_floor", 0.5)

        scores = _score(
            answer=answer,
            retrieved_doc_ids=retrieved_doc_ids,
            expected_evidence_doc_ids=[str(x) for x in expected_e]  # type: ignore[reportUnknownArgumentType]
            if isinstance(expected_e, list)
            else [],
            expected_key_points=[str(x) for x in expected_k]  # type: ignore[reportUnknownArgumentType]
            if isinstance(expected_k, list)
            else [],
            must_not_contain=[str(x) for x in forbidden]  # type: ignore[reportUnknownArgumentType]
            if isinstance(forbidden, list)
            else [],
        )
        floor = float(floor_raw) if isinstance(floor_raw, (int, float)) else 0.5
        composite = 0.4 * float(scores["recall"]) + 0.6 * float(scores["key_point_cov"])
        passed = (
            composite >= floor
            and bool(scores["citation_ok"])
            and int(scores["forbidden_violations"]) == 0
        )
        results.append(
            {
                "sample_id": sample_id,
                "recall": scores["recall"],
                "key_point_cov": scores["key_point_cov"],
                "citation_ok": scores["citation_ok"],
                "composite": composite,
                "passed": passed,
            }
        )

    n = len(results)

    def _avg(key: str) -> float:
        total = 0.0
        for r in results:
            v = r.get(key, 0)
            if isinstance(v, (int, float)):
                total += float(v)
        return total / max(n, 1)

    summary: dict[str, float | int] = {
        "n": n,
        "passed": sum(1 for r in results if r.get("passed")),
        "errors": sum(1 for r in results if "error" in r),
        "avg_recall": _avg("recall"),
        "avg_key_point_cov": _avg("key_point_cov"),
        "avg_composite": _avg("composite"),
        "citation_pct": sum(1 for r in results if r.get("citation_ok")) / max(n, 1),
    }

    table = Table(title=f"Claude-LLM eval — {in_path.stem}")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Pass rate", f"{int(summary['passed'])}/{int(summary['n'])}")
    table.add_row("Errors (no answer)", f"{int(summary['errors'])}")
    table.add_row("Avg Recall@k", f"{summary['avg_recall']:.3f}")
    table.add_row("Avg KeyPointCov", f"{summary['avg_key_point_cov']:.3f}")
    table.add_row("Avg Composite", f"{summary['avg_composite']:.3f}")
    table.add_row("Citation present", f"{summary['citation_pct'] * 100:.0f}%")
    console.print(table)

    out_path = in_path.with_name(in_path.stem.replace("retrieval.", "scores.") + ".json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, indent=2, ensure_ascii=False)
    console.print(f"\n[dim]Detailed scores: {out_path}[/dim]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
