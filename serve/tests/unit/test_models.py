"""Tests for core domain models.

Covers serialization roundtrip, immutability, validation, and library_id constraints.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.core.models import Chunk, Document, Entity, Library, Query, Triple


class TestLibrary:
    def test_create_valid_library(self) -> None:
        lib = Library(
            library_id="my-lib",
            name="My Library",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert lib.library_id == "my-lib"
        assert lib.name == "My Library"
        assert lib.description is None

    def test_library_id_pattern_rejects_uppercase(self) -> None:
        with pytest.raises(ValidationError):
            Library(
                library_id="MyLib",
                name="Bad",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_library_id_pattern_rejects_too_short(self) -> None:
        with pytest.raises(ValidationError):
            Library(
                library_id="ab",
                name="Bad",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_library_id_pattern_rejects_special_chars(self) -> None:
        with pytest.raises(ValidationError):
            Library(
                library_id="my_lib",
                name="Bad",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_library_is_frozen(self, sample_library: Library) -> None:
        with pytest.raises(ValidationError):
            sample_library.library_id = "other"  # type: ignore[misc]

    def test_library_forbids_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            Library(
                library_id="test-lib",
                name="Test",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                unknown_field="bad",  # type: ignore[call-arg]
            )

    def test_library_serialization_roundtrip(self, sample_library: Library) -> None:
        data = sample_library.model_dump()
        restored = Library.model_validate(data)
        assert restored == sample_library

    def test_library_json_roundtrip(self, sample_library: Library) -> None:
        json_str = sample_library.model_dump_json()
        restored = Library.model_validate_json(json_str)
        assert restored == sample_library


class TestDocument:
    def test_create_valid_document(self, sample_document: Document) -> None:
        assert sample_document.library_id == "test-lib"
        assert sample_document.doc_id == "doc-001"
        assert sample_document.authors == ("Alice", "Bob")

    def test_document_library_id_is_first_field(self) -> None:
        fields = list(Document.model_fields.keys())
        assert fields[0] == "library_id"

    def test_document_is_frozen(self, sample_document: Document) -> None:
        with pytest.raises(ValidationError):
            sample_document.title = "Changed"  # type: ignore[misc]

    def test_document_serialization_roundtrip(self, sample_document: Document) -> None:
        data = sample_document.model_dump()
        restored = Document.model_validate(data)
        assert restored == sample_document

    def test_document_requires_content_hash(self) -> None:
        with pytest.raises(ValidationError):
            Document(
                library_id="test-lib",
                doc_id="doc-001",
                title="No Hash",
                content_hash="",
                ingest_ts=datetime(2026, 1, 1, tzinfo=UTC),
            )


class TestChunk:
    def test_create_valid_chunk(self, sample_chunk: Chunk) -> None:
        assert sample_chunk.library_id == "test-lib"
        assert sample_chunk.kind == "text"

    def test_chunk_library_id_is_first_field(self) -> None:
        fields = list(Chunk.model_fields.keys())
        assert fields[0] == "library_id"

    def test_chunk_is_frozen(self, sample_chunk: Chunk) -> None:
        with pytest.raises(ValidationError):
            sample_chunk.text = "modified"  # type: ignore[misc]

    def test_chunk_serialization_roundtrip(self, sample_chunk: Chunk) -> None:
        data = sample_chunk.model_dump()
        restored = Chunk.model_validate(data)
        assert restored == sample_chunk

    def test_chunk_kind_literal_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            Chunk(
                library_id="test-lib",
                chunk_id="c1",
                doc_id="d1",
                text="hello",
                kind="image",  # type: ignore[arg-type]
            )

    def test_chunk_model_copy_creates_new_instance(self, sample_chunk: Chunk) -> None:
        updated = sample_chunk.model_copy(update={"text": "new text"})
        assert updated.text == "new text"
        assert sample_chunk.text == "This is a test chunk about knowledge graphs."


class TestEntity:
    def test_create_valid_entity(self, sample_entity: Entity) -> None:
        assert sample_entity.library_id == "test-lib"
        assert sample_entity.name == "GraphRAG"

    def test_entity_library_id_is_first_field(self) -> None:
        fields = list(Entity.model_fields.keys())
        assert fields[0] == "library_id"

    def test_entity_is_frozen(self, sample_entity: Entity) -> None:
        with pytest.raises(ValidationError):
            sample_entity.name = "Changed"  # type: ignore[misc]

    def test_entity_serialization_roundtrip(self, sample_entity: Entity) -> None:
        data = sample_entity.model_dump()
        restored = Entity.model_validate(data)
        assert restored == sample_entity


class TestTriple:
    def test_create_valid_triple(self, sample_triple: Triple) -> None:
        assert sample_triple.library_id == "test-lib"
        assert sample_triple.confidence == 0.95

    def test_triple_library_id_is_first_field(self) -> None:
        fields = list(Triple.model_fields.keys())
        assert fields[0] == "library_id"

    def test_triple_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Triple(
                library_id="test-lib",
                head="a",
                relation="r",
                tail="b",
                confidence=1.5,
            )

    def test_triple_is_frozen(self, sample_triple: Triple) -> None:
        with pytest.raises(ValidationError):
            sample_triple.relation = "other"  # type: ignore[misc]

    def test_triple_serialization_roundtrip(self, sample_triple: Triple) -> None:
        data = sample_triple.model_dump()
        restored = Triple.model_validate(data)
        assert restored == sample_triple


class TestQuery:
    def test_create_valid_query(self, sample_query: Query) -> None:
        assert sample_query.library_id == "test-lib"
        assert sample_query.type == "single-hop"

    def test_query_library_id_is_first_field(self) -> None:
        fields = list(Query.model_fields.keys())
        assert fields[0] == "library_id"

    def test_query_max_results_bounds(self) -> None:
        with pytest.raises(ValidationError):
            Query(
                library_id="test-lib",
                text="question",
                max_results=0,
            )

    def test_query_type_literal_rejects_invalid(self) -> None:
        with pytest.raises(ValidationError):
            Query(
                library_id="test-lib",
                text="question",
                type="invalid",  # type: ignore[arg-type]
            )
