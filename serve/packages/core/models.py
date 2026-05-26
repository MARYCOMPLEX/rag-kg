"""Domain models shared across all packages.

Every cross-library model has library_id as its first field.
All models are frozen and forbid extra fields.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LIBRARY_ID_PATTERN = r"^[a-z][a-z0-9-]{2,30}$"


class LibraryStatus(StrEnum):
    """Library lifecycle status, set by `library_status_check` worker job.

    See ADR-0013 for state machine and PRD §16.7 for definitions.
    """

    HEALTHY = "healthy"
    INDEXING = "indexing"
    STALE_COMMUNITY = "stale_community"
    PURGING = "purging"
    PARTIAL_PURGED = "partial_purged"


type Language = Literal["en", "zh", "mixed"]


class Library(BaseModel):
    """A self-contained research corpus partition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(pattern=LIBRARY_ID_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    created_at: datetime
    domain: str | None = None
    language: Language | None = None  # narrowed in M7; see ADR-0013 / ADR_REVIEW R10
    status: LibraryStatus = LibraryStatus.HEALTHY
    status_updated_at: datetime | None = None


class Document(BaseModel):
    """An ingested research document within a library."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str | None = None
    source_url: str = ""
    doi: str | None = None
    content_hash: str = Field(min_length=1)
    ingest_ts: datetime


class Chunk(BaseModel):
    """A text segment of a document, the atomic retrieval unit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    text: str
    page: int | None = None
    section: str | None = None
    kind: Literal["text", "formula", "table", "caption"] = "text"
    offset: tuple[int, int] = (0, 0)


class Entity(BaseModel):
    """A named entity extracted from the knowledge graph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    type: str = Field(min_length=1)
    description: str | None = None


class Triple(BaseModel):
    """A knowledge graph triple with provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    head: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    tail: str = Field(min_length=1)
    evidence: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    source_model: str = ""


class Query(BaseModel):
    """A user query scoped to a library."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    type: Literal["single-hop", "multi-hop", "global", "definition"] = "single-hop"
    max_results: int = Field(default=10, ge=1, le=100)


class Community(BaseModel):
    """A KG community (cluster of densely-connected entities) with summary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    community_id: str = Field(min_length=1)
    level: int = Field(ge=0, le=10)
    member_entity_ids: tuple[str, ...] = ()
    title: str = ""
    summary: str = ""
    summary_model: str = ""
    representative_entities: tuple[str, ...] = ()


class DomainEvent(BaseModel):
    """Base for all domain events. Payload always includes library_id."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    timestamp: datetime
    event_type: str = Field(min_length=1)
