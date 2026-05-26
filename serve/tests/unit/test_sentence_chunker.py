"""Tests for the sentence-based chunker."""

from __future__ import annotations

from datetime import UTC, datetime

from packages.core.models import Document
from packages.ingestion.adapters.sentence_chunker import (
    SentenceChunker,
    SentenceChunkerConfig,
)
from packages.ingestion.protocols import ParsedDocument, ParsedSection


def _make_doc(text_per_page: list[str]) -> ParsedDocument:
    doc = Document(
        library_id="test-lib",
        doc_id="d1",
        title="t",
        content_hash="h",
        ingest_ts=datetime(2026, 1, 1, tzinfo=UTC),
    )
    sections = tuple(ParsedSection(text=t, page=i + 1) for i, t in enumerate(text_per_page) if t)
    return ParsedDocument(document=doc, sections=sections)


class TestSentenceChunker:
    def test_chunks_empty_doc(self) -> None:
        parsed = ParsedDocument(
            document=Document(
                library_id="test-lib",
                doc_id="d1",
                title="t",
                content_hash="h",
                ingest_ts=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        chunker = SentenceChunker()
        assert chunker.chunk("test-lib", parsed) == []

    def test_short_text_below_min_chars_dropped(self) -> None:
        parsed = _make_doc(["hi."])
        chunker = SentenceChunker()
        assert chunker.chunk("test-lib", parsed) == []

    def test_basic_chunk_creation(self) -> None:
        text = ". ".join(["This is a complete sentence" for _ in range(20)]) + "."
        parsed = _make_doc([text])
        chunker = SentenceChunker(SentenceChunkerConfig(target_chars=200, min_chars=50))
        chunks = chunker.chunk("test-lib", parsed)
        assert len(chunks) >= 2
        for c in chunks:
            assert c.library_id == "test-lib"
            assert c.doc_id == "d1"
            assert "::p1::" in c.chunk_id
            assert c.kind == "text"
            assert c.page == 1

    def test_chunk_ids_unique_within_doc(self) -> None:
        text = ". ".join([f"sentence number {i}" for i in range(50)]) + "."
        parsed = _make_doc([text, text])
        chunker = SentenceChunker(SentenceChunkerConfig(target_chars=150, min_chars=40))
        chunks = chunker.chunk("test-lib", parsed)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_max_chars_enforced(self) -> None:
        # One huge sentence, no terminators — should still cap at max_chars
        long_text = "word " * 1000
        parsed = _make_doc([long_text])
        chunker = SentenceChunker(SentenceChunkerConfig(max_chars=500))
        chunks = chunker.chunk("test-lib", parsed)
        for c in chunks:
            assert len(c.text) <= 500

    def test_overlap_creates_continuity(self) -> None:
        text = ". ".join([f"unique-{i}" for i in range(40)]) + "."
        parsed = _make_doc([text])
        chunker = SentenceChunker(
            SentenceChunkerConfig(target_chars=80, overlap_chars=40, min_chars=20)
        )
        chunks = chunker.chunk("test-lib", parsed)
        assert len(chunks) >= 2
