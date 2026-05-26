"""Community rebuild pipeline: detect → summarize → embed → upsert into community index.

Pulls all triples from the KG, runs Louvain to find communities, summarizes
each one with the LLM, embeds the summary text, and writes to Qdrant.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from apps._shared.factories.builders import AppContainer
from packages.core.models import Community, Entity, Triple


@dataclass(frozen=True, slots=True)
class CommunityRebuildResult:
    """Summary of a community rebuild for one library."""

    library_id: str
    triples_loaded: int
    communities_detected: int
    communities_summarized: int
    communities_indexed: int


async def rebuild_communities(
    container: AppContainer,
    *,
    library_id: str,
) -> CommunityRebuildResult:
    """Rebuild the community index for a library from its current KG state."""
    triples = await container.graph_index.list_all_triples(library_id)
    if not triples:
        return CommunityRebuildResult(
            library_id=library_id,
            triples_loaded=0,
            communities_detected=0,
            communities_summarized=0,
            communities_indexed=0,
        )

    # Build undirected weighted edge list from triples (aggregate dups)
    edge_weights: dict[tuple[str, str], float] = {}
    for t in triples:
        a, b = sorted((t.head, t.tail))
        edge_weights[(a, b)] = edge_weights.get((a, b), 0.0) + 1.0
    edges = [(h, tl, w) for (h, tl), w in edge_weights.items()]

    communities = await container.community_detector.detect(library_id, edges)
    if not communities:
        return CommunityRebuildResult(
            library_id=library_id,
            triples_loaded=len(triples),
            communities_detected=0,
            communities_summarized=0,
            communities_indexed=0,
        )

    triples_by_endpoint: dict[str, list[Triple]] = {}
    for t in triples:
        triples_by_endpoint.setdefault(t.head, []).append(t)
        triples_by_endpoint.setdefault(t.tail, []).append(t)

    sem = asyncio.Semaphore(container.settings.community_summary_max_concurrent)

    async def _summarize_one(c: Community) -> Community:
        async with sem:
            members = set(c.member_entity_ids)
            local_triples_set: set[tuple[str, str, str]] = set()
            for eid in members:
                for t in triples_by_endpoint.get(eid, []):
                    if t.head in members and t.tail in members:
                        local_triples_set.add((t.head, t.relation, t.tail))
            local_triples = [
                Triple(
                    library_id=library_id,
                    head=h,
                    relation=r,
                    tail=tl,
                    confidence=0.9,
                    evidence=("auto",),
                )
                for h, r, tl in local_triples_set
            ]
            local_entities = [
                Entity(
                    library_id=library_id,
                    entity_id=eid,
                    name=eid.split(":", 1)[-1].replace("_", " "),
                    type=eid.split(":", 1)[0].title() if ":" in eid else "Entity",
                )
                for eid in members
            ]
            return await container.community_summarizer.summarize(
                library_id, c, local_entities, local_triples
            )

    summarized = await asyncio.gather(*(_summarize_one(c) for c in communities))
    summarized = [c for c in summarized if c.summary and c.summary != "[summary failed]"]
    if not summarized:
        return CommunityRebuildResult(
            library_id=library_id,
            triples_loaded=len(triples),
            communities_detected=len(communities),
            communities_summarized=0,
            communities_indexed=0,
        )

    summary_texts = [f"{c.title}\n\n{c.summary}" for c in summarized]
    vectors = await container.embedder.embed(summary_texts)
    items = list(zip(summarized, vectors, strict=True))

    await container.community_index.init_library(library_id)
    await container.community_index.upsert(library_id, items)

    return CommunityRebuildResult(
        library_id=library_id,
        triples_loaded=len(triples),
        communities_detected=len(communities),
        communities_summarized=len(summarized),
        communities_indexed=len(items),
    )
