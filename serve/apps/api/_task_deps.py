"""Lazy DI for the M7 task subsystem (ADR-0009 + ADR-0010).

Kept private to `apps/api/` (underscore prefix per CODING_STANDARDS §10.1).
The factories are async-singleton: the first request that needs the queue
or event bus builds the engine + Redis client; subsequent requests reuse.

The whole module is import-lazy on `redis` and `sqlalchemy` so app startup
in environments without a queue (e.g. unit tests) is not penalised.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

from fastapi import Depends

from apps._shared.factories import AppContainer
from apps.api.deps import get_container
from packages.orchestration.adapters.arq_queue import ArqTaskQueue
from packages.orchestration.adapters.postgres_task_store import PostgresTaskStore
from packages.orchestration.adapters.redis_event_bus import RedisTaskEventBus
from packages.orchestration.errors import QueueFullError
from packages.orchestration.queue import TaskEventBus, TaskQueue


@dataclass
class _TaskBundle:
    queue: TaskQueue
    events: TaskEventBus
    store: PostgresTaskStore
    engine: Any
    redis: Any


_bundle_lock = asyncio.Lock()
_bundle_cache: _TaskBundle | None = None


async def _build_bundle(container: AppContainer) -> _TaskBundle:
    """Build the queue + bus, sharing the AppContainer's settings."""
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = container.settings
    engine = create_async_engine(settings.postgres_url, future=True)
    store = PostgresTaskStore(engine)
    redis_client = _connect_redis(settings.redis_url)
    bus = RedisTaskEventBus(redis_client)
    arq_pool = await _create_arq_pool(settings.redis_url)
    queue = ArqTaskQueue(arq=arq_pool, store=store, events=bus)
    return _TaskBundle(
        queue=queue,
        events=bus,
        store=store,
        engine=engine,
        redis=redis_client,
    )


def _connect_redis(url: str) -> Any:
    from redis.asyncio import Redis

    return Redis.from_url(url, decode_responses=True)


async def _create_arq_pool(url: str) -> Any:
    from arq.connections import RedisSettings, create_pool

    return await create_pool(RedisSettings.from_dsn(url))


async def get_task_bundle(
    container: AppContainer = Depends(get_container),
) -> _TaskBundle:
    """Async singleton accessor for the task bundle."""
    global _bundle_cache  # noqa: PLW0603 — process-wide singleton by design
    if _bundle_cache is None:
        async with _bundle_lock:
            if _bundle_cache is None:
                try:
                    _bundle_cache = await _build_bundle(container)
                except QueueFullError:
                    raise
                except Exception as exc:
                    msg = f"Task queue unavailable: {exc}"
                    raise QueueFullError(msg) from exc
    return _bundle_cache


async def get_task_queue(
    bundle: _TaskBundle = Depends(get_task_bundle),
) -> TaskQueue:
    return bundle.queue


async def get_task_event_bus(
    bundle: _TaskBundle = Depends(get_task_bundle),
) -> TaskEventBus:
    return bundle.events


async def reset_task_bundle() -> None:
    """Test hook — drops the cached bundle so the next request rebuilds."""
    global _bundle_cache  # noqa: PLW0603
    _bundle_cache = None


def set_task_bundle_for_testing(
    queue: TaskQueue,
    events: TaskEventBus,
    *,
    store: PostgresTaskStore | None = None,
) -> None:
    """Test hook — inject pre-built fakes into the cache."""
    global _bundle_cache  # noqa: PLW0603
    _bundle_cache = _TaskBundle(
        queue=queue,
        events=events,
        store=store if store is not None else cast(Any, None),
        engine=None,
        redis=None,
    )
