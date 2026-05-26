"""Run NER + RE + EL over a Library's chunks and upsert into the KG.

Stages emitted (ADR-0010):
- ``kg_extract``        : NER + RE batch over the chunk tail
- ``upsert``            : entities + triples → graph index

The job is **idempotent at the (library_id, entity_id) / (library_id,
chunk_id, head, relation, tail) granularity** — re-running over the same
chunks must not duplicate entities or triples (the graph index adapter
enforces this on its side).

Inputs are intentionally narrow: this job only consumes the chunks
already indexed for the library. The caller does not need to ship the
chunk payload back over the queue.
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, cast

import structlog

from apps.worker.jobs._stages import StageEmitter, make_stage_emitter
from apps.worker.jobs.base import JobContext, job_lifecycle
from packages.core.models import Chunk, Entity, Triple
from packages.indexing.protocols import GraphIndex
from packages.observability import with_span
from packages.structuring.protocols import (
    EntityExtractor,
    EntityLinker,
    RelationExtractor,
)

logger = structlog.get_logger(__name__)

_KG_EXTRACT_TIMEOUT_S = 900.0


class _ChunkSourceLike(Protocol):
    """Pluggable source of chunks for a library.

    Tests inject a list-backed fake; production wires a Postgres-backed
    chunk store. The signature matches what we actually need: list chunks
    optionally filtered to a doc_id (single-doc post-ingest extraction).
    """

    async def list_chunks(self, library_id: str, *, doc_id: str | None = None) -> list[Chunk]: ...


async def run(
    ctx: dict[str, Any],
    *,
    library_id: str,
    task_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    """Extract entities + triples for a library (or for one document)."""
    jc = JobContext.from_arq(ctx, library_id=library_id, task_id=task_id, task_type="extract_kg")
    emitter = make_stage_emitter(jc)
    doc_id = input_payload.get("doc_id")
    doc_filter = str(doc_id) if doc_id else None

    async with job_lifecycle(jc):
        async with asyncio.timeout(_KG_EXTRACT_TIMEOUT_S):
            return await _run_inner(jc, ctx, emitter, doc_filter)


async def _run_inner(
    jc: JobContext,
    ctx: dict[str, Any],
    emitter: StageEmitter,
    doc_filter: str | None,
) -> dict[str, Any]:
    chunk_source = cast(_ChunkSourceLike, ctx["chunk_source"])
    ner = cast(EntityExtractor, ctx["entity_extractor"])
    re = cast(RelationExtractor, ctx["relation_extractor"])
    linker = cast(EntityLinker | None, ctx.get("entity_linker"))
    graph_index = cast(GraphIndex, ctx["graph_index"])

    async with with_span(
        "worker.extract_kg",
        library_id=jc.library_id,
        task_id=jc.task_id,
        doc_id=doc_filter or "",
    ):
        await emitter("kg_extract", "stage_started", {"doc_id": doc_filter})
        chunks = await chunk_source.list_chunks(jc.library_id, doc_id=doc_filter)
        entities = await ner.extract(jc.library_id, list(chunks))
        if linker is not None and entities:
            entities = await linker.link(jc.library_id, list(entities))
        triples = await re.extract(jc.library_id, list(chunks), list(entities)) if entities else []
        await emitter(
            "kg_extract",
            "stage_completed",
            {
                "chunk_count": len(chunks),
                "entity_count": len(entities),
                "triple_count": len(triples),
            },
        )

        await emitter("upsert", "stage_started", {})
        if entities:
            await graph_index.upsert_entities(jc.library_id, _as_list(entities))
        if triples:
            await graph_index.upsert_triples(jc.library_id, _as_list(triples))
        await emitter(
            "upsert",
            "stage_completed",
            {"entities_upserted": len(entities), "triples_upserted": len(triples)},
        )

    return {
        "chunks": len(chunks),
        "entities": len(entities),
        "triples": len(triples),
    }


def _as_list(items: list[Entity] | list[Triple]) -> list[Any]:
    """Pyright nudges us to list[T]; defer to plain list at the boundary."""
    return list(items)


__all__ = ["run"]
