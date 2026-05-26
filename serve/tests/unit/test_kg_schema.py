"""Tests for KG schema loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.structuring.schema import (
    EntityType,
    KGSchema,
    RelationType,
    SchemaValidationError,
    load_schema,
)


def _make_schema() -> KGSchema:
    return KGSchema(
        library_id="test-lib",
        entity_types=(
            EntityType(id="Method"),
            EntityType(id="Dataset"),
        ),
        relation_types=(
            RelationType(
                id="evaluated_on",
                head_types=("Method",),
                tail_types=("Dataset",),
            ),
            RelationType(id="freeform"),
        ),
    )


class TestKGSchema:
    def test_is_valid_entity_type(self) -> None:
        schema = _make_schema()
        assert schema.is_valid_entity_type("Method") is True
        assert schema.is_valid_entity_type("Bogus") is False

    def test_get_relation_type(self) -> None:
        schema = _make_schema()
        rel = schema.get_relation_type("evaluated_on")
        assert rel is not None
        assert rel.id == "evaluated_on"
        assert schema.get_relation_type("nope") is None

    def test_validate_triple_ok(self) -> None:
        schema = _make_schema()
        schema.validate_triple(
            relation="evaluated_on",
            head_type="Method",
            tail_type="Dataset",
        )

    def test_validate_triple_unknown_relation_raises(self) -> None:
        schema = _make_schema()
        with pytest.raises(SchemaValidationError, match="Unknown relation"):
            schema.validate_triple(relation="bogus", head_type="Method", tail_type="Dataset")

    def test_validate_triple_wrong_head_type_raises(self) -> None:
        schema = _make_schema()
        with pytest.raises(SchemaValidationError, match="head type"):
            schema.validate_triple(
                relation="evaluated_on",
                head_type="Dataset",
                tail_type="Dataset",
            )

    def test_validate_triple_freeform_relation_allows_any_types(self) -> None:
        schema = _make_schema()
        # No type constraints — should pass
        schema.validate_triple(relation="freeform", head_type="Method", tail_type="Dataset")
        schema.validate_triple(relation="freeform", head_type="Dataset", tail_type="Method")

    def test_load_schema_from_file(self, tmp_path: Path) -> None:
        ontology = tmp_path / "lib"
        ontology.mkdir()
        (ontology / "v1.yaml").write_text(
            """library_id: lib
schema_version: v1
entity_types:
  - id: Method
relation_types:
  - id: improves_upon
    head_types: [Method]
    tail_types: [Method]
""",
            encoding="utf-8",
        )
        schema = load_schema("lib", tmp_path)
        assert schema.library_id == "lib"
        assert len(schema.entity_types) == 1

    def test_load_schema_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_schema("nope", tmp_path)
