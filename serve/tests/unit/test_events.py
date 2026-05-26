"""Tests for domain events."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.core.events import (
    ChunksEmbedded,
    DocumentParsed,
    DocumentUploaded,
    KGUpdated,
    LibraryCreated,
    LibraryPurged,
    make_event_ts,
)


class TestDocumentUploaded:
    def test_create_valid_event(self) -> None:
        evt = DocumentUploaded(
            library_id="test-lib",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            doc_id="doc-001",
            file_path="/tmp/paper.pdf",
        )
        assert evt.event_type == "docs.uploaded"
        assert evt.library_id == "test-lib"

    def test_is_frozen(self) -> None:
        evt = DocumentUploaded(
            library_id="test-lib",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            doc_id="doc-001",
            file_path="/tmp/paper.pdf",
        )
        with pytest.raises(ValidationError):
            evt.doc_id = "other"  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        evt = DocumentUploaded(
            library_id="test-lib",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            doc_id="doc-001",
            file_path="/tmp/paper.pdf",
        )
        data = evt.model_dump()
        restored = DocumentUploaded.model_validate(data)
        assert restored == evt


class TestDocumentParsed:
    def test_create_valid_event(self) -> None:
        evt = DocumentParsed(
            library_id="test-lib",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            doc_id="doc-001",
            chunk_count=42,
        )
        assert evt.event_type == "docs.parsed"
        assert evt.chunk_count == 42


class TestChunksEmbedded:
    def test_create_valid_event(self) -> None:
        evt = ChunksEmbedded(
            library_id="test-lib",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            doc_id="doc-001",
            chunk_count=42,
        )
        assert evt.event_type == "chunks.embedded"


class TestKGUpdated:
    def test_create_valid_event(self) -> None:
        evt = KGUpdated(
            library_id="test-lib",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            triple_count=100,
            entity_count=50,
        )
        assert evt.event_type == "kg.updated"


class TestLibraryCreated:
    def test_create_valid_event(self) -> None:
        evt = LibraryCreated(
            library_id="test-lib",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            name="Test Library",
        )
        assert evt.event_type == "library.created"


class TestLibraryPurged:
    def test_create_valid_event(self) -> None:
        evt = LibraryPurged(
            library_id="test-lib",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert evt.event_type == "library.purged"


class TestMakeEventTs:
    def test_returns_utc_datetime(self) -> None:
        ts = make_event_ts()
        assert ts.tzinfo is not None
