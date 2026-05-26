"""HTTP wire schemas for the Document Detail Drawer (M4).

Drives BACKEND_ROADMAP §4.4: list / sections / chunks / pdf preview / retry /
delete. Domain `Document` (`packages.core.models.Document`) is unchanged;
these schemas are the wire-stable shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentSummaryResponse(BaseModel):
    """Compact row for document list views."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    ingest_ts: datetime
    chunks_count: int = Field(ge=0, default=0)
    ingest_status: Literal["queued", "parsing", "indexing", "ready", "failed"] = "ready"
    ingest_error: str | None = None


class DocumentSectionResponse(BaseModel):
    """A logical section of a parsed document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    section_path: str = ""
    title: str = ""
    page: int | None = None


class DocumentDetailResponse(BaseModel):
    """`GET /v1/libraries/{lib}/docs/{doc_id}` payload."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    source_url: str = ""
    doi: str | None = None
    content_hash: str = ""
    ingest_ts: datetime
    ingest_status: Literal["queued", "parsing", "indexing", "ready", "failed"] = "ready"
    ingest_error: str | None = None
    sections: list[DocumentSectionResponse] = Field(default_factory=list)
    chunks_count: int = Field(ge=0, default=0)
    entities_count: int = Field(ge=0, default=0)
    triples_count: int = Field(ge=0, default=0)
    pages_count: int = Field(ge=0, default=0)


class DocumentChunkResponse(BaseModel):
    """One chunk row in the document detail chunks endpoint."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    text: str
    page: int | None = None
    section: str | None = None
    kind: Literal["text", "formula", "table", "caption"] = "text"


class DocumentChunksListResponse(BaseModel):
    """Envelope for paged chunk listing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    chunks: list[DocumentChunkResponse] = Field(default_factory=list)
    total: int = Field(ge=0, default=0)


class DocumentPdfUrlResponse(BaseModel):
    """Pre-signed MinIO URL with expiry timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    expires_at: datetime


class DocumentRetryResponse(BaseModel):
    """Returned when a failed document is re-queued."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    parser: str = "auto"
