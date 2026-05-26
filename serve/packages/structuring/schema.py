"""KG schema loading and validation.

A schema defines the allowed entity and relation types for a library.
Schemas live at `docs/ontology/<library_id>/v1.yaml` and are loaded at
runtime. Triples that violate the schema (unknown types or invalid
type-pair for a relation) are rejected before being written.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from packages.core.errors import RKBError


class SchemaValidationError(RKBError):
    """Triple or entity violates the configured schema."""


class EntityType(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(min_length=1)
    description: str = ""


class RelationType(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(min_length=1)
    description: str = ""
    head_types: tuple[str, ...] = ()
    tail_types: tuple[str, ...] = ()


class KGSchema(BaseModel):
    """Per-library knowledge graph schema."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    schema_version: str = "v1"
    entity_types: tuple[EntityType, ...]
    relation_types: tuple[RelationType, ...]

    def is_valid_entity_type(self, type_id: str) -> bool:
        return any(t.id == type_id for t in self.entity_types)

    def get_relation_type(self, relation_id: str) -> RelationType | None:
        for r in self.relation_types:
            if r.id == relation_id:
                return r
        return None

    def validate_triple(
        self,
        *,
        relation: str,
        head_type: str,
        tail_type: str,
    ) -> None:
        """Raise SchemaValidationError if triple violates schema."""
        rel = self.get_relation_type(relation)
        if rel is None:
            msg = f"Unknown relation type '{relation}'"
            raise SchemaValidationError(msg)
        if rel.head_types and head_type not in rel.head_types:
            msg = (
                f"Relation '{relation}' does not allow head type '{head_type}' "
                f"(allowed: {rel.head_types})"
            )
            raise SchemaValidationError(msg)
        if rel.tail_types and tail_type not in rel.tail_types:
            msg = (
                f"Relation '{relation}' does not allow tail type '{tail_type}' "
                f"(allowed: {rel.tail_types})"
            )
            raise SchemaValidationError(msg)


def load_schema(library_id: str, ontology_dir: Path) -> KGSchema:
    """Load the schema YAML for a library, falling back to default if missing."""
    candidate = ontology_dir / library_id / "v1.yaml"
    if not candidate.exists():
        candidate = ontology_dir / "default" / "v1.yaml"
    if not candidate.exists():
        msg = f"No schema found for library '{library_id}' at {ontology_dir}"
        raise FileNotFoundError(msg)

    with candidate.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    return KGSchema(
        library_id=raw.get("library_id", library_id),
        schema_version=raw.get("schema_version", "v1"),
        entity_types=tuple(EntityType.model_validate(e) for e in raw.get("entity_types", [])),
        relation_types=tuple(RelationType.model_validate(r) for r in raw.get("relation_types", [])),
    )
