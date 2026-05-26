"""Ingest a single PDF: parse → chunk → embed → upsert (ADR-0009 §2.1).

Stages emitted (ADR-0010 §2):
- ``parse``      : PDF → structured sections
- ``chunk``      : sections → retrieval chunks
- ``embed``      : chunks → dense vectors
- ``upsert``     : chunks + vectors → vector + bm25 indices

Idempotency: the SHA-256 of the on-disk file is computed before any
expensive work. If the same `(library_id, file_sha256)` is already
recorded as ``status=done``, the job short-circuits with a
``stage_completed`` event for each stage and returns the existing
result pointer (ADR-0019 §11 idempotency reuse).

Adapter dependencies are read from `ctx` so unit tests can inject
fakes without standing up a full container.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import structlog

from apps.worker.jobs._stages import StageEmitter, make_stage_emitter
from apps.worker.jobs.base import JobContext, job_lifecycle
from packages.ingestion.idempotency import hash_file
from packages.ingestion.protocols import Chunker, Parser
from packages.observability import with_span

logger = structlog.get_logger(__name__)

# Hard ceiling on the wall-clock time of a single document ingest. The
# worker still has the global `job_timeout` defense, but we want a tight
# bound so a stuck PDF doesn't pin a worker slot.
_INGEST_TIMEOUT_S = 600.0


class _Embedder(Protocol):
    """Minimal embed surface (avoids a hard dependency on packages.embedding)."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class _VectorIndex(Protocol):
    async def upsert(self, library_id: str, items: list[tuple[Any, list[float]]]) -> None: ...


class _BM25Index(Protocol):
    async def upsert(self, library_id: str, chunks: list[Any]) -> None: ...


class _IngestStateLike(Protocol):
    """Subset of `IngestStateStore` we touch (sync sqlite ops)."""

    def get(self, library_id: str, file_sha256: str) -> Any: ...

    def put(self, record: Any) -> None: ...


async def run(
    ctx: dict[str, Any],
    *,
    library_id: str,
    task_id: str,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    """Ingest one PDF end-to-end.

    Required ``input_payload`` keys:
        - ``file_path``: absolute path of the PDF on disk (sandbox-staged).
        - ``doc_id`` (optional): caller-supplied id; defaults to the short
          content hash so re-ingest is deterministic.
    """
    jc = JobContext.from_arq(
        ctx, library_id=library_id, task_id=task_id, task_type="ingest_document"
    )
    emitter = make_stage_emitter(jc)
    file_path = Path(str(input_payload["file_path"]))

    async with job_lifecycle(jc):
        async with asyncio.timeout(_INGEST_TIMEOUT_S):
            return await _run_inner(jc, ctx, emitter, file_path, input_payload)


async def _run_inner(
    jc: JobContext,
    ctx: dict[str, Any],
    emitter: StageEmitter,
    file_path: Path,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    parser = cast(Parser, ctx["parser"])
    chunker = cast(Chunker, ctx["chunker"])
    embedder = cast(_Embedder, ctx["embedder"])
    vector_index = cast(_VectorIndex, ctx["vector_index"])
    bm25_index = cast(_BM25Index, ctx["bm25_index"])
    state_store = cast(_IngestStateLike | None, ctx.get("ingest_state_store"))

    sha256 = await asyncio.to_thread(hash_file, file_path)
    doc_id = str(input_payload.get("doc_id") or sha256[:12])

    # Dedup short-circuit (ADR-0019 §11)
    if state_store is not None:
        existing = await asyncio.to_thread(state_store.get, jc.library_id, sha256)
        if existing is not None and getattr(existing, "status", "") == "done":
            await jc.log.ainfo(
                "ingest_document_skipped_duplicate",
                file_sha256=sha256,
                doc_id=getattr(existing, "doc_id", doc_id),
            )
            return {
                "doc_id": getattr(existing, "doc_id", doc_id),
                "file_sha256": sha256,
                "deduplicated": True,
                "chunks_upserted": int(getattr(existing, "chunks_upserted", 0)),
            }

    async with with_span(
        "worker.ingest_document",
        library_id=jc.library_id,
        task_id=jc.task_id,
        file_sha256=sha256,
    ):
        await emitter("parse", "stage_started", {"file": file_path.name})
        parsed = await parser.parse(jc.library_id, file_path)
        await emitter(
            "parse",
            "stage_completed",
            {"sections": len(parsed.sections)},
        )

        await emitter("chunk", "stage_started", {})
        chunks = await asyncio.to_thread(chunker.chunk, jc.library_id, parsed)
        await emitter("chunk", "stage_completed", {"chunk_count": len(chunks)})

        await emitter("embed", "stage_started", {"chunk_count": len(chunks)})
        vectors = await embedder.embed([c.text for c in chunks]) if chunks else []
        await emitter("embed", "stage_completed", {"vector_count": len(vectors)})

        await emitter("upsert", "stage_started", {})
        if chunks:
            await vector_index.upsert(jc.library_id, list(zip(chunks, vectors, strict=True)))
            await bm25_index.upsert(jc.library_id, list(chunks))
        await emitter("upsert", "stage_completed", {"chunks_upserted": len(chunks)})

    if state_store is not None:
        await asyncio.to_thread(
            _record_done, state_store, jc.library_id, sha256, file_path.name, doc_id, len(chunks)
        )

    return {
        "doc_id": doc_id,
        "file_sha256": sha256,
        "deduplicated": False,
        "chunks_upserted": len(chunks),
    }


def _record_done(
    store: _IngestStateLike,
    library_id: str,
    sha256: str,
    file_name: str,
    doc_id: str,
    chunk_count: int,
) -> None:
    """Persist the success record so future re-ingest short-circuits.

    Imported lazily to avoid a hard dependency cycle between the worker
    job module and the SQLite-backed state store.
    """
    from packages.ingestion.state import IngestRecord

    now = datetime.now(UTC).isoformat()
    record = IngestRecord(
        library_id=library_id,
        file_sha256=sha256,
        file_name=file_name,
        doc_id=doc_id,
        title=None,
        status="done",
        chunks_created=chunk_count,
        chunks_upserted=chunk_count,
        last_error=None,
        created_at=now,
        updated_at=now,
    )
    store.put(record)


__all__ = ["run"]
