"""L5-only cross-library activity reader (ADR-0014 §6).

This module is the **single sanctioned exception** to PRD §16.6's per-
library Protocol rule: it accepts a `library_ids: list[str]` parameter
to drive the S2 Library Dashboard's cross-library "Recent activity" feed.

The Protocol surfaces inside `packages/orchestration/activity.py` remain
strictly per-library; this reader lives intentionally in `apps/api/` so
`tach check` / dependency rules never see a cross-library SQL helper
inside `packages/`.

Underscore prefix marks it as API-layer private; nothing outside
`apps/api/routes/activity.py` (and its tests) should import it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.observability import with_span
from packages.orchestration.activity import ActivityEvent, ActivityType


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _decode_payload(raw: object) -> dict[str, object]:
    """JSONB columns may come back as either dict or str depending on driver."""
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


def _row_to_event(row: Mapping[str, Any]) -> ActivityEvent:
    return ActivityEvent(
        id=int(row["id"] or 0),
        library_id=row["library_id"],
        type=ActivityType(row["type"]),
        title=row["title"],
        summary=row.get("summary"),
        payload=_decode_payload(row.get("payload")),
        actor=row.get("actor") or "system",
        created_at=_ensure_aware(row.get("created_at")) or datetime.now(UTC),
    )


class ActivityCrossReader:
    """SQL helper that aggregates `activity_log` rows across libraries.

    Cross-library aggregation is permitted **only here** (PRD §16.6 L5
    read-only meta-view exception, ADR-0014 §1).
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
        since: datetime | None = None,
        until: datetime | None = None,
        types: Sequence[ActivityType] | None = None,
        limit: int = 50,
    ) -> tuple[ActivityEvent, ...]:
        """Return at most `limit` events whose `library_id` is in `library_ids`.

        Ordered newest-first via `(created_at DESC, id DESC)`. The hot index
        is `(library_id, created_at DESC)` (per ADR-0014 §2); Postgres uses
        index merge for the `ANY($1)` filter.
        """
        if not library_ids:
            return ()
        async with with_span(
            "api.activity.list_for_libraries",
            library_count=len(library_ids),
        ):
            type_values: list[str] | None = [t.value for t in types] if types else None
            sql = text(
                """
                SELECT id, library_id, type, title, summary, payload, actor, created_at
                FROM activity_log
                WHERE library_id = ANY(:library_ids)
                  AND (CAST(:since AS TIMESTAMPTZ) IS NULL OR created_at >= CAST(:since AS TIMESTAMPTZ))
                  AND (CAST(:until AS TIMESTAMPTZ) IS NULL OR created_at <= CAST(:until AS TIMESTAMPTZ))
                  AND (CAST(:types AS TEXT[]) IS NULL OR type = ANY(CAST(:types AS TEXT[])))
                ORDER BY created_at DESC, id DESC
                LIMIT :limit
                """
            )
            async with self._sessionmaker() as session:
                result = await session.execute(
                    sql,
                    {
                        "library_ids": list(library_ids),
                        "since": since,
                        "until": until,
                        "types": type_values,
                        "limit": int(limit),
                    },
                )
                rows = result.mappings().all()
            return tuple(_row_to_event(cast(Mapping[str, Any], r)) for r in rows)
