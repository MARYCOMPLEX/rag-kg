"""Lazy DI for the M7 cross-cutting orchestration adapters.

Wires up Postgres-backed `NotificationStore`, `ActivityLogger`,
`LibraryConfigStore`, and `CostCapEnforcer` once per process and exposes
FastAPI deps for the new routes (notifications / activity /
library_settings).

Mirrors the structure of `_task_deps.py` — module is import-lazy on
`sqlalchemy` so unit-test environments without Postgres can still import
this file. Real Postgres is required at first request time.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from fastapi import Depends

from apps._shared.factories import AppContainer
from apps.api._activity_reader import ActivityCrossReader
from apps.api._notification_reader import NotificationCrossReader
from apps.api.deps import get_container
from packages.orchestration.adapters.postgres_activity import PostgresActivityLogger
from packages.orchestration.adapters.postgres_cost import PostgresCostCapEnforcer
from packages.orchestration.adapters.postgres_library_config import (
    PostgresLibraryConfigStore,
)
from packages.orchestration.adapters.postgres_notifications import (
    PostgresNotificationStore,
)


@dataclass
class _OrchestrationBundle:
    notifications: PostgresNotificationStore
    activity: PostgresActivityLogger
    config: PostgresLibraryConfigStore
    cost: PostgresCostCapEnforcer
    activity_reader: ActivityCrossReader
    notification_reader: NotificationCrossReader
    engine: Any


_lock = asyncio.Lock()
_cache: _OrchestrationBundle | None = None


def _build_engine(postgres_url: str) -> Any:
    from sqlalchemy.ext.asyncio import create_async_engine

    return create_async_engine(postgres_url, future=True)


async def _build_bundle(container: AppContainer) -> _OrchestrationBundle:
    settings = container.settings
    engine = _build_engine(settings.postgres_url)
    listen_dsn = _maybe_listen_dsn(settings.postgres_url)
    notifications = PostgresNotificationStore(engine, listen_dsn=listen_dsn)
    activity = PostgresActivityLogger(engine)
    config = PostgresLibraryConfigStore(engine, notifier=notifications)
    cost = PostgresCostCapEnforcer(engine, config_store=config, notifier=notifications)
    return _OrchestrationBundle(
        notifications=notifications,
        activity=activity,
        config=config,
        cost=cost,
        activity_reader=ActivityCrossReader(engine),
        notification_reader=NotificationCrossReader(engine),
        engine=engine,
    )


def _maybe_listen_dsn(postgres_url: str) -> str | None:
    """Strip the ``+asyncpg`` driver tag for the asyncpg LISTEN connection.

    SQLAlchemy URLs use ``postgresql+asyncpg://...`` but `asyncpg.connect`
    expects the bare ``postgresql://`` form. Returning None opts out of
    LISTEN/NOTIFY entirely (the store falls back to polling).
    """
    if "+asyncpg" not in postgres_url:
        return None
    return postgres_url.replace("+asyncpg", "")


async def get_orchestration_bundle(
    container: AppContainer = Depends(get_container),
) -> _OrchestrationBundle:
    """Async singleton accessor for the orchestration bundle."""
    global _cache  # noqa: PLW0603 — process-wide singleton by design
    if _cache is None:
        async with _lock:
            if _cache is None:
                _cache = await _build_bundle(container)
    return _cache


async def get_notification_store(
    bundle: _OrchestrationBundle = Depends(get_orchestration_bundle),
) -> PostgresNotificationStore:
    return bundle.notifications


async def get_notification_reader(
    bundle: _OrchestrationBundle = Depends(get_orchestration_bundle),
) -> NotificationCrossReader:
    return bundle.notification_reader


async def get_activity_logger(
    bundle: _OrchestrationBundle = Depends(get_orchestration_bundle),
) -> PostgresActivityLogger:
    return bundle.activity


async def get_activity_reader(
    bundle: _OrchestrationBundle = Depends(get_orchestration_bundle),
) -> ActivityCrossReader:
    return bundle.activity_reader


async def get_library_config_store(
    bundle: _OrchestrationBundle = Depends(get_orchestration_bundle),
) -> PostgresLibraryConfigStore:
    return bundle.config


async def get_cost_enforcer(
    bundle: _OrchestrationBundle = Depends(get_orchestration_bundle),
) -> PostgresCostCapEnforcer:
    return bundle.cost


async def reset_orchestration_bundle() -> None:
    """Test hook — drop the cached bundle so the next request rebuilds."""
    global _cache  # noqa: PLW0603
    _cache = None


def set_orchestration_bundle_for_testing(
    *,
    notifications: PostgresNotificationStore | None = None,
    activity: PostgresActivityLogger | None = None,
    config: PostgresLibraryConfigStore | None = None,
    cost: PostgresCostCapEnforcer | None = None,
    activity_reader: ActivityCrossReader | None = None,
    notification_reader: NotificationCrossReader | None = None,
) -> None:
    """Test hook — inject pre-built fakes into the cache."""
    global _cache  # noqa: PLW0603
    _cache = _OrchestrationBundle(
        notifications=cast(PostgresNotificationStore, notifications),
        activity=cast(PostgresActivityLogger, activity),
        config=cast(PostgresLibraryConfigStore, config),
        cost=cast(PostgresCostCapEnforcer, cost),
        activity_reader=cast(ActivityCrossReader, activity_reader),
        notification_reader=cast(NotificationCrossReader, notification_reader),
        engine=None,
    )
