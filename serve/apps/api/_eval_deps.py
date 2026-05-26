"""Lazy DI for the M7 eval subsystem (ADR-0016 + ADR-0021).

Kept private to ``apps/api/`` (underscore prefix per CODING_STANDARDS
§10.1). The factories are async-singleton: the first request that needs
the eval adapters builds the AsyncEngine + adapters; subsequent requests
reuse them.

Imports of ``sqlalchemy`` are lazy so unit tests in environments without
a Postgres URL configured don't pay the cost.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from fastapi import Depends

from apps._shared.factories import AppContainer
from apps.api.deps import get_container
from packages.orchestration.adapters.postgres_alerts import (
    LibraryCreatedAtLookup,
    PostgresAlertEngine,
)
from packages.orchestration.adapters.postgres_cost import (
    PostgresCostCapEnforcer,
)
from packages.orchestration.adapters.postgres_eval_snapshots import (
    PostgresEvalSnapshotter,
)
from packages.orchestration.adapters.postgres_feedback import (
    PostgresFeedbackStore,
)
from packages.orchestration.adapters.postgres_library_config import (
    PostgresLibraryConfigStore,
)
from packages.orchestration.adapters.postgres_notifications import (
    PostgresNotificationStore,
)


@dataclass
class _EvalBundle:
    """Container for the four eval adapters + the shared async engine."""

    engine: Any
    snapshots: PostgresEvalSnapshotter
    feedback: PostgresFeedbackStore
    alerts: PostgresAlertEngine
    notifications: PostgresNotificationStore


_bundle_lock = asyncio.Lock()
_bundle_cache: _EvalBundle | None = None


async def _build_bundle(container: AppContainer) -> _EvalBundle:
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = container.settings
    engine = create_async_engine(settings.postgres_url, future=True)
    notifications = PostgresNotificationStore(engine)
    config_store = PostgresLibraryConfigStore(engine)
    cost_enforcer = PostgresCostCapEnforcer(
        engine,
        config_store=config_store,
        notifier=notifications,
    )
    snapshots = PostgresEvalSnapshotter(engine)
    feedback = PostgresFeedbackStore(engine)
    library_lookup = LibraryCreatedAtLookup(engine)
    alerts = PostgresAlertEngine(
        engine,
        snapshots=snapshots,
        cost_enforcer=cost_enforcer,
        notifier=notifications,
        library_lookup=library_lookup,
    )
    return _EvalBundle(
        engine=engine,
        snapshots=snapshots,
        feedback=feedback,
        alerts=alerts,
        notifications=notifications,
    )


async def get_eval_bundle(
    container: AppContainer = Depends(get_container),
) -> _EvalBundle:
    """Async singleton accessor for the eval bundle."""
    global _bundle_cache  # noqa: PLW0603 — process-wide singleton by design
    if _bundle_cache is None:
        async with _bundle_lock:
            if _bundle_cache is None:
                _bundle_cache = await _build_bundle(container)
    return _bundle_cache


async def get_eval_snapshotter(
    bundle: _EvalBundle = Depends(get_eval_bundle),
) -> PostgresEvalSnapshotter:
    return bundle.snapshots


async def get_feedback_store(
    bundle: _EvalBundle = Depends(get_eval_bundle),
) -> PostgresFeedbackStore:
    return bundle.feedback


async def get_alert_engine(
    bundle: _EvalBundle = Depends(get_eval_bundle),
) -> PostgresAlertEngine:
    return bundle.alerts


async def reset_eval_bundle() -> None:
    """Test hook — drops the cached bundle so the next request rebuilds."""
    global _bundle_cache  # noqa: PLW0603
    _bundle_cache = None


def set_eval_bundle_for_testing(
    *,
    snapshots: PostgresEvalSnapshotter | None = None,
    feedback: PostgresFeedbackStore | None = None,
    alerts: PostgresAlertEngine | None = None,
    notifications: PostgresNotificationStore | None = None,
) -> None:
    """Test hook — inject pre-built fakes into the cache."""
    global _bundle_cache  # noqa: PLW0603
    _bundle_cache = _EvalBundle(
        engine=None,
        snapshots=cast(PostgresEvalSnapshotter, snapshots),
        feedback=cast(PostgresFeedbackStore, feedback),
        alerts=cast(PostgresAlertEngine, alerts),
        notifications=cast(PostgresNotificationStore, notifications),
    )


__all__ = [
    "get_alert_engine",
    "get_eval_bundle",
    "get_eval_snapshotter",
    "get_feedback_store",
    "reset_eval_bundle",
    "set_eval_bundle_for_testing",
]
