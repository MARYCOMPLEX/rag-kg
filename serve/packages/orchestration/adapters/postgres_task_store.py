"""Postgres-backed durable task state store (ADR-0009 §4).

The Arq queue stores ephemeral metadata in Redis but the **single source of
truth** for task lifecycle is the `tasks` table. This module wraps SQLAlchemy
2.0 core async statements behind a small async API that the
`ArqTaskQueue` calls.

Library scope (`library_id`) is enforced as a WHERE clause on every read
so a task in Library A is invisible from Library B even if its `task_id`
were guessed (CODING_STANDARDS §6.5).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, cast

import structlog
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    and_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.core.models import Library
from packages.observability import with_span
from packages.orchestration.queue import (
    BudgetSpec,
    TaskHandle,
    TaskId,
    TaskSpec,
    TaskState,
    TaskType,
)

logger = structlog.get_logger(__name__)

# ----------------------------------------------------------------------
# Table definition (mirrors migration `m7_002_task_queue.py`)
# ----------------------------------------------------------------------

_metadata = MetaData()

libraries_table = Table(
    "libraries",
    _metadata,
    Column("library_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("domain", Text, nullable=True),
    Column("language", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("status_updated_at", DateTime(timezone=True), nullable=True),
)

tasks_table = Table(
    "tasks",
    _metadata,
    Column("task_id", Text, primary_key=True),
    Column("library_id", Text, nullable=False),
    Column("task_type", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("progress", Float, nullable=False, default=0.0),
    Column("current_stage", Text, nullable=True),
    Column("input_payload", JSON, nullable=False),
    Column("budget", JSON, nullable=True),
    Column("priority", Integer, nullable=False, default=0),
    Column("dedup_key", Text, nullable=True),
    Column("result_pointer", Text, nullable=True),
    Column("error", Text, nullable=True),
    Column("enqueued_at", DateTime(timezone=True), nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("finished_at", DateTime(timezone=True), nullable=True),
    Column("created_by", Text, nullable=True),
    Column("cost_usd", Numeric(10, 6), nullable=False, default=0),
)


_TerminalStatus = Literal["completed", "failed", "cancelled"]
_NonTerminalStatus = Literal["queued", "running"]
TaskStatus = Literal[_NonTerminalStatus, _TerminalStatus]


def _ensure_aware(dt: datetime | None) -> datetime | None:
    """Force a UTC tzinfo so cross-DB DATETIME types compare consistently."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _row_to_state(row: Mapping[str, Any]) -> TaskState:
    """Map a SQLAlchemy Row mapping to a `TaskState` Pydantic model."""
    return TaskState(
        library_id=row["library_id"],
        task_id=row["task_id"],
        task_type=cast(TaskType, row["task_type"]),
        status=cast(TaskStatus, row["status"]),
        progress=float(row["progress"] or 0.0),
        current_stage=row["current_stage"],
        enqueued_at=_ensure_aware(row["enqueued_at"]) or datetime.now(UTC),
        started_at=_ensure_aware(row["started_at"]),
        finished_at=_ensure_aware(row["finished_at"]),
        error=row["error"],
        result_pointer=row["result_pointer"],
        cost_usd=float(row["cost_usd"] or 0.0),
    )


def _budget_to_json(budget: BudgetSpec | None) -> dict[str, Any] | None:
    if budget is None:
        return None
    return budget.model_dump(mode="json")


class PostgresTaskStore:
    """Durable persistence for the `tasks` table (ADR-0009)."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def ensure_library(self, library: Library) -> None:
        """Upsert a Library row so task-table FK checks match API-visible libraries."""
        async with with_span(
            "orchestration.postgres.library_ensure",
            library_id=library.library_id,
        ):
            row = {
                "library_id": library.library_id,
                "name": library.name,
                "description": library.description,
                "created_at": library.created_at,
                "domain": library.domain,
                "language": library.language,
                "status": str(library.status),
                "status_updated_at": library.status_updated_at,
            }
            stmt = pg_insert(libraries_table).values(**row)
            stmt = stmt.on_conflict_do_update(
                index_elements=[libraries_table.c.library_id],
                set_={
                    "name": stmt.excluded.name,
                    "description": stmt.excluded.description,
                    "domain": stmt.excluded.domain,
                    "language": stmt.excluded.language,
                    "status": stmt.excluded.status,
                    "status_updated_at": stmt.excluded.status_updated_at,
                },
            )
            async with self._sessionmaker() as session, session.begin():
                await session.execute(stmt)
            await logger.ainfo(
                "library_materialized_for_tasks",
                library_id=library.library_id,
            )

    async def insert(
        self,
        *,
        task_id: TaskId,
        spec: TaskSpec,
        enqueued_at: datetime,
    ) -> TaskHandle:
        """Insert a fresh `queued` row. Caller guarantees `task_id` is fresh."""
        async with with_span("orchestration.postgres.task_insert", library_id=spec.library_id):
            row = {
                "task_id": task_id,
                "library_id": spec.library_id,
                "task_type": spec.task_type,
                "status": "queued",
                "progress": 0.0,
                "current_stage": None,
                "input_payload": dict(spec.input_payload),
                "budget": _budget_to_json(spec.budget),
                "priority": spec.priority,
                "dedup_key": spec.dedup_key,
                "result_pointer": None,
                "error": None,
                "enqueued_at": enqueued_at,
                "started_at": None,
                "finished_at": None,
                "created_by": spec.created_by,
                "cost_usd": 0,
            }
            async with self._sessionmaker() as session, session.begin():
                await session.execute(tasks_table.insert().values(**row))
            await logger.ainfo(
                "task_persisted",
                library_id=spec.library_id,
                task_id=task_id,
                task_type=spec.task_type,
            )
            return TaskHandle(
                library_id=spec.library_id,
                task_id=task_id,
                enqueued_at=enqueued_at,
            )

    async def find_by_dedup_key(
        self,
        library_id: str,
        dedup_key: str,
    ) -> TaskState | None:
        """Look up an existing task with the same dedup_key in this library.

        Idempotency contract: re-enqueue with same dedup_key returns the
        original task instead of creating a duplicate (ADR-0009 R-Q3).
        """
        async with with_span("orchestration.postgres.dedup_lookup", library_id=library_id):
            stmt = select(tasks_table).where(
                and_(
                    tasks_table.c.library_id == library_id,
                    tasks_table.c.dedup_key == dedup_key,
                )
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                row = result.mappings().first()
            if row is None:
                return None
            return _row_to_state(dict(row))

    async def get(
        self,
        library_id: str,
        task_id: TaskId,
    ) -> TaskState | None:
        async with with_span("orchestration.postgres.task_get", library_id=library_id):
            stmt = select(tasks_table).where(
                and_(
                    tasks_table.c.library_id == library_id,
                    tasks_table.c.task_id == task_id,
                )
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                row = result.mappings().first()
            return None if row is None else _row_to_state(dict(row))

    async def list_active(
        self,
        library_id: str,
    ) -> tuple[TaskHandle, ...]:
        """Return queued + running tasks ordered by enqueued_at ASC."""
        async with with_span("orchestration.postgres.task_list_active", library_id=library_id):
            stmt = (
                select(
                    tasks_table.c.library_id,
                    tasks_table.c.task_id,
                    tasks_table.c.enqueued_at,
                )
                .where(
                    and_(
                        tasks_table.c.library_id == library_id,
                        tasks_table.c.status.in_(("queued", "running")),
                    )
                )
                .order_by(tasks_table.c.enqueued_at.asc())
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows: Sequence[Mapping[str, Any]] = cast(
                    "Sequence[Mapping[str, Any]]", result.mappings().all()
                )
        handles: list[TaskHandle] = []
        for row in rows:
            handles.append(
                TaskHandle(
                    library_id=row["library_id"],
                    task_id=row["task_id"],
                    enqueued_at=_ensure_aware(row["enqueued_at"]) or datetime.now(UTC),
                )
            )
        return tuple(handles)

    async def update_status(
        self,
        library_id: str,
        task_id: TaskId,
        *,
        status: TaskStatus,
        progress: float | None = None,
        current_stage: str | None = None,
        result_pointer: str | None = None,
        error: str | None = None,
        cost_usd: float | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> bool:
        """Atomically update mutable fields. Returns False if no row matched."""
        async with with_span("orchestration.postgres.task_update", library_id=library_id):
            values: dict[str, Any] = {"status": status}
            if progress is not None:
                values["progress"] = progress
            if current_stage is not None:
                values["current_stage"] = current_stage
            if result_pointer is not None:
                values["result_pointer"] = result_pointer
            if error is not None:
                values["error"] = error
            if cost_usd is not None:
                values["cost_usd"] = cost_usd
            if started_at is not None:
                values["started_at"] = started_at
            if finished_at is not None:
                values["finished_at"] = finished_at
            stmt = (
                update(tasks_table)
                .where(
                    and_(
                        tasks_table.c.library_id == library_id,
                        tasks_table.c.task_id == task_id,
                    )
                )
                .values(**values)
            )
            async with self._sessionmaker() as session, session.begin():
                result = await session.execute(stmt)
            return (cast(Any, result).rowcount or 0) > 0

    async def cancel_if_active(
        self,
        library_id: str,
        task_id: TaskId,
    ) -> bool:
        """Set status=cancelled iff currently queued/running. Atomic."""
        async with with_span("orchestration.postgres.task_cancel", library_id=library_id):
            now = datetime.now(UTC)
            stmt = (
                update(tasks_table)
                .where(
                    and_(
                        tasks_table.c.library_id == library_id,
                        tasks_table.c.task_id == task_id,
                        tasks_table.c.status.in_(("queued", "running")),
                    )
                )
                .values(status="cancelled", finished_at=now)
            )
            async with self._sessionmaker() as session, session.begin():
                result = await session.execute(stmt)
            return (cast(Any, result).rowcount or 0) > 0
