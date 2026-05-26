"""HTTP wire schemas for activity log endpoints (ADR-0014).

API-layer Pydantic models — separate from
`packages.orchestration.activity.ActivityEvent` per CODING_STANDARDS §13.1.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ActivityEventResponse(BaseModel):
    """Wire shape of one activity-log row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int = Field(ge=0)
    library_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    title: str
    summary: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    actor: str = "system"
    created_at: datetime


class ActivityListResponse(BaseModel):
    """Cross-library or per-library activity feed envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[ActivityEventResponse, ...]
