"""Postgres-backed per-library configuration overrides (ADR-0012).

Single table ``library_config`` with a JSONB ``overrides`` column +
``updated_at`` / ``updated_by`` audit. Reads degrade to global defaults
when Postgres is unreachable — but **only on read** (ADR-0012 §8). Writes
must fail loudly so the caller can surface a 5xx.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

import structlog
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.observability import with_span
from packages.orchestration.adapters.postgres_notifications import (
    PostgresNotificationStore,
)
from packages.orchestration.errors import LibraryConfigStoreError
from packages.orchestration.library_config import (
    EmbedderSpec,
    LibraryConfig,
    LibraryConfigPatch,
    LLMRouterSpec,
    RerankerSpec,
)
from packages.orchestration.notifications import (
    NotificationType,
)
from packages.retrieval.protocols import RetrievalBudget

logger = structlog.get_logger(__name__)

_metadata = MetaData()

library_config_table = Table(
    "library_config",
    _metadata,
    Column("library_id", Text, primary_key=True),
    Column("overrides", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", Text, nullable=False),
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _decode_overrides(raw: object) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    if isinstance(raw, dict):
        return cast(dict[str, Any], raw)
    return {}


def _row_to_config(library_id: str, row: Mapping[str, Any]) -> LibraryConfig:
    overrides = _decode_overrides(row["overrides"])
    return _build_config(
        library_id=library_id,
        overrides=overrides,
        updated_at=_ensure_aware(row["updated_at"]) or datetime.now(UTC),
        updated_by=row["updated_by"],
    )


def _build_config(
    *,
    library_id: str,
    overrides: Mapping[str, Any],
    updated_at: datetime,
    updated_by: str,
) -> LibraryConfig:
    """Re-hydrate the typed Pydantic model from a JSONB blob."""
    llm_router = (
        LLMRouterSpec.model_validate(overrides["llm_router_override"])
        if isinstance(overrides.get("llm_router_override"), Mapping)
        else None
    )
    embedder = (
        EmbedderSpec.model_validate(overrides["embedder_override"])
        if isinstance(overrides.get("embedder_override"), Mapping)
        else None
    )
    reranker = (
        RerankerSpec.model_validate(overrides["reranker_override"])
        if isinstance(overrides.get("reranker_override"), Mapping)
        else None
    )
    budget = (
        RetrievalBudget.model_validate(overrides["retrieval_budget_override"])
        if isinstance(overrides.get("retrieval_budget_override"), Mapping)
        else None
    )
    cap_raw = overrides.get("daily_cost_cap_usd")
    cap = Decimal(str(cap_raw)) if cap_raw is not None else None
    warn_raw = overrides.get("cost_cap_warn_pct")
    warn_pct = float(warn_raw) if isinstance(warn_raw, (int, float)) else 0.8
    schema_path = overrides.get("schema_yaml_path")
    timezone = overrides.get("timezone")
    return LibraryConfig(
        library_id=library_id,
        llm_router_override=llm_router,
        embedder_override=embedder,
        reranker_override=reranker,
        retrieval_budget_override=budget,
        daily_cost_cap_usd=cap,
        cost_cap_warn_pct=warn_pct,
        schema_yaml_path=schema_path if isinstance(schema_path, str) else None,
        timezone=timezone if isinstance(timezone, str) else "UTC",
        updated_at=updated_at,
        updated_by=updated_by,
    )


def _config_to_overrides(config: LibraryConfig) -> dict[str, Any]:
    blob: dict[str, Any] = {
        "cost_cap_warn_pct": config.cost_cap_warn_pct,
        "timezone": config.timezone,
    }
    if config.llm_router_override is not None:
        blob["llm_router_override"] = config.llm_router_override.model_dump(mode="json")
    if config.embedder_override is not None:
        blob["embedder_override"] = config.embedder_override.model_dump(mode="json")
    if config.reranker_override is not None:
        blob["reranker_override"] = config.reranker_override.model_dump(mode="json")
    if config.retrieval_budget_override is not None:
        blob["retrieval_budget_override"] = config.retrieval_budget_override.model_dump(mode="json")
    if config.daily_cost_cap_usd is not None:
        blob["daily_cost_cap_usd"] = str(config.daily_cost_cap_usd)
    if config.schema_yaml_path is not None:
        blob["schema_yaml_path"] = config.schema_yaml_path
    return blob


def _apply_patch(current: LibraryConfig, patch: LibraryConfigPatch) -> LibraryConfig:
    """Merge ``patch`` into ``current`` and return a fresh config.

    A field set explicitly to ``None`` in the patch ``model_fields_set`` is
    treated as "clear override"; an absent field is "leave unchanged".
    """
    set_fields = patch.model_fields_set
    updates: dict[str, Any] = {}
    if "llm_router_override" in set_fields:
        updates["llm_router_override"] = patch.llm_router_override
    if "embedder_override" in set_fields:
        updates["embedder_override"] = patch.embedder_override
    if "reranker_override" in set_fields:
        updates["reranker_override"] = patch.reranker_override
    if "retrieval_budget_override" in set_fields:
        updates["retrieval_budget_override"] = patch.retrieval_budget_override
    if "daily_cost_cap_usd" in set_fields:
        updates["daily_cost_cap_usd"] = patch.daily_cost_cap_usd
    if "cost_cap_warn_pct" in set_fields and patch.cost_cap_warn_pct is not None:
        updates["cost_cap_warn_pct"] = patch.cost_cap_warn_pct
    if "schema_yaml_path" in set_fields:
        updates["schema_yaml_path"] = patch.schema_yaml_path
    if "timezone" in set_fields and patch.timezone is not None:
        updates["timezone"] = patch.timezone
    return current.model_copy(update=updates)


def _empty_config(library_id: str, *, now: datetime) -> LibraryConfig:
    return LibraryConfig(library_id=library_id, updated_at=now)


class PostgresLibraryConfigStore:
    """Adapter for ``library_config`` table (ADR-0012)."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        notifier: PostgresNotificationStore | None = None,
    ) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )
        self._notifier = notifier

    async def get(self, library_id: str) -> LibraryConfig:
        """Return the effective per-library config row.

        On Postgres outage, falls back to a fully-empty config (i.e. all
        overrides ``None``), emitting a danger-level alert notification.
        Per ADR-0012 §8 this is intentionally biased toward availability.
        """
        async with with_span(
            "orchestration.library_config.get",
            library_id=library_id,
        ):
            try:
                stmt = select(library_config_table).where(
                    library_config_table.c.library_id == library_id
                )
                async with self._sessionmaker() as session:
                    result = await session.execute(stmt)
                    row = result.mappings().first()
            except (OperationalError, DBAPIError, ConnectionError, TimeoutError) as exc:
                await logger.aerror(
                    "library_config_unreachable",
                    library_id=library_id,
                    error=repr(exc),
                )
                await self._emit_unreachable_warning(library_id)
                return _empty_config(library_id, now=datetime.now(UTC))
            if row is None:
                return _empty_config(library_id, now=datetime.now(UTC))
            return _row_to_config(library_id, dict(row))

    async def update(
        self,
        library_id: str,
        patch: LibraryConfigPatch,
        *,
        updated_by: str,
    ) -> LibraryConfig:
        """Atomic upsert. Fails loudly if Postgres is unreachable."""
        async with with_span(
            "orchestration.library_config.update",
            library_id=library_id,
        ):
            try:
                current = await self.get(library_id)
                merged = _apply_patch(current, patch)
                now = datetime.now(UTC)
                merged = merged.model_copy(update={"updated_at": now, "updated_by": updated_by})
                blob = _config_to_overrides(merged)
                stmt = pg_insert(library_config_table).values(
                    library_id=library_id,
                    overrides=blob,
                    updated_at=now,
                    updated_by=updated_by,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["library_id"],
                    set_={
                        "overrides": blob,
                        "updated_at": now,
                        "updated_by": updated_by,
                    },
                )
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                await logger.aerror(
                    "library_config_update_failed",
                    library_id=library_id,
                    error=repr(exc),
                )
                raise LibraryConfigStoreError("library_config update failed") from exc

            await logger.ainfo(
                "library_config_updated",
                library_id=library_id,
                updated_by=updated_by,
                changed_fields=sorted(patch.model_fields_set),
            )
            return merged

    async def init_library(self, library_id: str) -> None:
        """Create an empty config row for a fresh Library."""
        async with with_span(
            "orchestration.library_config.init_library",
            library_id=library_id,
        ):
            now = datetime.now(UTC)
            stmt = pg_insert(library_config_table).values(
                library_id=library_id,
                overrides={"cost_cap_warn_pct": 0.8, "timezone": "UTC"},
                updated_at=now,
                updated_by="system",
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["library_id"])
            try:
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                raise LibraryConfigStoreError(
                    f"library_config init_library failed: {library_id}"
                ) from exc

    async def purge_library(self, library_id: str) -> None:
        """Delete the row when its Library is purged.

        Postgres FK ``ON DELETE CASCADE`` handles this automatically when
        the parent ``libraries`` row is dropped, but the purge saga
        (ADR-0022) calls us explicitly when running in step-by-step mode.
        """
        async with with_span(
            "orchestration.library_config.purge_library",
            library_id=library_id,
        ):
            try:
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(
                        library_config_table.delete().where(
                            library_config_table.c.library_id == library_id
                        )
                    )
            except SQLAlchemyError as exc:
                raise LibraryConfigStoreError(f"library_config purge failed: {library_id}") from exc

    async def _emit_unreachable_warning(self, library_id: str) -> None:
        if self._notifier is None:
            return
        try:
            await self._notifier.emit(
                library_id=library_id,
                notification_type=NotificationType.ALERT_TRIGGERED,
                severity="warning",
                title="LibraryConfigStore unreachable; using global defaults",
                body=("Per-library config could not be loaded; falling back to global defaults."),
                payload={"library_id": library_id},
                dedup_key=f"library_config_unreachable:{library_id}",
            )
        except Exception as exc:
            await logger.aerror(
                "library_config_unreachable_notify_failed",
                library_id=library_id,
                error=repr(exc),
            )
