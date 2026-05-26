"""L5-only cross-library notification reader (ADR-0011 §6, ADR-0014 §6).

Cross-library aggregation for the top-bar Notify center. Mirrors the
shape of `_activity_reader.py` and is sanctioned by PRD §16.6's L5 read-
only meta-view exception. Lives in `apps/api/` so domain Protocols stay
strictly per-library.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.observability import with_span
from packages.orchestration.notifications import (
    Notification,
    NotificationType,
    Severity,
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _decode_payload(raw: object) -> dict[str, object]:
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return cast(dict[str, object], decoded)
        return {}
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    return {}


def _row_to_notification(row: Mapping[str, Any]) -> Notification:
    return Notification(
        id=row["id"],
        library_id=row.get("library_id"),
        type=NotificationType(row["type"]),
        severity=cast(Severity, row["severity"]),
        title=row["title"],
        body=row.get("body"),
        payload=_decode_payload(row.get("payload")),
        read=bool(row.get("read")),
        read_at=_ensure_aware(row.get("read_at")),
        created_at=_ensure_aware(row.get("created_at")) or datetime.now(UTC),
        expires_at=_ensure_aware(row.get("expires_at")) or datetime.now(UTC),
        dedup_key=row.get("dedup_key"),
    )


class NotificationCrossReader:
    """SQL helper aggregating `notifications` rows across libraries.

    Library scope policy (ADR-0011 §6): a row is visible to a principal
    if its `library_id` is NULL (system-wide) **or** matches one of the
    requested `library_ids`. The `expires_at > now()` guard hides
    TTL'd rows (ADR-0011 §7).
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def list_for_libraries(
        self,
        *,
        library_ids: Sequence[str],
        unread_only: bool = False,
        since: datetime | None = None,
        limit: int = 50,
    ) -> tuple[Notification, ...]:
        """Return notifications visible to the supplied library set.

        Empty `library_ids` still returns globals (`library_id IS NULL`).
        """
        async with with_span(
            "api.notifications.list_for_libraries",
            library_count=len(library_ids),
        ):
            sql = text(
                """
                SELECT id, library_id, type, severity, title, body, payload,
                       read, read_at, created_at, expires_at, dedup_key
                FROM notifications
                WHERE (library_id IS NULL
                       OR library_id = ANY(:library_ids))
                  AND expires_at > now()
                  AND (NOT :unread_only OR read = FALSE)
                  AND (CAST(:since AS TIMESTAMPTZ) IS NULL OR created_at >= CAST(:since AS TIMESTAMPTZ))
                ORDER BY created_at DESC
                LIMIT :limit
                """
            )
            async with self._sessionmaker() as session:
                result = await session.execute(
                    sql,
                    {
                        "library_ids": list(library_ids),
                        "unread_only": bool(unread_only),
                        "since": since,
                        "limit": int(limit),
                    },
                )
                rows = result.mappings().all()
            return tuple(_row_to_notification(cast(Mapping[str, Any], r)) for r in rows)

    async def count_unread(
        self,
        *,
        library_ids: Sequence[str],
    ) -> int:
        """Return the unread-notification count for the top-bar dot.

        Ref: ADR-0011 §6 — partial index `notifications_unread_idx` keeps
        this cheap.
        """
        async with with_span(
            "api.notifications.count_unread",
            library_count=len(library_ids),
        ):
            sql = text(
                """
                SELECT count(*) AS c
                FROM notifications
                WHERE read = FALSE
                  AND expires_at > now()
                  AND (library_id IS NULL
                       OR library_id = ANY(:library_ids))
                """
            )
            async with self._sessionmaker() as session:
                result = await session.execute(sql, {"library_ids": list(library_ids)})
                row = result.first()
            if row is None:
                return 0
            return int(row[0] or 0)
