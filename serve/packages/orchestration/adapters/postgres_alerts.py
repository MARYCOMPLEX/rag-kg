"""Postgres-backed eval alert engine (ADR-0021).

Wraps the ``alerts`` table whose offset-unique invariant
``UNIQUE INDEX (library_id, rule) WHERE status = 'active'`` guarantees a
single active row per (Library, rule) pair (ADR-0021 §3 + ADR-0021 §5
deduplication).

The pure rule logic lives in ``packages.evaluation.alerts`` (already
implemented). This adapter is the **state-machine driver**:

  * Fetch context (snapshots + cost) for a (Library, today)
  * Run every rule via the pure evaluator
  * Reconcile each rule's outcome with any existing active row:
      - new trigger    → INSERT, write notification
      - same trigger   → UPDATE payload, no new notification
      - 2 days OK      → flip status to ``recovered``, write notification
      - skip           → no row mutation
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from datetime import date as Date
from typing import Any, cast

import structlog
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    and_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.evaluation.alerts import (
    LibraryAlertContext,
    OkOutcome,
    Outcome,
    RuleEngine,
    SkipOutcome,
    TriggerOutcome,
    default_rules,
)
from packages.observability import with_span
from packages.orchestration._internal.ulid import new_ulid
from packages.orchestration.adapters.postgres_cost import (
    PostgresCostCapEnforcer,
)
from packages.orchestration.adapters.postgres_eval_snapshots import (
    PostgresEvalSnapshotter,
)
from packages.orchestration.adapters.postgres_notifications import (
    PostgresNotificationStore,
)
from packages.orchestration.cost import CostCheckResult
from packages.orchestration.errors import OrchestrationError
from packages.orchestration.eval_models import (
    AlertRule,
    AlertSeverity,
    AlertStatus,
    EvalAlert,
)
from packages.orchestration.notifications import NotificationType

logger = structlog.get_logger(__name__)

# How many days of snapshot history we feed the rule engine.
_RULE_WINDOW_DAYS: int = 30
# ADR-0021 §4 — number of consecutive OK days needed to flip an alert
# from active → recovered.
_RECOVERY_CONSECUTIVE_DAYS_REQUIRED: int = 2

_metadata = MetaData()

alerts_table = Table(
    "alerts",
    _metadata,
    Column("id", Text, primary_key=True),
    Column("library_id", Text, nullable=False),
    Column("rule", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("triggered_at", DateTime(timezone=True), nullable=False),
    Column("recovered_at", DateTime(timezone=True), nullable=True),
    Column(
        "recovery_consecutive_days",
        Integer,
        nullable=False,
        default=0,
    ),
    Column("payload", JSON, nullable=False),
    Column("notification_id", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
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
        return cast(dict[str, object], decoded) if isinstance(decoded, dict) else {}
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    return {}


def _row_to_alert(row: Mapping[str, Any]) -> EvalAlert:
    return EvalAlert(
        id=row["id"],
        library_id=row["library_id"],
        rule=AlertRule(row["rule"]),
        severity=cast(AlertSeverity, row["severity"]),
        status=cast(AlertStatus, row["status"]),
        triggered_at=_ensure_aware(row["triggered_at"]) or datetime.now(UTC),
        recovered_at=_ensure_aware(row["recovered_at"]),
        recovery_consecutive_days=int(row["recovery_consecutive_days"] or 0),
        payload=_decode_payload(row["payload"]),
        notification_id=row["notification_id"],
    )


class PostgresAlertEngine:
    """Stateful alert evaluator backed by the ``alerts`` table.

    Composes the existing pure rule engine + the Postgres adapters for
    snapshots, cost, and notifications. Each ``evaluate(library_id)`` call
    is a single transaction-per-rule unit; rule failures are logged but do
    not abort the rest of the pass.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        snapshots: PostgresEvalSnapshotter,
        cost_enforcer: PostgresCostCapEnforcer,
        notifier: PostgresNotificationStore,
        library_lookup: LibraryCreatedAtLookup,
        rules: Sequence[RuleEngine] | None = None,
    ) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )
        self._snapshots = snapshots
        self._cost = cost_enforcer
        self._notifier = notifier
        self._library_lookup = library_lookup
        self._rules: tuple[RuleEngine, ...] = tuple(rules) if rules is not None else default_rules()

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    async def evaluate(self, library_id: str) -> tuple[EvalAlert, ...]:
        """Run every rule once for ``library_id`` and return current actives."""
        async with with_span("orchestration.alerts.evaluate", library_id=library_id):
            ctx = await self._build_context(library_id)
            if ctx is None:
                await logger.awarning(
                    "alerts_evaluate_skipped_no_library",
                    library_id=library_id,
                )
                return ()
            for rule in self._rules:
                try:
                    outcome = rule.evaluate(ctx)
                    await self._reconcile(rule, outcome, ctx)
                except Exception as exc:
                    await logger.aerror(
                        "alert_rule_failed",
                        library_id=library_id,
                        rule=rule.rule.value,
                        error=repr(exc),
                    )
            return await self.list_active(library_id)

    async def list_active(self, library_id: str) -> tuple[EvalAlert, ...]:
        async with with_span("orchestration.alerts.list_active", library_id=library_id):
            stmt = (
                select(alerts_table)
                .where(
                    and_(
                        alerts_table.c.library_id == library_id,
                        alerts_table.c.status == "active",
                    )
                )
                .order_by(alerts_table.c.triggered_at.desc())
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            return tuple(_row_to_alert(cast(Mapping[str, Any], r)) for r in rows)

    async def list_recent(
        self,
        library_id: str,
        *,
        days: int = 30,
        limit: int = 50,
    ) -> tuple[EvalAlert, ...]:
        async with with_span("orchestration.alerts.list_recent", library_id=library_id):
            since = datetime.now(UTC) - timedelta(days=max(days, 1))
            stmt = (
                select(alerts_table)
                .where(
                    and_(
                        alerts_table.c.library_id == library_id,
                        alerts_table.c.triggered_at >= since,
                    )
                )
                .order_by(alerts_table.c.triggered_at.desc())
                .limit(limit)
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            return tuple(_row_to_alert(cast(Mapping[str, Any], r)) for r in rows)

    async def purge_library(self, library_id: str) -> None:
        async with with_span("orchestration.alerts.purge_library", library_id=library_id):
            stmt = alerts_table.delete().where(alerts_table.c.library_id == library_id)
            try:
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                raise OrchestrationError(f"alerts purge failed: {library_id}") from exc
            await logger.ainfo("alerts_purged", library_id=library_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _build_context(self, library_id: str) -> LibraryAlertContext | None:
        created_at = await self._library_lookup.get_created_at(library_id)
        if created_at is None:
            return None
        snapshots = await self._snapshots.list_for_alert_window(library_id, days=_RULE_WINDOW_DAYS)
        cost_today: CostCheckResult | None
        try:
            cost_today = await self._cost.check(library_id)
        except Exception as exc:
            await logger.awarning(
                "alerts_cost_check_failed",
                library_id=library_id,
                error=repr(exc),
            )
            cost_today = None
        today: Date = datetime.now(UTC).date()
        return LibraryAlertContext(
            library_id=library_id,
            library_created_at=created_at,
            today=today,
            snapshots=snapshots,
            cost_today=cost_today,
        )

    async def _reconcile(
        self,
        rule: RuleEngine,
        outcome: Outcome,
        ctx: LibraryAlertContext,
    ) -> None:
        active = await self._find_active(ctx.library_id, rule.rule)
        if isinstance(outcome, TriggerOutcome):
            await self._on_trigger(active, outcome, ctx)
            return
        if isinstance(outcome, OkOutcome):
            if active is not None:
                await self._on_ok(rule, active, ctx)
            return
        # Remaining branch is SkipOutcome — exhaustive over the Outcome ADT.
        skip: SkipOutcome = outcome
        await logger.adebug(
            "alert_rule_skipped",
            library_id=ctx.library_id,
            rule=rule.rule.value,
            reason=skip.reason,
        )

    async def _on_trigger(
        self,
        active: EvalAlert | None,
        outcome: TriggerOutcome,
        ctx: LibraryAlertContext,
    ) -> None:
        now = datetime.now(UTC)
        if active is not None:
            # Refresh payload only — `UNIQUE WHERE status='active'` keeps
            # the original row authoritative; no new notification.
            await self._update_payload(
                alert_id=active.id,
                payload=outcome.payload,
                updated_at=now,
            )
            await logger.ainfo(
                "alert_refreshed",
                library_id=ctx.library_id,
                rule=outcome.rule.value,
            )
            return
        notification = await self._notifier.emit(
            library_id=ctx.library_id,
            notification_type=NotificationType.ALERT_TRIGGERED,
            severity=outcome.severity,
            title=_alert_title(outcome.rule, outcome.payload),
            payload={
                "rule": outcome.rule.value,
                "library_id": ctx.library_id,
                **outcome.payload,
            },
            dedup_key=f"alert-trigger:{ctx.library_id}:{outcome.rule.value}:"
            f"{ctx.today.isoformat()}",
        )
        alert_id = new_ulid()
        await self._insert_alert(
            alert_id=alert_id,
            library_id=ctx.library_id,
            rule=outcome.rule,
            severity=outcome.severity,
            triggered_at=now,
            payload=outcome.payload,
            notification_id=notification.id,
        )
        await logger.ainfo(
            "alert_triggered",
            library_id=ctx.library_id,
            rule=outcome.rule.value,
            severity=outcome.severity,
            notification_id=notification.id,
        )

    async def _on_ok(
        self,
        rule: RuleEngine,
        active: EvalAlert,
        ctx: LibraryAlertContext,
    ) -> None:
        if not rule.is_recovered_today(active, ctx):
            if active.recovery_consecutive_days != 0:
                await self._update_recovery_counter(active.id, 0)
            return
        new_count = active.recovery_consecutive_days + 1
        if new_count < _RECOVERY_CONSECUTIVE_DAYS_REQUIRED:
            await self._update_recovery_counter(active.id, new_count)
            return
        # 2 consecutive days OK → flip to recovered.
        now = datetime.now(UTC)
        await self._mark_recovered(active.id, now)
        try:
            await self._notifier.emit(
                library_id=ctx.library_id,
                notification_type=NotificationType.ALERT_RECOVERED,
                severity="info",
                title=f"Alert recovered: {active.rule.value}",
                payload={
                    "rule": active.rule.value,
                    "library_id": ctx.library_id,
                    "alert_id": active.id,
                },
                dedup_key=f"alert-recovered:{ctx.library_id}:"
                f"{active.rule.value}:{ctx.today.isoformat()}",
            )
        except Exception as exc:
            await logger.awarning(
                "alert_recovered_notification_failed",
                library_id=ctx.library_id,
                rule=active.rule.value,
                error=repr(exc),
            )
        await logger.ainfo(
            "alert_recovered",
            library_id=ctx.library_id,
            rule=active.rule.value,
            alert_id=active.id,
        )

    async def _find_active(self, library_id: str, rule: AlertRule) -> EvalAlert | None:
        stmt = (
            select(alerts_table)
            .where(
                and_(
                    alerts_table.c.library_id == library_id,
                    alerts_table.c.rule == rule.value,
                    alerts_table.c.status == "active",
                )
            )
            .limit(1)
        )
        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            row = result.mappings().first()
        if row is None:
            return None
        return _row_to_alert(cast(Mapping[str, Any], row))

    async def _insert_alert(
        self,
        *,
        alert_id: str,
        library_id: str,
        rule: AlertRule,
        severity: AlertSeverity,
        triggered_at: datetime,
        payload: dict[str, object],
        notification_id: str | None,
    ) -> None:
        stmt = pg_insert(alerts_table).values(
            id=alert_id,
            library_id=library_id,
            rule=rule.value,
            severity=severity,
            status="active",
            triggered_at=triggered_at,
            recovered_at=None,
            recovery_consecutive_days=0,
            payload=dict(payload),
            notification_id=notification_id,
            created_at=triggered_at,
            updated_at=triggered_at,
        )
        # Race-safe against the partial unique index — fall back to
        # payload refresh if another evaluator inserted concurrently.
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["library_id", "rule"],
            index_where=alerts_table.c.status == "active",
        )
        try:
            async with self._sessionmaker() as session, session.begin():
                await session.execute(stmt)
        except SQLAlchemyError as exc:
            raise OrchestrationError("alert insert failed") from exc

    async def _update_payload(
        self,
        *,
        alert_id: str,
        payload: dict[str, object],
        updated_at: datetime,
    ) -> None:
        stmt = (
            update(alerts_table)
            .where(alerts_table.c.id == alert_id)
            .values(payload=dict(payload), updated_at=updated_at)
        )
        try:
            async with self._sessionmaker() as session, session.begin():
                await session.execute(stmt)
        except SQLAlchemyError as exc:
            raise OrchestrationError("alert update failed") from exc

    async def _update_recovery_counter(self, alert_id: str, count: int) -> None:
        stmt = (
            update(alerts_table)
            .where(alerts_table.c.id == alert_id)
            .values(
                recovery_consecutive_days=count,
                updated_at=datetime.now(UTC),
            )
        )
        try:
            async with self._sessionmaker() as session, session.begin():
                await session.execute(stmt)
        except SQLAlchemyError as exc:
            raise OrchestrationError("alert recovery update failed") from exc

    async def _mark_recovered(self, alert_id: str, recovered_at: datetime) -> None:
        stmt = (
            update(alerts_table)
            .where(alerts_table.c.id == alert_id)
            .values(
                status="recovered",
                recovered_at=recovered_at,
                updated_at=recovered_at,
            )
        )
        try:
            async with self._sessionmaker() as session, session.begin():
                await session.execute(stmt)
        except SQLAlchemyError as exc:
            raise OrchestrationError("alert mark_recovered failed") from exc


def _alert_title(rule: AlertRule, payload: Mapping[str, object]) -> str:
    """Human-readable headline for the notification row."""
    metric = payload.get("metric")
    delta = payload.get("delta_pp")
    if isinstance(delta, (int, float)) and metric:
        return f"{metric} dropped {abs(float(delta)):.1f}pp ({rule.value})"
    return f"Alert triggered: {rule.value}"


# ----------------------------------------------------------------------
# Library lookup helper (kept intentionally minimal — adapter does not
# need full Library metadata, only created_at for cold-start discipline).
# ----------------------------------------------------------------------


class LibraryCreatedAtLookup:
    """Reads ``libraries.created_at`` from Postgres for the cold-start gate."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def get_created_at(self, library_id: str) -> datetime | None:
        from sqlalchemy import column, table  # noqa: PLC0415 — local helper

        libraries = table("libraries", column("library_id"), column("created_at"))
        stmt = select(libraries.c.created_at).where(libraries.c.library_id == library_id)
        async with self._sessionmaker() as session:
            result = await session.execute(stmt)
            row = result.first()
        if row is None:
            return None
        value = row[0]
        if isinstance(value, datetime):
            return _ensure_aware(value)
        return None


__all__ = [
    "LibraryCreatedAtLookup",
    "PostgresAlertEngine",
    "alerts_table",
]
