"""HTTP wire schemas for ⌘K search (ADR-0023).

Why a separate response model from `packages.orchestration.search.SearchHit`:
the API may add display-only fields (`deeplink`) without polluting the
domain model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SearchHitResponse(BaseModel):
    """One row in `/v1/search` response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["entity", "document", "library", "action"]
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    subtitle: str | None = None
    library_id: str | None = None
    score: float = Field(ge=0.0)
    deeplink: str = ""
    payload: dict[str, object] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Envelope for `GET /v1/search`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str
    library_id: str | None = None
    hits: list[SearchHitResponse] = Field(default_factory=list)
    timing_ms: dict[str, int] = Field(default_factory=dict)
    degraded: list[str] = Field(default_factory=list)
