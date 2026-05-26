"""HTTP wire schemas for notifications endpoints (ADR-0011).

API-layer Pydantic models — kept separate from the domain
`packages.orchestration.notifications.Notification` per CODING_STANDARDS
§13.1 so the wire contract can evolve independently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    """Wire shape of a single Notification row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    library_id: str | None = None
    type: str = Field(min_length=1)
    severity: Literal["info", "warning", "danger"]
    title: str
    body: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    read: bool = False
    read_at: datetime | None = None
    created_at: datetime
    expires_at: datetime
    dedup_key: str | None = None


class NotificationListResponse(BaseModel):
    """Envelope for a paginated/filtered list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[NotificationResponse, ...]
    unread_count: int = Field(ge=0, default=0)


class NotificationMarkReadResponse(BaseModel):
    """Result of a mark-read POST."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    marked: bool
