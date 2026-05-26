"""Postgres-backed notification center (ADR-0011).

Persists user-facing events in the `notifications` table and pushes
realtime updates via PostgreSQL ``LISTEN/NOTIFY``. Per ADR-0011 §5,
inserts go through ``ON CONFLICT (dedup_key) DO NOTHING`` so the
worker outbox can retry safely.

Two key contracts:

1. The Protocol is **strictly per-library** — cross-library reads live
   in ``apps/api/_activity_reader.py``-style helpers (PRD §16.6 L5
   exception).
2. ``listen()`` only forwards row IDs (Postgres NOTIFY payload is
   capped at 8 KB); subscribers re-fetch the full row by id.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import structlog
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
    and_,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.observability import with_span
from packages.orchestration._internal.ulid import new_ulid
from packages.orchestration.errors import NotificationStoreError
from packages.orchestration.notifications import (
    Notification,
    NotificationId,
    NotificationType,
    Severity,
)

logger = structlog.get_logger(__name__)

_DANGER_TTL_DAYS: int = 180
_DEFAULT_TTL_DAYS: int = 90
_LISTEN_CHANNEL: str = "notifications_channel"

_metadata = MetaData()

notifications_table = Table(
    "notifications",
    _metadata,
    Column("id", Text, primary_key=True),
    Column("library_id", Text, nullable=True),
    Column("type", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("body", Text, nullable=True),
    Column("payload", JSON, nullable=False),
    Column("read", Boolean, nullable=False, default=False),
    Column("read_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("dedup_key", Text, nullable=True),
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _row_to_notification(row: Mapping[str, Any]) -> Notification:
    raw_payload = row["payload"]
    payload: dict[str, object]
    if isinstance(raw_payload, str):
        try:
            payload = cast(dict[str, object], json.loads(raw_payload))
        except json.JSONDecodeError:
            payload = {}
    elif isinstance(raw_payload, dict):
        payload = cast(dict[str, object], raw_payload)
    else:
        payload = {}
    return Notification(
        id=row["id"],
        library_id=row["library_id"],
        type=NotificationType(row["type"]),
        severity=cast(Severity, row["severity"]),
        title=row["title"],
        body=row["body"],
        payload=payload,
        read=bool(row["read"]),
        read_at=_ensure_aware(row["read_at"]),
        created_at=_ensure_aware(row["created_at"]) or datetime.now(UTC),
        expires_at=_ensure_aware(row["expires_at"]) or datetime.now(UTC),
        dedup_key=row["dedup_key"],
    )


def _default_expires_at(severity: Severity, created_at: datetime) -> datetime:
    """Per ADR-0011 §7: danger gets 180 d, others 90 d."""
    days = _DANGER_TTL_DAYS if severity == "danger" else _DEFAULT_TTL_DAYS
    return created_at + timedelta(days=days)


class PostgresNotificationStore:
    """Durable persistence + LISTEN/NOTIFY transport for notifications.

    Implements the ``NotificationStore`` Protocol declared in
    ``packages.orchestration.notifications``. Construction takes an
    ``AsyncEngine`` (writes) plus an optional asyncpg DSN string (used to
    open dedicated raw connections for ``LISTEN``).
    """

    def __init__(self, engine: AsyncEngine, *, listen_dsn: str | None = None) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )
        self._listen_dsn = listen_dsn

    async def write(self, notification: Notification) -> None:
        """Insert a notification row. Idempotent on ``dedup_key``."""
        async with with_span(
            "orchestration.notifications.write",
            library_id=notification.library_id or "",
        ):
            try:
                expires = notification.expires_at
                if expires <= notification.created_at:
                    expires = _default_expires_at(notification.severity, notification.created_at)
                stmt = pg_insert(notifications_table).values(
                    id=notification.id,
                    library_id=notification.library_id,
                    type=notification.type.value,
                    severity=notification.severity,
                    title=notification.title,
                    body=notification.body,
                    payload=dict(notification.payload),
                    read=notification.read,
                    read_at=notification.read_at,
                    created_at=notification.created_at,
                    expires_at=expires,
                    dedup_key=notification.dedup_key,
                )
                if notification.dedup_key is not None:
                    stmt = stmt.on_conflict_do_nothing(index_elements=["dedup_key"])
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except Exception as exc:
                await logger.aerror(
                    "notification_write_failed",
                    library_id=notification.library_id,
                    notification_id=notification.id,
                    error=repr(exc),
                )
                raise NotificationStoreError("notification write failed") from exc

            await logger.ainfo(
                "notification_written",
                library_id=notification.library_id,
                notification_id=notification.id,
                type=notification.type.value,
                severity=notification.severity,
            )

    async def emit(
        self,
        *,
        library_id: str | None,
        notification_type: NotificationType,
        severity: Severity,
        title: str,
        body: str | None = None,
        payload: Mapping[str, object] | None = None,
        dedup_key: str | None = None,
    ) -> Notification:
        """Convenience helper: build + write + return a notification.

        Used by status-checker / cost-cap call sites that don't pre-build
        a `Notification` object.
        """
        now = datetime.now(UTC)
        notification = Notification(
            id=new_ulid(),
            library_id=library_id,
            type=notification_type,
            severity=severity,
            title=title,
            body=body,
            payload=dict(payload or {}),
            created_at=now,
            expires_at=_default_expires_at(severity, now),
            dedup_key=dedup_key,
        )
        await self.write(notification)
        return notification

    async def mark_read(
        self,
        library_id: str | None,
        notification_id: NotificationId,
    ) -> None:
        """Idempotent: marks read and stamps ``read_at``."""
        async with with_span(
            "orchestration.notifications.mark_read",
            library_id=library_id or "",
        ):
            now = datetime.now(UTC)
            condition = notifications_table.c.id == notification_id
            if library_id is not None:
                condition = and_(
                    condition,
                    or_(
                        notifications_table.c.library_id == library_id,
                        notifications_table.c.library_id.is_(None),
                    ),
                )
            stmt = update(notifications_table).where(condition).values(read=True, read_at=now)
            async with self._sessionmaker() as session, session.begin():
                await session.execute(stmt)

    async def get(self, notification_id: NotificationId) -> Notification | None:
        """Fetch a single notification by id. Used by SSE handler after NOTIFY."""
        stmt = select(notifications_table).where(notifications_table.c.id == notification_id)
        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            row = result.mappings().first()
        if row is None:
            return None
        return _row_to_notification(dict(row))

    async def list_for_library(
        self,
        library_id: str,
        *,
        unread_only: bool = False,
        since: datetime | None = None,
        limit: int = 50,
    ) -> tuple[Notification, ...]:
        """Per-library list (single value, never a list of ids)."""
        async with with_span(
            "orchestration.notifications.list_for_library",
            library_id=library_id,
        ):
            conditions = [
                or_(
                    notifications_table.c.library_id == library_id,
                    notifications_table.c.library_id.is_(None),
                )
            ]
            if unread_only:
                conditions.append(notifications_table.c.read.is_(False))
            if since is not None:
                conditions.append(notifications_table.c.created_at >= since)
            stmt = (
                select(notifications_table)
                .where(and_(*conditions))
                .order_by(notifications_table.c.created_at.desc())
                .limit(limit)
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            return tuple(_row_to_notification(dict(r)) for r in rows)

    async def purge_library(self, library_id: str) -> None:
        """Delete every notification belonging to ``library_id``.

        Called from the Library Purge saga (ADR-0022). Global notifications
        (``library_id IS NULL``) are NOT deleted.
        """
        async with with_span(
            "orchestration.notifications.purge_library",
            library_id=library_id,
        ):
            stmt = notifications_table.delete().where(
                notifications_table.c.library_id == library_id
            )
            async with self._sessionmaker() as session, session.begin():
                await session.execute(stmt)
            await logger.ainfo("notifications_purged", library_id=library_id)

    async def listen(
        self,
        *,
        poll_interval_s: float = 1.0,
    ) -> AsyncIterator[NotificationId]:
        """Yield IDs of newly-inserted notifications via Postgres LISTEN.

        Falls back to a polling iterator (every ``poll_interval_s``) when
        no asyncpg DSN was supplied, so SQLite/test environments still see
        events. Note: payload from NOTIFY is a JSON object {"id": ulid,
        "library_id": ...}; only ``id`` is used by the SSE handler — the
        full row is re-fetched (8 KB cap, ADR-0011 §1).
        """
        if self._listen_dsn is None:
            async for nid in self._poll_loop(poll_interval_s):
                yield nid
            return

        try:
            import asyncpg  # noqa: PLC0415 — optional listen path
        except ImportError as exc:  # pragma: no cover — dep ships in pyproject
            raise NotificationStoreError("asyncpg is required for LISTEN/NOTIFY") from exc

        conn = await asyncpg.connect(self._listen_dsn)
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1024)

        def _on_notify(_conn: object, _pid: int, _channel: str, payload: str) -> None:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                return
            nid = data.get("id") if isinstance(data, dict) else None
            if isinstance(nid, str):
                queue.put_nowait(nid)

        try:
            await conn.add_listener(_LISTEN_CHANNEL, _on_notify)
            while True:
                yield await queue.get()
        finally:
            await conn.remove_listener(_LISTEN_CHANNEL, _on_notify)
            await conn.close()

    async def _poll_loop(self, interval_s: float) -> AsyncIterator[NotificationId]:
        """Polling fallback for environments without LISTEN/NOTIFY."""
        last_seen = datetime.now(UTC)
        while True:
            await asyncio.sleep(interval_s)
            stmt = (
                select(notifications_table.c.id, notifications_table.c.created_at)
                .where(notifications_table.c.created_at > last_seen)
                .order_by(notifications_table.c.created_at.asc())
                .limit(100)
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            for row in rows:
                last_seen = _ensure_aware(row["created_at"]) or last_seen
                yield cast(str, row["id"])
