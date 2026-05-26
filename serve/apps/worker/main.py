"""Arq worker entry point (M7, ADR-0009).

Wires the durable `tasks` store + Redis event bus into the Arq runtime so
every registered job has access via its `ctx` dict (see
`apps/worker/jobs/base.py:JobContext`). The actual job bodies are filled
in by sister-agent patches; this file is a thin registration point so
adding a new task type does not require touching wiring code.
"""

from __future__ import annotations

import importlib
from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings

from packages.core.config import Settings

logger = structlog.get_logger(__name__)


# Ordered list of task types registered with Arq. The job module file name
# matches the task type (`apps/worker/jobs/<task_type>.py`) and exports
# `async def run(ctx, library_id, task_id, input_payload) -> object`.
_TASK_MODULES: tuple[str, ...] = (
    "ingest_document",
    "ingest_batch",
    "extract_kg",
    "rebuild_community",
    "run_review",
    "run_reason",
    "run_hypothesize",
    "library_status_check",
    "eval_snapshot",
    "library_purge",
)


def _load_job_functions() -> list[Any]:
    """Best-effort import every job module present on disk.

    Missing modules are skipped so phased agent rollout never blocks the
    worker — only modules whose import fails for *non-missing* reasons
    bubble the error.
    """
    fns: list[Any] = []
    for name in _TASK_MODULES:
        try:
            mod = importlib.import_module(f"apps.worker.jobs.{name}")
        except ModuleNotFoundError as exc:
            if exc.name == f"apps.worker.jobs.{name}":
                continue
            raise
        fn = getattr(mod, "run", None)
        if fn is None:
            continue
        # Arq looks at `function.__qualname__` for naming. Wrap to give a
        # canonical `run_<task_type>` name that ArqTaskQueue.enqueue references.
        fn.__name__ = f"run_{name}"
        fn.__qualname__ = f"run_{name}"
        fns.append(fn)
    return fns


async def startup(ctx: dict[str, object]) -> None:
    """Initialize shared adapters once per worker process.

    Stores them in `ctx` so individual jobs can `JobContext.from_arq(ctx, ...)`
    without re-creating connections per job invocation.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from packages.orchestration.adapters.postgres_task_store import PostgresTaskStore
    from packages.orchestration.adapters.redis_event_bus import RedisTaskEventBus

    settings = Settings()
    engine = create_async_engine(settings.postgres_url, future=True)
    store = PostgresTaskStore(engine)

    redis_client = _connect_redis(settings.redis_url)
    bus = RedisTaskEventBus(redis_client)

    ctx["postgres_engine"] = engine
    ctx["task_store"] = store
    ctx["task_events"] = bus
    ctx["redis_client"] = redis_client
    await logger.ainfo("worker_started", redis_url=_safe_url(settings.redis_url))


async def shutdown(ctx: dict[str, object]) -> None:
    """Close shared adapters on worker exit."""
    engine = ctx.get("postgres_engine")
    if engine is not None:
        await engine.dispose()  # type: ignore[union-attr]
    redis_client = ctx.get("redis_client")
    if redis_client is not None:
        try:
            await redis_client.aclose()  # type: ignore[union-attr]
        except Exception as exc:
            await logger.awarning("redis_close_failed", error=str(exc))
    await logger.ainfo("worker_stopped")


def _connect_redis(url: str) -> Any:
    """Late-import redis.asyncio so unit tests don't need the lib at import time."""
    from redis.asyncio import Redis

    return Redis.from_url(url, decode_responses=True)


def _safe_url(url: str) -> str:
    """Mask any embedded password before logging the Redis DSN."""
    if "@" not in url:
        return url
    scheme_creds, host = url.rsplit("@", 1)
    if ":" not in scheme_creds:
        return url
    scheme, _ = scheme_creds.rsplit(":", 1)
    return f"{scheme}:***@{host}"


def _build_cron_jobs() -> list[Any]:
    """Register cron jobs whose backing modules are present on disk.

    ADR-0016 §5 / ADR-0021 §2 schedule:
      * 02:00 UTC → ``eval_snapshot_job`` writes yesterday's KPI rows.
      * 02:30 UTC → ``eval_alert_job`` runs the alert engine.

    The legacy 5-minute Library-status check (ADR-0013) is left in place.
    Missing job modules are skipped so phased rollout never breaks the worker.
    """
    from arq.cron import cron

    jobs: list[Any] = []
    try:
        eval_module = importlib.import_module("apps.worker.jobs.eval_snapshot")
    except ModuleNotFoundError:
        eval_module = None
    if eval_module is not None:
        snapshot_fn = getattr(eval_module, "eval_snapshot_job", None)
        alert_fn = getattr(eval_module, "eval_alert_job", None)
        if snapshot_fn is not None:
            jobs.append(
                cron(
                    snapshot_fn,
                    name="eval_snapshot_job",
                    hour={eval_module.SNAPSHOT_HOUR_UTC},
                    minute={eval_module.SNAPSHOT_MINUTE_UTC},
                    run_at_startup=False,
                )
            )
        if alert_fn is not None:
            jobs.append(
                cron(
                    alert_fn,
                    name="eval_alert_job",
                    hour={eval_module.ALERT_HOUR_UTC},
                    minute={eval_module.ALERT_MINUTE_UTC},
                    run_at_startup=False,
                )
            )
    try:
        status_module = importlib.import_module("apps.worker.jobs.library_status_check")
    except ModuleNotFoundError:
        status_module = None
    if status_module is not None:
        status_fn = getattr(status_module, "library_status_check", None)
        if status_fn is not None:
            jobs.append(
                cron(
                    status_fn,
                    name="library_status_check",
                    minute=set(range(0, 60, 5)),
                    run_at_startup=False,
                )
            )
    return jobs


class WorkerSettings:
    """Arq worker configuration (ADR-0009 §2)."""

    functions: ClassVar[list[Any]] = _load_job_functions()
    cron_jobs: ClassVar[list[Any]] = _build_cron_jobs()
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(Settings().redis_url)
    max_jobs = 4
    keep_result = 3600  # 1 h; durable record lives in Postgres
    job_timeout = 1800  # 30 min hard ceiling
