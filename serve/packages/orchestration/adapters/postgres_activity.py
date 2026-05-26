"""Postgres-backed activity log (ADR-0014).

Strict per-library writer + reader. Cross-library aggregation lives at
``apps/api/_activity_reader.py`` (the only L5 read-only meta-view, per
PRD §16.6 example). The Protocol surfaced from this module **never**
accepts ``library_ids: list``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
    and_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.observability import with_span
from packages.orchestration.activity import (
    ActivityEvent,
    ActivityType,
)
from packages.orchestration.errors import ActivityLogError

logger = structlog.get_logger(__name__)

_metadata = MetaData()

activity_log_table = Table(
    "activity_log",
    _metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("library_id", Text, nullable=False),
    Column("type", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("summary", Text, nullable=True),
    Column("payload", JSON, nullable=False),
    Column("actor", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _row_to_event(row: Mapping[str, Any]) -> ActivityEvent:
    raw = row["payload"]
    if isinstance(raw, str):
        try:
            payload = cast(dict[str, object], json.loads(raw))
        except json.JSONDecodeError:
            payload = {}
    elif isinstance(raw, dict):
        payload = cast(dict[str, object], raw)
    else:
        payload = {}
    return ActivityEvent(
        id=int(row["id"] or 0),
        library_id=row["library_id"],
        type=ActivityType(row["type"]),
        title=row["title"],
        summary=row["summary"],
        payload=payload,
        actor=row["actor"],
        created_at=_ensure_aware(row["created_at"]) or datetime.now(UTC),
    )


class PostgresActivityLogger:
    """Single-library activity recorder + reader (ADR-0014)."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def record(self, event: ActivityEvent) -> None:
        """Append one event row.

        ``event.id`` is server-assigned by Postgres (BIGSERIAL); any value
        the caller passes is ignored.
        """
        async with with_span(
            "orchestration.activity.record",
            library_id=event.library_id,
        ):
            try:
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(
                        activity_log_table.insert().values(
                            library_id=event.library_id,
                            type=event.type.value,
                            title=event.title,
                            summary=event.summary,
                            payload=dict(event.payload),
                            actor=event.actor,
                            created_at=event.created_at,
                        )
                    )
            except Exception as exc:
                await logger.aerror(
                    "activity_record_failed",
                    library_id=event.library_id,
                    type=event.type.value,
                    error=repr(exc),
                )
                raise ActivityLogError("activity record failed") from exc

            await logger.ainfo(
                "activity_recorded",
                library_id=event.library_id,
                type=event.type.value,
            )

    async def list_for_library(
        self,
        library_id: str,
        *,
        since: datetime | None = None,
        types: tuple[ActivityType, ...] | None = None,
        limit: int = 50,
    ) -> tuple[ActivityEvent, ...]:
        """Per-library list (single value, never a list of ids).

        ADR-0014 §5: the cross-library reader lives in `apps/api/`, not
        in this Protocol — keeping the L5 exception narrow.
        """
        async with with_span(
            "orchestration.activity.list_for_library",
            library_id=library_id,
        ):
            conditions = [activity_log_table.c.library_id == library_id]
            if since is not None:
                conditions.append(activity_log_table.c.created_at >= since)
            if types is not None and len(types) > 0:
                type_values: Sequence[str] = tuple(t.value for t in types)
                conditions.append(activity_log_table.c.type.in_(type_values))
            stmt = (
                select(activity_log_table)
                .where(and_(*conditions))
                .order_by(
                    activity_log_table.c.created_at.desc(),
                    activity_log_table.c.id.desc(),
                )
                .limit(limit)
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            return tuple(_row_to_event(dict(r)) for r in rows)
