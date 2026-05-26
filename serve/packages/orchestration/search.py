"""⌘K command palette cross-resource search (ADR-0023).

Searches 4 resource types in parallel:
- entity (current library only — Neo4j name+alias fuzzy)
- document (current library only — BM25 title)
- library (cross-library metadata — Postgres ILIKE on name/description/slug)
- action (static registry — keyword match)

The cross-library `library` search is L5-orchestration-only and parallels
ADR-0014's activity log boundary (§16.6 exception).
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

type SearchType = Literal["entity", "document", "library", "action"]


class SearchHit(BaseModel):
    """One row in `/v1/search` response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: SearchType
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    subtitle: str | None = None
    library_id: str | None = None  # None for action / library types
    score: float = Field(ge=0.0)
    payload: dict[str, object] = Field(default_factory=dict)


class SearchQuery(BaseModel):
    """Input to `/v1/search`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    q: str = Field(min_length=2, max_length=200)
    library_id: str | None = None  # current library context
    types: tuple[SearchType, ...] = ("entity", "document", "library", "action")
    limit: int = Field(default=20, ge=1, le=50)


@runtime_checkable
class SearchService(Protocol):
    """⌘K search facade. Internal fan-out hits 4 sources in parallel."""

    async def search(self, query: SearchQuery) -> tuple[SearchHit, ...]: ...
