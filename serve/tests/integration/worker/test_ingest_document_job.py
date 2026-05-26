"""Integration test for `apps.worker.jobs.ingest_document.run`.

Drives the job end-to-end with in-memory adapters so the lifecycle
contract (status row + SSE events + dedup) is exercised without
requiring Postgres / Redis / the real parser stack.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from apps.worker.jobs import ingest_document
from packages.core.models import Chunk
from packages.ingestion.protocols import ParsedDocument, ParsedSection
from packages.ingestion.state import IngestRecord


class _FakeParser:
    async def parse(self, library_id: str, file_path: Path) -> ParsedDocument:
        from packages.core.models import Document

        doc = Document(
            library_id=library_id,
            doc_id=file_path.stem,
            title=file_path.stem,
            content_hash="dummyhash",
            ingest_ts=datetime.now(UTC),
        )
        return ParsedDocument(
            document=doc,
            sections=(ParsedSection(text="Hello world.", page=1),),
        )


class _FakeChunker:
    def chunk(self, library_id: str, parsed: ParsedDocument) -> list[Chunk]:
        return [
            Chunk(
                library_id=library_id,
                chunk_id=f"{parsed.document.doc_id}::p1::0",
                doc_id=parsed.document.doc_id,
                text="Hello world.",
                page=1,
            )
        ]


class _FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _FakeVectorIndex:
    def __init__(self) -> None:
        self.upserts: list[Any] = []

    async def upsert(self, library_id: str, items: list[tuple[Any, list[float]]]) -> None:
        self.upserts.append((library_id, items))


class _FakeBM25Index:
    def __init__(self) -> None:
        self.upserts: list[Any] = []

    async def upsert(self, library_id: str, chunks: list[Any]) -> None:
        self.upserts.append((library_id, chunks))


class _FakeStateStore:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], IngestRecord] = {}

    def get(self, library_id: str, file_sha256: str) -> IngestRecord | None:
        return self.records.get((library_id, file_sha256))

    def put(self, record: IngestRecord) -> None:
        self.records[(record.library_id, record.file_sha256)] = record


@pytest.mark.asyncio
async def test_ingest_document_runs_full_pipeline(
    base_ctx: dict[str, Any],
    fake_event_bus: Any,
    tmp_path: Path,
) -> None:
    # Arrange — a tiny stub PDF on disk.
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%dummy")
    vector_index = _FakeVectorIndex()
    bm25_index = _FakeBM25Index()
    state_store = _FakeStateStore()
    ctx = {
        **base_ctx,
        "parser": _FakeParser(),
        "chunker": _FakeChunker(),
        "embedder": _FakeEmbedder(),
        "vector_index": vector_index,
        "bm25_index": bm25_index,
        "ingest_state_store": state_store,
    }

    # Act
    result = await ingest_document.run(
        ctx,
        library_id="test-lib",
        task_id="task-1",
        input_payload={"file_path": str(pdf)},
    )

    # Assert — pipeline succeeded and indices saw the chunk
    assert result["chunks_upserted"] == 1
    assert result["deduplicated"] is False
    assert vector_index.upserts and len(vector_index.upserts[0][1]) == 1
    assert bm25_index.upserts and len(bm25_index.upserts[0][1]) == 1
    # Stage events were emitted
    stages = [s for s, _ in fake_event_bus.stage_events() if s is not None]
    for expected in ("parse", "chunk", "embed", "upsert"):
        assert expected in stages
    # State store recorded done
    record = state_store.get("test-lib", result["file_sha256"])
    assert record is not None
    assert record.status == "done"


@pytest.mark.asyncio
async def test_ingest_document_short_circuits_on_duplicate(
    base_ctx: dict[str, Any],
    fake_event_bus: Any,
    tmp_path: Path,
) -> None:
    # Arrange — pre-seed the state store so the second run is a dedup hit.
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%dummy")

    from packages.ingestion.idempotency import hash_file

    sha = hash_file(pdf)
    now = datetime.now(UTC).isoformat()
    state_store = _FakeStateStore()
    state_store.put(
        IngestRecord(
            library_id="test-lib",
            file_sha256=sha,
            file_name=pdf.name,
            doc_id="prev-doc",
            title=None,
            status="done",
            chunks_created=4,
            chunks_upserted=4,
            last_error=None,
            created_at=now,
            updated_at=now,
        )
    )

    parser = _FakeParser()
    vector_index = _FakeVectorIndex()
    ctx = {
        **base_ctx,
        "parser": parser,
        "chunker": _FakeChunker(),
        "embedder": _FakeEmbedder(),
        "vector_index": vector_index,
        "bm25_index": _FakeBM25Index(),
        "ingest_state_store": state_store,
    }

    # Act
    result = await ingest_document.run(
        ctx,
        library_id="test-lib",
        task_id="task-2",
        input_payload={"file_path": str(pdf)},
    )

    # Assert — early exit, no upsert touched.
    assert result["deduplicated"] is True
    assert result["chunks_upserted"] == 4
    assert vector_index.upserts == []
