"""Postgres-backed library status checker (ADR-0013).

Periodic worker job lives in ``apps/worker/jobs/library_status_check.py``;
this adapter does the actual evaluation + advisory-lock-protected write.
The state-machine logic itself is a pure function in
``packages/orchestration/_internal/status_evaluator.py`` (testable in
isolation).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import structlog
from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
    select,
    text,
    update,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.core.models import LibraryStatus
from packages.observability import with_span
from packages.orchestration._internal.status_evaluator import (
    StatusDecision,
    StatusInputs,
    evaluate,
)
from packages.orchestration.activity import ActivityEvent, ActivityType
from packages.orchestration.adapters.postgres_activity import (
    PostgresActivityLogger,
)
from packages.orchestration.adapters.postgres_notifications import (
    PostgresNotificationStore,
)
from packages.orchestration.errors import LibraryStatusEvaluationError
from packages.orchestration.library_status import LibraryStatusEvaluation
from packages.orchestration.notifications import NotificationType, Severity

logger = structlog.get_logger(__name__)

_metadata = MetaData()

# Mirror of the libraries table (status columns added in M7 per ADR-0013 §1).
libraries_status_table = Table(
    "libraries",
    _metadata,
    Column("library_id", Text, primary_key=True),
    Column("status", Text, nullable=False),
    Column("status_updated_at", DateTime(timezone=True), nullable=False),
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _severity_for(status: LibraryStatus) -> Severity:
    if status is LibraryStatus.STALE_COMMUNITY:
        return "warning"
    return "info"


def _advisory_lock_key(library_id: str) -> int:
    """Map a library_id to a 31-bit positive int for ``pg_advisory_xact_lock``."""
    # Stable hash; we do NOT need cryptographic strength — just collision-free
    # within the single-process worker (ADR-0013 §S02 documents the v2
    # multi-worker tightening).
    return abs(hash(("library_status", library_id))) & 0x7FFFFFFF


class StatusFactsProvider:
    """Read-only collaborator that supplies the inputs to the evaluator.

    Splitting this out lets the unit tests inject deterministic facts
    without spinning up Qdrant / Neo4j / a community store.
    """

    async def active_index_tasks(self, library_id: str) -> int:  # pragma: no cover
        return 0

    async def last_community_rebuild(self, library_id: str) -> datetime | None:  # pragma: no cover
        return None

    async def new_docs_since(self, library_id: str, since: datetime) -> int:  # pragma: no cover
        return 0


class PostgresLibraryStatusChecker:
    """Idempotent status evaluator (ADR-0013)."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        facts: StatusFactsProvider,
        activity: PostgresActivityLogger | None = None,
        notifier: PostgresNotificationStore | None = None,
    ) -> None:
        self._engine = engine
        self._facts = facts
        self._activity = activity
        self._notifier = notifier
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def evaluate(self, library_id: str) -> LibraryStatusEvaluation:
        """Run a single evaluation pass under an advisory lock."""
        async with with_span(
            "orchestration.library_status.evaluate",
            library_id=library_id,
        ):
            try:
                current = await self._read_current(library_id)
                if current is None:
                    raise LibraryStatusEvaluationError(f"Library not found: {library_id}")
                facts = await self._collect_facts(library_id, current)
                decision = evaluate(facts)
                if decision.new_status == current.status:
                    if decision.stuck_in_indexing:
                        await self._emit_stuck_alert(library_id)
                    return LibraryStatusEvaluation(
                        library_id=library_id,
                        previous_status=current.status,
                        new_status=current.status,
                        reason="no change: " + decision.reason,
                        evaluated_at=facts.now,
                    )
                await self._transition(
                    library_id=library_id,
                    previous=current.status,
                    decision=decision,
                    evaluated_at=facts.now,
                )
                if decision.stuck_in_indexing:
                    await self._emit_stuck_alert(library_id)
                return LibraryStatusEvaluation(
                    library_id=library_id,
                    previous_status=current.status,
                    new_status=decision.new_status,
                    reason=decision.reason,
                    evaluated_at=facts.now,
                )
            except LibraryStatusEvaluationError:
                raise
            except SQLAlchemyError as exc:
                raise LibraryStatusEvaluationError(
                    f"library_status evaluate failed: {library_id}"
                ) from exc

    async def evaluate_all(self) -> tuple[LibraryStatusEvaluation, ...]:
        """Iterate every library and evaluate each (L5-orchestration only)."""
        async with self._sessionmaker() as session:
            result = await session.execute(select(libraries_status_table.c.library_id))
            rows = result.scalars().all()
        out: list[LibraryStatusEvaluation] = []
        for library_id in rows:
            try:
                out.append(await self.evaluate(cast(str, library_id)))
            except LibraryStatusEvaluationError as exc:
                await logger.aerror(
                    "library_status_evaluate_one_failed",
                    library_id=library_id,
                    error=repr(exc),
                )
        return tuple(out)

    async def _read_current(self, library_id: str) -> _CurrentStatusRow | None:
        stmt = select(libraries_status_table).where(
            libraries_status_table.c.library_id == library_id
        )
        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            row = result.mappings().first()
        if row is None:
            return None
        status_raw = row.get("status") or LibraryStatus.HEALTHY.value
        return _CurrentStatusRow(
            status=LibraryStatus(status_raw),
            status_updated_at=_ensure_aware(row.get("status_updated_at")),
        )

    async def _collect_facts(
        self,
        library_id: str,
        current: _CurrentStatusRow,
    ) -> StatusInputs:
        active = await self._facts.active_index_tasks(library_id)
        last_rebuild = await self._facts.last_community_rebuild(library_id)
        if last_rebuild is not None:
            new_docs = await self._facts.new_docs_since(library_id, last_rebuild)
        else:
            new_docs = 0
        return StatusInputs(
            library_id=library_id,
            current_status=current.status,
            status_updated_at=current.status_updated_at,
            active_index_tasks=active,
            last_community_rebuild=last_rebuild,
            new_docs_since_rebuild=new_docs,
            now=datetime.now(UTC),
        )

    async def _transition(
        self,
        *,
        library_id: str,
        previous: LibraryStatus,
        decision: StatusDecision,
        evaluated_at: datetime,
    ) -> None:
        """Acquire advisory lock + double-check + write + emit follow-ups."""
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                text("SELECT pg_advisory_xact_lock(:k)"),
                {"k": _advisory_lock_key(library_id)},
            )
            recheck = await session.execute(
                select(libraries_status_table).where(
                    libraries_status_table.c.library_id == library_id
                )
            )
            row = recheck.mappings().first()
            if row is None:
                return
            current_status = LibraryStatus(row["status"])
            if current_status == decision.new_status:
                return
            await session.execute(
                update(libraries_status_table)
                .where(libraries_status_table.c.library_id == library_id)
                .values(
                    status=decision.new_status.value,
                    status_updated_at=evaluated_at,
                )
            )
        # Side effects after commit: activity log + notification
        if self._activity is not None:
            try:
                await self._activity.record(
                    ActivityEvent(
                        library_id=library_id,
                        type=ActivityType.LIBRARY_STATUS_CHANGED,
                        title=(f"Status: {previous.value} → {decision.new_status.value}"),
                        summary=decision.reason,
                        payload={
                            "from": previous.value,
                            "to": decision.new_status.value,
                            "reason": decision.reason,
                        },
                        actor="library_status_check",
                        created_at=evaluated_at,
                    )
                )
            except Exception as exc:
                await logger.aerror(
                    "library_status_activity_failed",
                    library_id=library_id,
                    error=repr(exc),
                )
        # Stale → Healthy is silenced per ADR-0013 §6.
        if (
            previous is LibraryStatus.STALE_COMMUNITY
            and decision.new_status is LibraryStatus.HEALTHY
        ):
            return
        if self._notifier is not None:
            try:
                await self._notifier.emit(
                    library_id=library_id,
                    notification_type=NotificationType.LIBRARY_STATUS_CHANGED,
                    severity=_severity_for(decision.new_status),
                    title=f"Library '{library_id}' is now {decision.new_status.value}",
                    body=decision.reason,
                    payload={
                        "from": previous.value,
                        "to": decision.new_status.value,
                    },
                    dedup_key=(
                        f"status:{library_id}:{previous.value}->"
                        f"{decision.new_status.value}:{evaluated_at.date().isoformat()}"
                    ),
                )
            except Exception as exc:
                await logger.aerror(
                    "library_status_notify_failed",
                    library_id=library_id,
                    error=repr(exc),
                )

    async def _emit_stuck_alert(self, library_id: str) -> None:
        if self._notifier is None:
            return
        today_iso = datetime.now(UTC).date().isoformat()
        try:
            await self._notifier.emit(
                library_id=library_id,
                notification_type=NotificationType.ALERT_TRIGGERED,
                severity="warning",
                title=(f"Library '{library_id}' has been Indexing for over 24h"),
                body=(
                    "Possible stuck job; investigate the worker queue or "
                    "manually reset via the admin endpoint."
                ),
                payload={"library_id": library_id},
                dedup_key=f"stuck-indexing:{library_id}:{today_iso}",
            )
        except Exception as exc:
            await logger.aerror(
                "library_status_stuck_notify_failed",
                library_id=library_id,
                error=repr(exc),
            )


class _CurrentStatusRow:
    """Tiny value-object for the current status snapshot (private)."""

    __slots__ = ("status", "status_updated_at")

    def __init__(
        self,
        *,
        status: LibraryStatus,
        status_updated_at: datetime | None,
    ) -> None:
        self.status = status
        self.status_updated_at = status_updated_at
