"""Daily eval snapshot + alert evaluator cron jobs (ADR-0016 §5 + ADR-0021 §2).

Two scheduled hooks, both running once per UTC day:

  * ``02:00`` — ``eval_snapshot_job`` writes the previous day's KPI rows
    via ``EvalSnapshotter.write_daily`` for every Library known to
    Postgres.
  * ``02:30`` — ``eval_alert_job`` walks every Library through
    ``AlertEngine.evaluate`` so the rule-state machine catches
    transitions while the snapshot freshly written above is the
    source-of-truth window.

The actual cron registration is done by ``apps/worker/main.py`` via the
``cron_jobs`` ``ClassVar`` on ``WorkerSettings``. Job bodies stay tiny
because all logic lives in the evaluation package + adapters.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from datetime import date as Date
from typing import Any, cast

import structlog

from packages.orchestration.adapters.postgres_alerts import PostgresAlertEngine
from packages.orchestration.adapters.postgres_eval_snapshots import (
    PostgresEvalSnapshotter,
)

logger = structlog.get_logger(__name__)

# ADR-0016 §5: snapshot writer fires at 02:00 UTC.
SNAPSHOT_HOUR_UTC: int = 2
SNAPSHOT_MINUTE_UTC: int = 0
# ADR-0021 §2: alert evaluator runs at 02:30 UTC, after the snapshot.
ALERT_HOUR_UTC: int = 2
ALERT_MINUTE_UTC: int = 30

# Per ADR-0021 §2 — total timeout for one full sweep across all libraries.
_RUN_TIMEOUT_S: float = 300.0


async def eval_snapshot_job(ctx: dict[str, Any]) -> dict[str, int]:
    """Write yesterday's KPI snapshots for every active Library.

    The Arq worker registers this function and triggers it via the cron
    schedule defined in ``apps/worker/main.py``. Returns a small dict so
    monitoring can chart "how many libraries did we score today".
    """
    snapshots = cast(PostgresEvalSnapshotter | None, ctx.get("eval_snapshots"))
    if snapshots is None:
        await logger.awarning("eval_snapshot_job_skipped_no_adapter")
        return {"libraries": 0, "rows": 0}

    library_ids = await _resolve_active_libraries(ctx)
    if not library_ids:
        return {"libraries": 0, "rows": 0}

    yesterday: Date = (datetime.now(UTC) - timedelta(days=1)).date()
    total_rows = 0
    succeeded = 0
    try:
        async with asyncio.timeout(_RUN_TIMEOUT_S):
            for library_id in library_ids:
                try:
                    rows = await snapshots.write_daily(library_id, as_of=yesterday)
                    total_rows += len(rows)
                    succeeded += 1
                except Exception as exc:
                    await logger.aerror(
                        "eval_snapshot_library_failed",
                        library_id=library_id,
                        as_of=yesterday.isoformat(),
                        error=repr(exc),
                    )
    except TimeoutError:
        await logger.aerror(
            "eval_snapshot_job_timeout",
            as_of=yesterday.isoformat(),
            timeout_s=_RUN_TIMEOUT_S,
        )

    await logger.ainfo(
        "eval_snapshot_job_done",
        libraries=succeeded,
        rows=total_rows,
        as_of=yesterday.isoformat(),
    )
    return {"libraries": succeeded, "rows": total_rows}


async def eval_alert_job(ctx: dict[str, Any]) -> dict[str, int]:
    """Run the alert engine on every active Library."""
    engine = cast(PostgresAlertEngine | None, ctx.get("alert_engine"))
    if engine is None:
        await logger.awarning("eval_alert_job_skipped_no_engine")
        return {"libraries": 0, "active": 0}

    library_ids = await _resolve_active_libraries(ctx)
    if not library_ids:
        return {"libraries": 0, "active": 0}

    total_active = 0
    succeeded = 0
    try:
        async with asyncio.timeout(_RUN_TIMEOUT_S):
            for library_id in library_ids:
                try:
                    actives = await engine.evaluate(library_id)
                    total_active += len(actives)
                    succeeded += 1
                except Exception as exc:
                    await logger.aerror(
                        "eval_alert_library_failed",
                        library_id=library_id,
                        error=repr(exc),
                    )
    except TimeoutError:
        await logger.aerror(
            "eval_alert_job_timeout",
            timeout_s=_RUN_TIMEOUT_S,
        )

    await logger.ainfo(
        "eval_alert_job_done",
        libraries=succeeded,
        active=total_active,
    )
    return {"libraries": succeeded, "active": total_active}


async def _resolve_active_libraries(ctx: dict[str, Any]) -> tuple[str, ...]:
    """Resolve the list of Libraries the cron should iterate over.

    Looks up ``ctx["library_repo"]`` (preferred) or falls back to a
    pre-computed ``ctx["library_ids"]`` list so unit tests can inject
    a fixed set without instantiating a repo.
    """
    repo: Any = ctx.get("library_repo")
    if repo is not None and hasattr(repo, "list_all"):
        try:
            libs = await _invoke_list_all(repo)
        except Exception as exc:
            await logger.aerror("eval_cron_library_list_failed", error=repr(exc))
            return ()
        return tuple(_iter_library_ids(libs))
    static = ctx.get("library_ids")
    if isinstance(static, (list, tuple)):
        items = cast(Iterable[object], static)
        return tuple(item for item in items if isinstance(item, str))
    return ()


async def _invoke_list_all(repo: Any) -> Iterable[Any]:
    """Invoke ``repo.list_all()`` (assumed coroutine returning an iterable)."""
    coro: Any = repo.list_all()
    result: Any = await coro
    return cast(Iterable[Any], result)


def _iter_library_ids(libraries: Iterable[Any]) -> Iterable[str]:
    for lib in libraries:
        lib_id = getattr(lib, "library_id", None)
        if isinstance(lib_id, str) and lib_id:
            yield lib_id


# Worker entry point — Arq looks up `run` on each module in
# `apps.worker.main._TASK_MODULES`.
async def run(ctx: dict[str, Any]) -> dict[str, int]:
    """Default Arq entry point — runs the snapshot pass.

    The alert pass is registered separately via ``cron_jobs`` so the two
    schedules (02:00 + 02:30) stay independent.
    """
    return await eval_snapshot_job(ctx)


__all__ = [
    "ALERT_HOUR_UTC",
    "ALERT_MINUTE_UTC",
    "SNAPSHOT_HOUR_UTC",
    "SNAPSHOT_MINUTE_UTC",
    "eval_alert_job",
    "eval_snapshot_job",
    "run",
]
