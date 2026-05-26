"""Periodic library-status checker job (ADR-0013 §4).

Cron: every 5 minutes (``STATUS_CHECK_INTERVAL_SECONDS = 300``). The job
just delegates to ``LibraryStatusChecker.evaluate_all`` — that method
holds the advisory-lock-and-double-check discipline. Anything heavier
than that lives in the orchestration adapter, not here.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

import structlog

from packages.orchestration.adapters.postgres_library_status import (
    PostgresLibraryStatusChecker,
)

logger = structlog.get_logger(__name__)

# Per ADR-0013 — total timeout for one round of full-library evaluation.
_RUN_TIMEOUT_S: float = 60.0


async def library_status_check(ctx: dict[str, Any]) -> dict[str, int]:
    """Run a single status-check pass over every library.

    The Arq worker registers this function and triggers it via
    ``cron_jobs`` declared in ``apps/worker/main.py``. The handler is
    deliberately tiny so the testable logic stays in the adapter.

    Returns:
        ``{"evaluated": <n>, "transitions": <m>}`` for monitoring.
    """
    checker = cast(PostgresLibraryStatusChecker | None, ctx.get("library_status_checker"))
    if checker is None:
        await logger.awarning("library_status_check_skipped_no_checker")
        return {"evaluated": 0, "transitions": 0}

    try:
        async with asyncio.timeout(_RUN_TIMEOUT_S):
            evaluations = await checker.evaluate_all()
    except TimeoutError:
        await logger.aerror("library_status_check_timeout")
        return {"evaluated": 0, "transitions": 0}
    except Exception as exc:
        await logger.aerror("library_status_check_failed", error=repr(exc))
        return {"evaluated": 0, "transitions": 0}

    transitions = sum(1 for e in evaluations if e.previous_status != e.new_status)
    await logger.ainfo(
        "library_status_check_done",
        evaluated=len(evaluations),
        transitions=transitions,
    )
    return {"evaluated": len(evaluations), "transitions": transitions}


__all__ = ["library_status_check"]
