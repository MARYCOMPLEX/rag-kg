"""Domain event definitions.

All events carry library_id in their payload for routing and tracing.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ConfigDict, Field

from packages.core.models import DomainEvent


class DocumentUploaded(DomainEvent):
    """Fired when a raw document is received for processing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = "docs.uploaded"
    doc_id: str = Field(min_length=1)
    file_path: str = Field(min_length=1)


class DocumentParsed(DomainEvent):
    """Fired when a document has been parsed into sections."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = "docs.parsed"
    doc_id: str = Field(min_length=1)
    chunk_count: int = Field(ge=0)


class ChunksEmbedded(DomainEvent):
    """Fired when chunks have been embedded and indexed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = "chunks.embedded"
    doc_id: str = Field(min_length=1)
    chunk_count: int = Field(ge=0)


class KGUpdated(DomainEvent):
    """Fired when the knowledge graph has been updated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = "kg.updated"
    triple_count: int = Field(ge=0)
    entity_count: int = Field(ge=0)


class LibraryCreated(DomainEvent):
    """Fired when a new library is initialized."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = "library.created"
    name: str


class LibraryPurged(DomainEvent):
    """Fired when a library is fully purged from all stores."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_type: str = "library.purged"


def make_event_ts() -> datetime:
    """Return a UTC-aware timestamp for event creation."""
    return datetime.now(UTC)
