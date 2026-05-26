"""Rebuild a Library's community hierarchy: Leiden + LLM summary.

Stages emitted (ADR-0010):
- ``community_rebuild``: Leiden clustering of the library's KG
- ``embed``            : community-summary embedding
- ``upsert``           : community + summary write to the community index

The job assumes the caller has already populated the graph index for the
library (via ``extract_kg``). It is safe to re-run — the community index
adapter is responsible for replacing the prior community set atomically
(or via a swap-on-write key namespace).
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, cast

import structlog

from apps.worker.jobs._stages import StageEmitter, make_stage_emitter
from apps.worker.jobs.base import JobContext, job_lifecycle
from packages.core.models import Community, Entity, Triple
from packages.indexing.protocols import CommunityDetector, CommunityIndex
from packages.observability import with_span
from packages.structuring.protocols import CommunitySummarizer

logger = structlog.get_logger(__name__)

_REBUILD_TIMEOUT_S = 900.0


class _Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class _GraphSnapshotLike(Protocol):
    """Source of (entities, triples) for a library.

    `GraphIndex` exposes neighbor reads but not a full snapshot — keeping
    the interface here narrow lets a Postgres-backed mirror be wired in
    production while tests inject a list-backed fake.
    """

    async def list_entities(self, library_id: str) -> list[Entity]: ...

    async def list_triples(self, library_id: str) -> list[Triple]: ...


async def run(
    ctx: dict[str, Any],
    *,
    library_id: str,
    task_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    jc = JobContext.from_arq(
        ctx, library_id=library_id, task_id=task_id, task_type="rebuild_community"
    )
    emitter = make_stage_emitter(jc)

    async with job_lifecycle(jc):
        async with asyncio.timeout(_REBUILD_TIMEOUT_S):
            return await _run_inner(jc, ctx, emitter, input_payload)


async def _run_inner(
    jc: JobContext,
    ctx: dict[str, Any],
    emitter: StageEmitter,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    snapshot = cast(_GraphSnapshotLike, ctx["graph_snapshot"])
    detector = cast(CommunityDetector, ctx["community_detector"])
    summarizer = cast(CommunitySummarizer, ctx["community_summarizer"])
    index = cast(CommunityIndex, ctx["community_index"])
    embedder = cast(_Embedder, ctx["embedder"])

    _ = input_payload  # reserved for level / resolution overrides

    async with with_span(
        "worker.rebuild_community",
        library_id=jc.library_id,
        task_id=jc.task_id,
    ):
        await emitter("community_rebuild", "stage_started", {})
        entities = await snapshot.list_entities(jc.library_id)
        triples = await snapshot.list_triples(jc.library_id)
        edges = _triples_to_weighted_edges(triples)
        bare_communities = await detector.detect(jc.library_id, edges)
        # Summarize each community with the LLM-backed summarizer.
        summaries = await _summarize_all(
            summarizer, jc.library_id, bare_communities, entities, triples
        )
        await emitter(
            "community_rebuild",
            "stage_completed",
            {
                "entity_count": len(entities),
                "triple_count": len(triples),
                "community_count": len(summaries),
            },
        )

        await emitter("embed", "stage_started", {"community_count": len(summaries)})
        vectors = await embedder.embed([c.summary for c in summaries]) if summaries else []
        await emitter("embed", "stage_completed", {"vector_count": len(vectors)})

        await emitter("upsert", "stage_started", {})
        if summaries:
            await index.upsert(jc.library_id, list(zip(summaries, vectors, strict=True)))
        await emitter(
            "upsert",
            "stage_completed",
            {"communities_upserted": len(summaries)},
        )

    return {
        "communities": len(summaries),
        "entities": len(entities),
        "triples": len(triples),
    }


async def _summarize_all(
    summarizer: CommunitySummarizer,
    library_id: str,
    communities: list[Community],
    all_entities: list[Entity],
    all_triples: list[Triple],
) -> list[Community]:
    """Summarize each community with its member entities + adjacent triples."""
    by_id = {e.entity_id: e for e in all_entities}
    summaries: list[Community] = []
    for community in communities:
        member_set = set(community.member_entity_ids)
        members = [by_id[eid] for eid in community.member_entity_ids if eid in by_id]
        adj = [t for t in all_triples if t.head in member_set or t.tail in member_set]
        summarized = await summarizer.summarize(library_id, community, members, adj)
        summaries.append(summarized)
    return summaries


def _triples_to_weighted_edges(
    triples: list[Triple],
) -> list[tuple[str, str, float]]:
    """Aggregate parallel triples into weighted edges by confidence sum."""
    weights: dict[tuple[str, str], float] = {}
    for triple in triples:
        key = (triple.head, triple.tail)
        weights[key] = weights.get(key, 0.0) + triple.confidence
    return [(head, tail, w) for (head, tail), w in weights.items()]


__all__ = ["run"]
