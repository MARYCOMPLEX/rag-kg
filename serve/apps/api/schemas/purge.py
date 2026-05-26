"""HTTP wire schemas for purge + library stats (ADR-0022).

Stats-v2 collapses the `/stats` endpoint into a single hit that returns
all 5 backends' counters; older `LibraryStatsResponse` in
`apps/api/routes/libraries.py` stays for backward compatibility.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LibraryPurgeReceiptResponse(BaseModel):
    """Per-backend purge receipt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    backend: Literal["qdrant", "bm25", "neo4j", "minio", "postgres"]
    found: bool
    deleted: int = Field(ge=0, default=0)
    duration_ms: int = Field(ge=0, default=0)
    error: str | None = None


class LibraryPurgeResponse(BaseModel):
    """Envelope for `DELETE /v1/libraries/{id}?purge=1`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    status: Literal["purged", "partial_purged", "purging"]
    receipts: list[LibraryPurgeReceiptResponse] = Field(default_factory=list)
    requested_by: str | None = None
    completed_at: datetime | None = None


class LibraryStatsResponseV2(BaseModel):
    """Aggregated stats across the 4 storage adapters + Postgres."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    documents: int = Field(ge=0, default=0)
    chunks: int = Field(ge=0, default=0)
    entities: int = Field(ge=0, default=0)
    triples: int = Field(ge=0, default=0)
    communities: int = Field(ge=0, default=0)
    bm25_docs: int = Field(ge=0, default=0)
    summary_freshness_iso: str | None = None
    status: str = "healthy"
