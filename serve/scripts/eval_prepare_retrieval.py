"""Pre-retrieve all eval questions, dump (question, chunks) to JSON.

This bypasses chat-completion entirely — only embedding + Qdrant + BM25 + rerank
are called (all relatively fast). The dumped JSON can then be handed to a
Claude sub-agent that synthesizes answers without touching SiliconFlow.

Usage:
    uv run python scripts/eval_prepare_retrieval.py \
        --library rag-agent --suite qa.multihop.v2.yaml --planner routed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import yaml
from rich.console import Console

from apps._shared.factories import build_container
from packages.core.config import Settings
from packages.core.models import Query

console = Console()


async def main_async(library_id: str, suite_path: Path, planner: str, k: int) -> int:
    with suite_path.open("r", encoding="utf-8") as f:
        suite = yaml.safe_load(f)
    samples = suite.get("samples", [])
    if not samples:
        console.print("[red]No samples in suite.[/red]")
        return 1

    os.environ["PLANNER"] = planner
    settings = Settings()
    container = build_container(settings=settings, library_id_for_schema=library_id)

    out_records: list[dict[str, object]] = []

    try:
        if not await container.library_repo.exists(library_id):
            console.print(f"[red]Library '{library_id}' does not exist.[/red]")
            return 1

        for i, s in enumerate(samples, 1):
            sample_id = str(s["sample_id"])
            question = str(s["question"])
            console.print(f"[dim]({i}/{len(samples)})[/dim] {sample_id}")

            try:
                query = Query(
                    library_id=library_id,
                    text=question,
                    type="multi-hop",
                    max_results=k,
                )
                result = await container.planner.plan_and_retrieve(library_id, query)
                evidence = [
                    {
                        "chunk_id": ev.chunk.chunk_id,
                        "doc_id": ev.chunk.doc_id,
                        "page": ev.chunk.page,
                        "score": ev.score,
                        "source": ev.source,
                        "text": ev.chunk.text,
                    }
                    for ev in result.evidence
                ]
            except Exception as e:
                console.print(f"  [red]retrieval error: {type(e).__name__}: {e}[/red]")
                evidence = []

            out_records.append(
                {
                    "sample_id": sample_id,
                    "question": question,
                    "expected_evidence_doc_ids": list(s.get("expected_evidence_doc_ids", []) or []),
                    "expected_key_points": list(s.get("expected_key_points", []) or []),
                    "must_not_contain": list(s.get("must_not_contain", []) or []),
                    "acceptable_score_floor": float(s.get("acceptable_score_floor", 0.5)),
                    "evidence": evidence,
                }
            )
    finally:
        await container.aclose()

    out_dir = suite_path.parent / "claude_eval"
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = out_dir / f"retrieval.{planner}.{ts}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "library_id": library_id,
                "suite": suite_path.stem,
                "planner": planner,
                "k": k,
                "generated_at": ts,
                "records": out_records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    total_evidence = 0
    for r in out_records:
        ev = r["evidence"]
        if isinstance(ev, list):
            total_evidence += len(ev)  # type: ignore[arg-type]
    console.print(
        f"\n[green]✓ Done.[/green] {len(out_records)} questions, "
        f"{total_evidence} chunks total → {out}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", default="rag-agent")
    parser.add_argument("--suite", default="qa.multihop.v2.yaml")
    parser.add_argument(
        "--planner",
        default="routed",
        choices=["routed", "hybrid", "direct", "global", "react"],
    )
    parser.add_argument("--k", type=int, default=8)
    args = parser.parse_args()

    suite_path = Path("data/libraries") / args.library / "evals" / args.suite
    if not suite_path.exists():
        console.print(f"[red]Suite not found: {suite_path}[/red]")
        return 1

    return asyncio.run(main_async(args.library, suite_path, args.planner, args.k))


if __name__ == "__main__":
    raise SystemExit(main())
