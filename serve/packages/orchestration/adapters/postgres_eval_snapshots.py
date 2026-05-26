"""Postgres-backed eval snapshot adapter (ADR-0016 §5 + ADR-0021).

Wraps the ``eval_snapshots`` table whose composite primary key is
``(library_id, date, eval_set, metric)`` per ADR-0016 §5. Implements the
``EvalSnapshotter`` Protocol from
``packages.orchestration.eval_protocols``.

The Protocol's ``write_daily`` is delegated to a pluggable
``DailyEvalSnapshotter`` (defined in ``packages.evaluation.snapshot``)
which computes the four metrics from a sample source. This adapter holds
two responsibilities:

  * **Persistence** — row-level ``write_one`` plus the single-shot
    ``write_daily`` Protocol entry that fans out across configured eval
    sets.
  * **Queries** — ``get_kpis`` (Eval Dashboard cards) and ``get_trend``
    (sparkline / 30-day trend).

Library scope is enforced as a WHERE clause on every read.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from datetime import date as Date
from decimal import Decimal
from typing import Any, cast

import structlog
from sqlalchemy import (
    JSON,
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
from packages.orchestration.errors import OrchestrationError
from packages.orchestration.eval_models import (
    EvalKPIs,
    EvalSet,
    EvalSnapshot,
    Metric,
)

logger = structlog.get_logger(__name__)

_KPI_METRICS: tuple[Metric, ...] = (
    "var",
    "citation_f1",
    "p95_latency_s",
    "avg_cost_usd",
)
_DEFAULT_EVAL_SETS: tuple[EvalSet, ...] = ("smoke",)

_metadata = MetaData()

eval_snapshots_table = Table(
    "eval_snapshots",
    _metadata,
    Column("library_id", Text, primary_key=True),
    Column("date", SADate, primary_key=True),
    Column("eval_set", Text, primary_key=True),
    Column("metric", Text, primary_key=True),
    Column("value", Numeric(18, 6), nullable=False),
    Column("sample_size", Integer, nullable=False, default=0),
    Column("extra", JSON, nullable=True),
    Column("computed_at", DateTime(timezone=True), nullable=False),
)


# -- Per-day driver Protocol shape (kept narrow on purpose) -----------------
#
# `DailyEvalSnapshotter.write_for_day(library_id, eval_set=..., day=...)`
# from `packages.evaluation.snapshot` matches this signature; we duck-type
# on it so unit tests can pass a fake.
type _DailyDriver = Callable[
    [str, EvalSet, Date],
    "Any",  # actually Awaitable[tuple[EvalSnapshot, ...]]
]


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _row_to_snapshot(row: Mapping[str, Any]) -> EvalSnapshot:
    return EvalSnapshot(
        library_id=row["library_id"],
        date=cast(Date, row["date"]),
        eval_set=cast(EvalSet, row["eval_set"]),
        metric=cast(Metric, row["metric"]),
        value=float(row["value"] or 0.0),
        sample_size=int(row["sample_size"] or 0),
        computed_at=_ensure_aware(row["computed_at"]) or datetime.now(UTC),
    )


def _index_by_metric(
    rows: Sequence[EvalSnapshot],
) -> dict[Metric, EvalSnapshot]:
    """Last-writer-wins keyed by metric — newest snapshot per KPI."""
    out: dict[Metric, EvalSnapshot] = {}
    for row in rows:
        existing = out.get(row.metric)
        if existing is None or row.date > existing.date:
            out[row.metric] = row
    return out


class PostgresEvalSnapshotter:
    """Adapter for ``eval_snapshots`` (ADR-0016 §5 + ADR-0021).

    Construction takes an ``AsyncEngine`` and an optional ``daily_driver``
    callable that performs the compute-and-persist for one day. When
    ``daily_driver`` is ``None``, ``write_daily`` is a no-op (test
    environments / cron not yet wired) and emits a structured log.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        daily_driver: _DailyDriver | None = None,
        eval_sets: Sequence[EvalSet] = _DEFAULT_EVAL_SETS,
    ) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )
        self._daily_driver = daily_driver
        self._eval_sets = tuple(eval_sets)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def write_one(self, row: EvalSnapshot) -> None:
        """Upsert a single snapshot row (last-writer-wins on PK)."""
        async with with_span("orchestration.eval_snapshots.write_one", library_id=row.library_id):
            try:
                stmt = pg_insert(eval_snapshots_table).values(
                    library_id=row.library_id,
                    date=row.date,
                    eval_set=row.eval_set,
                    metric=row.metric,
                    value=Decimal(str(row.value)),
                    sample_size=row.sample_size,
                    extra=None,
                    computed_at=row.computed_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        "library_id",
                        "date",
                        "eval_set",
                        "metric",
                    ],
                    set_={
                        "value": Decimal(str(row.value)),
                        "sample_size": row.sample_size,
                        "computed_at": row.computed_at,
                    },
                )
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                await logger.aerror(
                    "eval_snapshot_write_failed",
                    library_id=row.library_id,
                    metric=row.metric,
                    error=repr(exc),
                )
                raise OrchestrationError("eval snapshot write failed") from exc

    async def write_daily(
        self,
        library_id: str,
        *,
        as_of: Date,
    ) -> tuple[EvalSnapshot, ...]:
        """Compute + persist all metrics for the day across configured eval sets.

        Delegates to the injected ``daily_driver``; if absent, logs a
        structured warning and returns an empty tuple so the worker cron
        can still run in degraded environments.
        """
        async with with_span("orchestration.eval_snapshots.write_daily", library_id=library_id):
            if self._daily_driver is None:
                await logger.awarning(
                    "eval_snapshots_daily_driver_missing",
                    library_id=library_id,
                    as_of=as_of.isoformat(),
                )
                return ()
            rows: list[EvalSnapshot] = []
            for eval_set in self._eval_sets:
                day_rows = await self._daily_driver(library_id, eval_set, as_of)
                rows.extend(day_rows)
            return tuple(rows)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get_kpis(
        self,
        library_id: str,
        *,
        eval_set: EvalSet,
    ) -> EvalKPIs | None:
        """Aggregate the latest 7-day window into a Dashboard card row."""
        async with with_span("orchestration.eval_snapshots.get_kpis", library_id=library_id):
            today = datetime.now(UTC).date()
            since_recent = today - timedelta(days=7)
            since_prior = today - timedelta(days=14)
            stmt = (
                select(eval_snapshots_table)
                .where(
                    and_(
                        eval_snapshots_table.c.library_id == library_id,
                        eval_snapshots_table.c.eval_set == eval_set,
                        eval_snapshots_table.c.date >= since_prior,
                    )
                )
                .order_by(eval_snapshots_table.c.date.asc())
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = [
                    _row_to_snapshot(cast(Mapping[str, Any], r)) for r in result.mappings().all()
                ]
        if not rows:
            return None
        recent = [r for r in rows if r.date >= since_recent]
        prior = [r for r in rows if since_prior <= r.date < since_recent]
        if not recent:
            return None
        recent_by_metric = _index_by_metric(recent)
        prior_by_metric = _index_by_metric(prior)
        var_row = recent_by_metric.get("var")
        cit_row = recent_by_metric.get("citation_f1")
        p95_row = recent_by_metric.get("p95_latency_s")
        cost_row = recent_by_metric.get("avg_cost_usd")
        delta_7d: dict[Metric, float] = {}
        for metric in _KPI_METRICS:
            cur = recent_by_metric.get(metric)
            prev = prior_by_metric.get(metric)
            if cur is not None and prev is not None:
                delta_7d[metric] = cur.value - prev.value
        sample_size = max(
            (row.sample_size for row in recent_by_metric.values()),
            default=0,
        )
        computed_at = max(
            (row.computed_at for row in recent_by_metric.values()),
            default=datetime.now(UTC),
        )
        return EvalKPIs(
            library_id=library_id,
            eval_set=eval_set,
            var=_clamped(var_row.value if var_row is not None else 0.0),
            citation_f1=_clamped(cit_row.value if cit_row is not None else 0.0),
            p95_latency_s=max(p95_row.value if p95_row is not None else 0.0, 0.0),
            avg_cost_usd=Decimal(str(cost_row.value if cost_row is not None else 0.0)),
            delta_1d={},
            delta_7d=delta_7d,
            sample_size=sample_size,
            computed_at=computed_at,
        )

    async def get_trend(
        self,
        library_id: str,
        *,
        metric: Metric,
        eval_set: EvalSet,
        days: int = 30,
    ) -> tuple[EvalSnapshot, ...]:
        """Return the (metric, eval_set) trend for the last ``days``."""
        async with with_span("orchestration.eval_snapshots.get_trend", library_id=library_id):
            today = datetime.now(UTC).date()
            since = today - timedelta(days=max(days - 1, 0))
            stmt = (
                select(eval_snapshots_table)
                .where(
                    and_(
                        eval_snapshots_table.c.library_id == library_id,
                        eval_snapshots_table.c.eval_set == eval_set,
                        eval_snapshots_table.c.metric == metric,
                        eval_snapshots_table.c.date >= since,
                    )
                )
                .order_by(eval_snapshots_table.c.date.asc())
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            return tuple(_row_to_snapshot(cast(Mapping[str, Any], r)) for r in rows)

    async def list_for_alert_window(
        self,
        library_id: str,
        *,
        days: int = 30,
    ) -> tuple[EvalSnapshot, ...]:
        """Return every snapshot in a window — used by ``AlertEngine``.

        Not part of the ``EvalSnapshotter`` Protocol; ``PostgresAlertEngine``
        composes this adapter directly to fetch the window it needs.
        """
        async with with_span(
            "orchestration.eval_snapshots.list_for_alert_window",
            library_id=library_id,
        ):
            today = datetime.now(UTC).date()
            since = today - timedelta(days=max(days - 1, 0))
            stmt = (
                select(eval_snapshots_table)
                .where(
                    and_(
                        eval_snapshots_table.c.library_id == library_id,
                        eval_snapshots_table.c.date >= since,
                    )
                )
                .order_by(eval_snapshots_table.c.date.asc())
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            return tuple(_row_to_snapshot(cast(Mapping[str, Any], r)) for r in rows)

    async def list_failures(
        self,
        library_id: str,
        *,
        days: int = 30,
        limit: int = 20,
    ) -> tuple[EvalSnapshot, ...]:
        """Return low-VAR samples (var < 0.5) as a "failure case" feed.

        Eval Dashboard §Failures table — picks days where ``var < 0.5``
        for the smoke set, newest first.
        """
        async with with_span(
            "orchestration.eval_snapshots.list_failures",
            library_id=library_id,
        ):
            today = datetime.now(UTC).date()
            since = today - timedelta(days=max(days - 1, 0))
            stmt = (
                select(eval_snapshots_table)
                .where(
                    and_(
                        eval_snapshots_table.c.library_id == library_id,
                        eval_snapshots_table.c.metric == "var",
                        eval_snapshots_table.c.date >= since,
                        eval_snapshots_table.c.value < Decimal("0.5"),
                    )
                )
                .order_by(eval_snapshots_table.c.date.desc())
                .limit(limit)
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            return tuple(_row_to_snapshot(cast(Mapping[str, Any], r)) for r in rows)

    async def purge_library(self, library_id: str) -> None:
        """Delete every snapshot row for a Library (ADR-0022 saga)."""
        async with with_span(
            "orchestration.eval_snapshots.purge_library",
            library_id=library_id,
        ):
            stmt = eval_snapshots_table.delete().where(
                eval_snapshots_table.c.library_id == library_id
            )
            try:
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                raise OrchestrationError(f"eval snapshots purge failed: {library_id}") from exc
            await logger.ainfo("eval_snapshots_purged", library_id=library_id)


def _clamped(value: float) -> float:
    """Clamp to [0, 1] — protects pydantic constraints on ``EvalKPIs``."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


__all__ = ["PostgresEvalSnapshotter", "eval_snapshots_table"]
