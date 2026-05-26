"""Ingestion runner — synchronous pipeline used by CLI/API.

parse → chunk → embed (cached) → upsert to vector + BM25 + KG.
Returns counts for progress reporting.

M7: idempotent — re-ingesting the same file (same sha256) into the same library
returns the prior IngestResult unless `force=True` is passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from apps._shared.factories.builders import AppContainer
from packages.ingestion.idempotency import hash_file
from packages.ingestion.state import IngestRecord, IngestStateStore


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Summary of an ingest run for one PDF."""

    doc_id: str
    title: str
    chunks_created: int
    chunks_upserted: int
    entities_extracted: int = 0
    triples_extracted: int = 0
    skipped: bool = False


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _state_store(container: AppContainer) -> IngestStateStore:
    db_path = Path(container.settings.ingest_state_dir) / "ingest.sqlite"
    return IngestStateStore(db_path)


async def ingest_pdf(
    container: AppContainer,
    *,
    library_id: str,
    pdf_path: Path,
    extract_kg: bool = True,
    force: bool = False,
) -> IngestResult:
    """Parse, chunk, embed, upsert into vector+BM25 and optionally extract KG.

    Idempotent: a file with the same sha256 is skipped when `force=False`.
    """
    sha = hash_file(pdf_path)
    store = _state_store(container)
    try:
        prior = store.get(library_id, sha)
        if prior is not None and prior.status == "done" and not force and prior.doc_id is not None:
            return IngestResult(
                doc_id=prior.doc_id,
                title=prior.title or "",
                chunks_created=prior.chunks_created,
                chunks_upserted=prior.chunks_upserted,
                skipped=True,
            )

        now = _now_iso()
        store.put(
            IngestRecord(
                library_id=library_id,
                file_sha256=sha,
                file_name=pdf_path.name,
                doc_id=prior.doc_id if prior else None,
                title=prior.title if prior else None,
                status="pending",
                chunks_created=0,
                chunks_upserted=0,
                last_error=None,
                created_at=prior.created_at if prior else now,
                updated_at=now,
            )
        )

        try:
            result = await _run_pipeline(
                container,
                library_id=library_id,
                pdf_path=pdf_path,
                extract_kg=extract_kg,
            )
        except Exception as exc:
            store.put(
                IngestRecord(
                    library_id=library_id,
                    file_sha256=sha,
                    file_name=pdf_path.name,
                    doc_id=prior.doc_id if prior else None,
                    title=prior.title if prior else None,
                    status="failed",
                    chunks_created=0,
                    chunks_upserted=0,
                    last_error=str(exc) or exc.__class__.__name__,
                    created_at=prior.created_at if prior else now,
                    updated_at=_now_iso(),
                )
            )
            raise

        store.put(
            IngestRecord(
                library_id=library_id,
                file_sha256=sha,
                file_name=pdf_path.name,
                doc_id=result.doc_id,
                title=result.title,
                status="done",
                chunks_created=result.chunks_created,
                chunks_upserted=result.chunks_upserted,
                last_error=None,
                created_at=prior.created_at if prior else now,
                updated_at=_now_iso(),
            )
        )
        return result
    finally:
        store.close()


async def _run_pipeline(
    container: AppContainer,
    *,
    library_id: str,
    pdf_path: Path,
    extract_kg: bool,
) -> IngestResult:
    parsed = await container.parser.parse(library_id, pdf_path)
    chunks = container.chunker.chunk(library_id, parsed)

    if not chunks:
        return IngestResult(
            doc_id=parsed.document.doc_id,
            title=parsed.document.title,
            chunks_created=0,
            chunks_upserted=0,
        )

    texts = [c.text for c in chunks]
    vectors = await container.embedder.embed(texts)
    items = list(zip(chunks, vectors, strict=True))

    await container.vector_index.upsert(library_id, items)
    await container.bm25_index.upsert(library_id, chunks)

    entities_count = 0
    triples_count = 0
    if extract_kg and container.extractor is not None:
        result = await container.extractor.extract(library_id, chunks)
        linked = await container.linker.link(library_id, list(result.entities))
        if linked:
            await container.graph_index.upsert_entities(library_id, linked)
        if result.triples:
            await container.graph_index.upsert_triples(library_id, list(result.triples))
        entities_count = len(linked)
        triples_count = len(result.triples)

    return IngestResult(
        doc_id=parsed.document.doc_id,
        title=parsed.document.title,
        chunks_created=len(chunks),
        chunks_upserted=len(items),
        entities_extracted=entities_count,
        triples_extracted=triples_count,
    )
