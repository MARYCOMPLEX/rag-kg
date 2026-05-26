"""Postgres-backed daily cost cap enforcer (ADR-0015).

Atomic ``INSERT ... ON CONFLICT DO UPDATE`` against the
``library_daily_cost`` (library_id, date) composite-PK table. Edge-
triggered warnings: emit ``daily_cost_warning`` once per day at 80 % and
``daily_cost_blocked`` once per day at 100 %; deduplication is enforced
via the notification ``dedup_key`` of the form
``cost-warn:<library_id>:<YYYY-MM-DD>``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from datetime import date as Date
from decimal import Decimal
from typing import cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    and_,
    select,
)
from sqlalchemy import (
    Date as SADate,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.observability import with_span
from packages.orchestration.adapters.postgres_library_config import (
    PostgresLibraryConfigStore,
)
from packages.orchestration.adapters.postgres_notifications import (
    PostgresNotificationStore,
)
from packages.orchestration.cost import CostCheckResult, LibraryDailyCost
from packages.orchestration.errors import OrchestrationError
from packages.orchestration.notifications import NotificationType

logger = structlog.get_logger(__name__)

_metadata = MetaData()

library_daily_cost_table = Table(
    "library_daily_cost",
    _metadata,
    Column("library_id", Text, primary_key=True),
    Column("date", SADate, primary_key=True),
    Column("cost_usd", Numeric(12, 6), nullable=False, default=Decimal("0")),
    Column("llm_calls", Integer, nullable=False, default=0),
    Column("last_updated_at", DateTime(timezone=True), nullable=False),
)


def _today(timezone_name: str) -> Date:
    """Return the current calendar date in the configured IANA timezone."""
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = UTC
    return datetime.now(tz).date()


def _next_reset_at(today: Date, timezone_name: str) -> datetime:
    """Compute the start of the next day in the library's timezone (UTC)."""
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = UTC
    next_local = datetime.combine(today + timedelta(days=1), datetime.min.time(), tz)
    return next_local.astimezone(UTC)


def _row_to_daily_cost(library_id: str, on_date: Date, row: object) -> LibraryDailyCost | None:
    if row is None:
        return None
    mapping = cast(dict[str, object], row)
    spent = Decimal(str(mapping.get("cost_usd") or "0"))
    calls = int(cast(int, mapping.get("llm_calls") or 0))
    last_updated = mapping.get("last_updated_at")
    if isinstance(last_updated, datetime):
        last_dt = (
            last_updated if last_updated.tzinfo is not None else last_updated.replace(tzinfo=UTC)
        )
    else:
        last_dt = datetime.now(UTC)
    return LibraryDailyCost(
        library_id=library_id,
        date=on_date,
        cost_usd=spent,
        llm_calls=calls,
        last_updated_at=last_dt,
    )


def _decide(
    *,
    spent: Decimal,
    cap: Decimal | None,
    warn_pct: float,
) -> tuple[str, float]:
    """Map (spent, cap) → (decision, ratio).

    Returns ``("allow"|"warn"|"blocked", ratio in [0, +inf))``.
    """
    if cap is None or cap <= Decimal("0"):
        return "allow", 0.0
    ratio = float(spent / cap) if cap else 0.0
    if spent >= cap:
        return "blocked", ratio
    if ratio >= warn_pct:
        return "warn", ratio
    return "allow", ratio


class PostgresCostCapEnforcer:
    """Adapter for ``library_daily_cost`` table (ADR-0015).

    Reads per-library cap from ``LibraryConfigStore``; counter is single-
    source-of-truth in Postgres (Langfuse trace stays advisory).
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        config_store: PostgresLibraryConfigStore,
        notifier: PostgresNotificationStore | None = None,
    ) -> None:
        self._engine = engine
        self._config_store = config_store
        self._notifier = notifier
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def check(self, library_id: str) -> CostCheckResult:
        """Read current spend; do NOT increment.

        Used at task admission (Gate 1, ADR-0015 §3) before allocating a
        new background job.
        """
        config = await self._config_store.get(library_id)
        cap = config.daily_cost_cap_usd
        warn_pct = config.cost_cap_warn_pct
        today = _today(config.timezone)
        spent = await self._fetch_spent(library_id, today)
        decision, ratio = _decide(spent=spent, cap=cap, warn_pct=warn_pct)
        return CostCheckResult(
            library_id=library_id,
            decision=decision,
            spent_usd=spent,
            cap_usd=cap,
            pct_used=ratio,
            next_reset_at=_next_reset_at(today, config.timezone),
        )

    async def record(
        self,
        library_id: str,
        cost_usd: Decimal,
        llm_calls: int = 1,
    ) -> CostCheckResult:
        """Atomically accumulate spend and emit edge-triggered notifications.

        Called by the LLM gateway middleware after every successful LLM
        response (Gate 2, ADR-0015 §3 — accounting only, never blocks).
        """
        if cost_usd < Decimal("0"):
            msg = "cost_usd must be non-negative"
            raise OrchestrationError(msg)
        if llm_calls < 0:
            msg = "llm_calls must be non-negative"
            raise OrchestrationError(msg)

        config = await self._config_store.get(library_id)
        cap = config.daily_cost_cap_usd
        warn_pct = config.cost_cap_warn_pct
        today = _today(config.timezone)

        async with with_span(
            "orchestration.cost.record",
            library_id=library_id,
        ):
            previous = await self._fetch_spent(library_id, today)
            try:
                async with self._sessionmaker() as session, session.begin():
                    stmt = pg_insert(library_daily_cost_table).values(
                        library_id=library_id,
                        date=today,
                        cost_usd=cost_usd,
                        llm_calls=llm_calls,
                        last_updated_at=datetime.now(UTC),
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["library_id", "date"],
                        set_={
                            "cost_usd": (library_daily_cost_table.c.cost_usd + cost_usd),
                            "llm_calls": (library_daily_cost_table.c.llm_calls + llm_calls),
                            "last_updated_at": datetime.now(UTC),
                        },
                    )
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                await logger.aerror(
                    "cost_record_failed",
                    library_id=library_id,
                    cost_usd=str(cost_usd),
                    error=repr(exc),
                )
                # Per ADR-0015 §Risks: do NOT roll back the upstream LLM
                # response — under-count is preferable to user-visible failure.
                raise OrchestrationError("cost record failed") from exc

            new_total = previous + cost_usd
            decision, ratio = _decide(spent=new_total, cap=cap, warn_pct=warn_pct)
            await self._maybe_emit_threshold(
                library_id=library_id,
                today=today,
                previous=previous,
                new_total=new_total,
                cap=cap,
                warn_pct=warn_pct,
                timezone=config.timezone,
            )
            return CostCheckResult(
                library_id=library_id,
                decision=decision,
                spent_usd=new_total,
                cap_usd=cap,
                pct_used=ratio,
                next_reset_at=_next_reset_at(today, config.timezone),
            )

    async def history(
        self,
        library_id: str,
        *,
        days: int = 30,
    ) -> tuple[LibraryDailyCost, ...]:
        """Return last ``days`` rows for the cost-trend panel."""
        config = await self._config_store.get(library_id)
        today = _today(config.timezone)
        since = today - timedelta(days=max(days - 1, 0))
        async with with_span(
            "orchestration.cost.history",
            library_id=library_id,
        ):
            stmt = (
                select(library_daily_cost_table)
                .where(
                    and_(
                        library_daily_cost_table.c.library_id == library_id,
                        library_daily_cost_table.c.date >= since,
                    )
                )
                .order_by(library_daily_cost_table.c.date.desc())
                .limit(days)
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
        out: list[LibraryDailyCost] = []
        for row in rows:
            on_date = cast(Date, row["date"])
            entry = _row_to_daily_cost(library_id, on_date, row)
            if entry is not None:
                out.append(entry)
        return tuple(out)

    async def purge_library(self, library_id: str) -> None:
        async with with_span(
            "orchestration.cost.purge_library",
            library_id=library_id,
        ):
            try:
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(
                        library_daily_cost_table.delete().where(
                            library_daily_cost_table.c.library_id == library_id
                        )
                    )
            except SQLAlchemyError as exc:
                raise OrchestrationError(f"cost purge failed: {library_id}") from exc

    async def _fetch_spent(self, library_id: str, on_date: Date) -> Decimal:
        stmt = select(library_daily_cost_table.c.cost_usd).where(
            and_(
                library_daily_cost_table.c.library_id == library_id,
                library_daily_cost_table.c.date == on_date,
            )
        )
        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            row = result.first()
        if row is None:
            return Decimal("0")
        return Decimal(str(row[0] or "0"))

    async def _maybe_emit_threshold(
        self,
        *,
        library_id: str,
        today: Date,
        previous: Decimal,
        new_total: Decimal,
        cap: Decimal | None,
        warn_pct: float,
        timezone: str,
    ) -> None:
        """Edge-triggered: only fire when crossing 80 % or 100 % the first time today."""
        if self._notifier is None or cap is None or cap <= Decimal("0"):
            return
        warn_threshold = cap * Decimal(str(warn_pct))
        crossed_warn = previous < warn_threshold <= new_total
        crossed_block = previous < cap <= new_total
        date_iso = today.isoformat()
        reset_at = _next_reset_at(today, timezone).isoformat()
        if crossed_block:
            await self._notifier.emit(
                library_id=library_id,
                notification_type=NotificationType.DAILY_COST_BLOCKED,
                severity="danger",
                title=(f"Daily cost cap of ${cap} reached for library '{library_id}'"),
                body=(
                    "New tasks will be refused until the next reset. "
                    "Adjust the cap from per-library settings if needed."
                ),
                payload={
                    "library_id": library_id,
                    "date": date_iso,
                    "today_cost_usd": str(new_total),
                    "cap_usd": str(cap),
                    "ratio": float(new_total / cap),
                    "reset_at": reset_at,
                },
                dedup_key=f"cost-block:{library_id}:{date_iso}",
            )
            return
        if crossed_warn:
            await self._notifier.emit(
                library_id=library_id,
                notification_type=NotificationType.DAILY_COST_WARNING,
                severity="warning",
                title=(
                    f"Library '{library_id}' has spent {warn_pct * 100:.0f}% of its daily cost cap"
                ),
                payload={
                    "library_id": library_id,
                    "date": date_iso,
                    "today_cost_usd": str(new_total),
                    "cap_usd": str(cap),
                    "warn_pct": warn_pct,
                    "reset_at": reset_at,
                },
                dedup_key=f"cost-warn:{library_id}:{date_iso}",
            )
