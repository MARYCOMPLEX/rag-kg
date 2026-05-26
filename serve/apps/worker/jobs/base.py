"""Shared helpers for Arq jobs (ADR_REVIEW §10.3).

Every concrete job (ingest, KG extract, community rebuild, review, ...) is
required by ADR-0009 to:

1. Bind `library_id` to a structured logger / OTEL span.
2. Update the `tasks` row at every status transition.
3. Emit a matching `TaskEvent` on the event bus.
4. On terminal status, write a `Notification` row.

`JobContext` is the bag of dependencies; `job_lifecycle` is the async
context manager that enforces the protocol. A sister-agent's job body
runs **inside** `job_lifecycle` and only does business logic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from structlog.stdlib import BoundLogger

from packages.orchestration.activity import (
    ActivityEvent,
    ActivityLogger,
    ActivityType,
)
from packages.orchestration.adapters.postgres_task_store import PostgresTaskStore
from packages.orchestration.errors import TaskCancelledError
from packages.orchestration.notifications import (
    Notification,
    NotificationStore,
    NotificationType,
    Severity,
)
from packages.orchestration.queue import (
    TaskEvent,
    TaskEventBus,
    TaskEventType,
    TaskId,
)


@dataclass(frozen=True)
class JobContext:
    """Per-job dependencies handed off via Arq `ctx`.

    `library_id` and `task_id` are bound on the logger so every log line
    inside the job is tagged consistently — no ad-hoc kwargs needed.
    """

    library_id: str
    task_id: TaskId
    task_type: str
    store: PostgresTaskStore
    events: TaskEventBus
    notify: NotificationStore | None
    activity: ActivityLogger | None
    log: BoundLogger

    @classmethod
    def from_arq(
        cls,
        ctx: dict[str, Any],
        *,
        library_id: str,
        task_id: TaskId,
        task_type: str,
    ) -> JobContext:
        """Pull pre-injected adapters out of the Arq ctx dict.

        The Worker's `on_startup` hook (see `apps/worker/main.py`) fills
        this dict; jobs only consume.
        """
        store = ctx["task_store"]
        events = ctx["task_events"]
        notify = ctx.get("notification_store")
        activity = ctx.get("activity_logger")
        bound = structlog.get_logger("worker.job").bind(
            library_id=library_id,
            task_id=task_id,
            task_type=task_type,
        )
        return cls(
            library_id=library_id,
            task_id=task_id,
            task_type=task_type,
            store=cast(PostgresTaskStore, store),
            events=cast(TaskEventBus, events),
            notify=cast(NotificationStore | None, notify),
            activity=cast(ActivityLogger | None, activity),
            log=cast(BoundLogger, bound),
        )


def _now() -> datetime:
    return datetime.now(UTC)


@asynccontextmanager  # pyright: ignore[reportDeprecated]  # py3.13 stubs marked async, but it's safe
async def job_lifecycle(ctx: JobContext) -> AsyncIterator[None]:
    """Orchestrate task_started → run → terminal handoff.

    Behaviour:
    - On enter: write ``status=running`` + emit ``task_started`` event.
    - On exit (no error): caller is expected to have called
      `mark_completed`/`mark_failed`/`mark_cancelled` already; if not,
      we mark the task completed with whatever progress is set.
    - On exception: mark failed + emit ``task_failed`` + write a
      `Notification` row (severity=danger). `TaskCancelledError` is
      converted to ``status=cancelled`` instead of failure.

    The lifecycle is idempotent — re-running a job whose row is already in
    a terminal state (because of a worker retry) short-circuits.
    """
    existing = await ctx.store.get(ctx.library_id, ctx.task_id)
    if existing is not None and existing.status in {"completed", "failed", "cancelled"}:
        await ctx.log.ainfo("job_skipped_already_terminal", status=existing.status)
        yield
        return

    started_at = _now()
    await ctx.store.update_status(
        ctx.library_id,
        ctx.task_id,
        status="running",
        started_at=started_at,
        progress=0.0,
    )
    await ctx.events.emit(
        TaskEvent(
            library_id=ctx.library_id,
            task_id=ctx.task_id,
            seq=0,
            timestamp=started_at,
            type=TaskEventType.TASK_STARTED,
            payload={
                "started_at": started_at.isoformat(),
                "estimated_duration_s": 0,
            },
        )
    )
    await ctx.log.ainfo("job_started")

    try:
        yield
    except TaskCancelledError as exc:
        await _mark_terminal(
            ctx,
            event_type=TaskEventType.TASK_CANCELLED,
            status="cancelled",
            error=None,
            payload={"reason": exc.reason, "by": "worker"},
        )
        await ctx.log.ainfo("job_cancelled", reason=exc.reason)
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        await _mark_terminal(
            ctx,
            event_type=TaskEventType.TASK_FAILED,
            status="failed",
            error=message,
            payload={
                "error_code": exc.__class__.__name__,
                "message": message,
                "request_id": ctx.task_id,
            },
        )
        if ctx.notify is not None:
            await _record_notification(
                ctx,
                ntype=NotificationType.TASK_FAILED,
                severity="danger",
                title=f"Task failed: {ctx.task_type}",
                body=message[:500],
            )
        await ctx.log.aerror("job_failed", error=message)
        raise
    else:
        # Success path — caller may have already pre-marked completed via
        # `mark_completed`. Re-check and only mark if still running.
        snapshot = await ctx.store.get(ctx.library_id, ctx.task_id)
        if snapshot is not None and snapshot.status == "running":
            await _mark_terminal(
                ctx,
                event_type=TaskEventType.TASK_COMPLETED,
                status="completed",
                error=None,
                payload={
                    "result_pointer": snapshot.result_pointer or "",
                    "duration_s": _duration_s(snapshot.started_at),
                },
                result_pointer=snapshot.result_pointer,
            )
        if ctx.notify is not None:
            await _record_notification(
                ctx,
                ntype=NotificationType.TASK_COMPLETED,
                severity="info",
                title=f"Task completed: {ctx.task_type}",
                body=None,
            )
        if ctx.activity is not None:
            await _record_activity(ctx)
        await ctx.log.ainfo("job_succeeded")


async def _mark_terminal(
    ctx: JobContext,
    *,
    event_type: TaskEventType,
    status: str,
    error: str | None,
    payload: dict[str, Any],
    result_pointer: str | None = None,
) -> None:
    finished_at = _now()
    await ctx.store.update_status(
        ctx.library_id,
        ctx.task_id,
        status=cast(Any, status),
        finished_at=finished_at,
        error=error,
        result_pointer=result_pointer,
    )
    await ctx.events.emit(
        TaskEvent(
            library_id=ctx.library_id,
            task_id=ctx.task_id,
            seq=0,
            timestamp=finished_at,
            type=event_type,
            payload=payload,
        )
    )


async def _record_notification(
    ctx: JobContext,
    *,
    ntype: NotificationType,
    severity: Severity,
    title: str,
    body: str | None,
) -> None:
    """Best-effort terminal notification; failure here MUST NOT mask the job result."""
    assert ctx.notify is not None  # narrow for pyright
    now = _now()
    notification = Notification(
        id=f"notif:{ctx.task_id}",
        library_id=ctx.library_id,
        type=ntype,
        severity=severity,
        title=title,
        body=body,
        payload={"task_id": ctx.task_id, "task_type": ctx.task_type},
        read=False,
        read_at=None,
        created_at=now,
        expires_at=now,
        dedup_key=f"{ctx.task_id}:{ntype.value}",
    )
    try:
        await ctx.notify.write(notification)
    except Exception as exc:
        await ctx.log.awarning("notification_write_failed", error=str(exc))


async def _record_activity(ctx: JobContext) -> None:
    assert ctx.activity is not None
    activity_type = _ACTIVITY_TYPE_BY_TASK.get(ctx.task_type)
    if activity_type is None:
        return
    event = ActivityEvent(
        id=0,
        library_id=ctx.library_id,
        type=activity_type,
        title=f"{ctx.task_type} completed",
        summary=None,
        payload={"task_id": ctx.task_id},
        actor="worker",
        created_at=_now(),
    )
    try:
        await ctx.activity.record(event)
    except Exception as exc:
        await ctx.log.awarning("activity_record_failed", error=str(exc))


_ACTIVITY_TYPE_BY_TASK: dict[str, ActivityType] = {
    "ingest_document": ActivityType.INGEST_COMPLETED,
    "ingest_batch": ActivityType.INGEST_COMPLETED,
    "extract_kg": ActivityType.KG_EXTRACTED,
    "rebuild_community": ActivityType.COMMUNITY_REBUILT,
    "run_review": ActivityType.REVIEW_COMPLETED,
    "run_reason": ActivityType.REASON_COMPLETED,
    "run_hypothesize": ActivityType.HYPOTHESIZE_COMPLETED,
    "eval_snapshot": ActivityType.EVAL_RUN_COMPLETED,
}


def _duration_s(started_at: datetime | None) -> float:
    if started_at is None:
        return 0.0
    return (_now() - started_at).total_seconds()


__all__ = ["JobContext", "job_lifecycle"]
