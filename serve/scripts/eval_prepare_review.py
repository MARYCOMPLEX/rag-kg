"""Pre-retrieve evidence per subtopic for ReviewGenerationTask sub-agent dispatch.

Mirrors `eval_prepare_retrieval.py` but for the review task: takes a topic,
uses a hand-picked outline (or LLM-generated outline if you wire one in),
pre-retrieves evidence per heading, and dumps a JSON for a Claude sub-agent
to synthesize the review without touching SiliconFlow chat completion.

Usage:
    uv run python scripts/eval_prepare_review.py \
        --library rag-agent \
        --topic "Retrieval-Augmented Generation methods and architectures" \
        --planner routed
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from apps._shared.factories import build_container
from packages.core.config import Settings
from packages.core.models import Query

console = Console()

# Hand-picked outline tailored for the rag-agent corpus content.
# Each heading is phrased so the existing routed planner gets meaningful
# chunks back (mix of method names + technique terms).
_DEFAULT_HEADINGS: tuple[str, ...] = (
    "Vector retrieval and hybrid search in RAG pipelines",
    "Knowledge graph augmented RAG: GraphRAG and HippoRAG",
    "Adaptive retrieval and self-reflection methods (Self-RAG, CRAG, Adaptive-RAG)",
    "Agent frameworks for retrieval and reasoning (ReAct, AutoGen, Modular RAG)",
    "Hierarchical and community-based retrieval (RAPTOR, GraphRAG communities)",
)


async def main_async(library_id: str, topic: str, planner: str, k: int) -> int:
    os.environ["PLANNER"] = planner
    settings = Settings()
    container = build_container(settings=settings, library_id_for_schema=library_id)

    sections_records: list[dict[str, object]] = []

    try:
        if not await container.library_repo.exists(library_id):
            console.print(f"[red]Library '{library_id}' does not exist.[/red]")
            return 1

        for i, heading in enumerate(_DEFAULT_HEADINGS, 1):
            console.print(f"[dim]({i}/{len(_DEFAULT_HEADINGS)})[/dim] {heading}")
            try:
                query = Query(
                    library_id=library_id,
                    text=heading,
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

            sections_records.append({"heading": heading, "evidence": evidence})
    finally:
        await container.aclose()

    out_dir = Path("data/libraries") / library_id / "evals" / "claude_eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    out = out_dir / f"review_input.{planner}.{ts}.json"
    with out.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "library_id": library_id,
                "topic": topic,
                "planner": planner,
                "k": k,
                "generated_at": ts,
                "sections": sections_records,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    total_evidence = 0
    for s in sections_records:
        ev_field = s["evidence"]
        if isinstance(ev_field, list):
            total_evidence += len(ev_field)  # type: ignore[reportUnknownArgumentType]
    console.print(
        f"\n[green]✓ Done.[/green] {len(sections_records)} sections, "
        f"{total_evidence} chunks total → {out}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", default="rag-agent")
    parser.add_argument(
        "--topic",
        default="Retrieval-Augmented Generation methods and architectures",
    )
    parser.add_argument("--planner", default="routed")
    parser.add_argument("--k", type=int, default=8)
    args = parser.parse_args()

    return asyncio.run(main_async(args.library, args.topic, args.planner, args.k))


if __name__ == "__main__":
    raise SystemExit(main())
