"""Notification center contracts (ADR-0011).

User-facing event channel: task completed/failed, alert triggered,
daily cost cap warnings, library status changes. Storage = Postgres
`notifications` table; transport = SSE pull from `/v1/notifications/stream`.

Cross-library reads are L5-orchestration-only (ADR-0014, §16.6 exception).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

type NotificationId = str  # ULID


class NotificationType(StrEnum):
    """Stable enum; append only, never remove/rename."""

    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    INGEST_COMPLETED = "ingest_completed"
    INGEST_FAILED = "ingest_failed"
    LIBRARY_STATUS_CHANGED = "library_status_changed"
    LIBRARY_PURGED = "library_purged"
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_RECOVERED = "alert_recovered"
    DAILY_COST_WARNING = "daily_cost_warning"
    DAILY_COST_BLOCKED = "daily_cost_blocked"


type Severity = Literal["info", "warning", "danger"]


class Notification(BaseModel):
    """A user-facing event.

    `library_id` is None for system-wide messages (e.g. worker offline).
    `dedup_key` prevents duplicate writes (e.g. retried outbox flush).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: NotificationId
    library_id: str | None
    type: NotificationType
    severity: Severity
    title: str = Field(min_length=1, max_length=120)
    body: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    read: bool = False
    read_at: datetime | None = None
    created_at: datetime
    expires_at: datetime
    dedup_key: str | None = None


@runtime_checkable
class NotificationStore(Protocol):
    """Contract for notification persistence + delivery.

    Single-arg `library_id` methods follow §16.6 strictly. The
    `list_for_user` cross-library aggregation lives in the API layer
    (`apps/api/_notification_reader.py`), not this Protocol.
    """

    async def write(self, notification: Notification) -> None: ...

    async def mark_read(self, library_id: str | None, notification_id: NotificationId) -> None: ...

    async def list_for_library(
        self,
        library_id: str,
        *,
        unread_only: bool = False,
        since: datetime | None = None,
        limit: int = 50,
    ) -> tuple[Notification, ...]: ...

    async def purge_library(self, library_id: str) -> None:
        """Delete all notifications for `library_id` (called from purge saga, ADR-0022)."""
        ...
