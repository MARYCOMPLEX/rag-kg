"""Activity log contracts (ADR-0014).

Append-only event stream of important per-library actions. Drives the
S2 Library Dashboard "Recent activity" feed.

Crucial §16.6 boundary: the Protocol below is per-library_id only. The
cross-library aggregation reader lives in `apps/api/_activity_reader.py`
and is the only place L5 may IN-list multiple library_ids.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ActivityType(StrEnum):
    """Stable enum; append only."""

    INGEST_COMPLETED = "ingest_completed"
    INGEST_FAILED = "ingest_failed"
    KG_EXTRACTED = "kg_extracted"
    COMMUNITY_REBUILT = "community_rebuilt"
    REVIEW_COMPLETED = "review_completed"
    REASON_COMPLETED = "reason_completed"
    HYPOTHESIZE_COMPLETED = "hypothesize_completed"
    LIBRARY_STATUS_CHANGED = "library_status_changed"
    LIBRARY_PURGED = "library_purged"
    EVAL_RUN_COMPLETED = "eval_run_completed"
    ALERT_TRIGGERED = "alert_triggered"


class ActivityEvent(BaseModel):
    """One audit row in `activity_log` (partitioned monthly, 90d TTL)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int = 0  # BIGSERIAL, auto-assigned on insert
    library_id: str = Field(min_length=1)
    type: ActivityType
    title: str = Field(min_length=1, max_length=200)
    summary: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    actor: str = "system"  # principal id or "system"
    created_at: datetime


@runtime_checkable
class ActivityLogger(Protocol):
    """Per-library activity recorder. Cross-library reads NOT exposed here."""

    async def record(self, event: ActivityEvent) -> None: ...

    async def list_for_library(
        self,
        library_id: str,
        *,
        since: datetime | None = None,
        types: tuple[ActivityType, ...] | None = None,
        limit: int = 50,
    ) -> tuple[ActivityEvent, ...]: ...
