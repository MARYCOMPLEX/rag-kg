"""Stage event helpers shared by every worker job (ADR-0010 §2).

Each long-running task emits ``stage_started`` / ``stage_progress`` /
``stage_completed`` events on the per-task event bus. The shape of those
events is identical across ingest / extract / community / review / reason
/ hypothesize jobs — only the stage name varies.

`make_stage_emitter` returns a small async callable that closes over a
`JobContext`; jobs pass it into the orchestration task layer (which never
imports Redis directly per CODING_STANDARDS §3.1).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from apps.worker.jobs.base import JobContext
from packages.orchestration.queue import TaskEvent, TaskEventType

# (stage_name, event_type, payload) -> awaitable. ``event_type`` is the
# string form of `TaskEventType` so the task layer doesn't need to import
# the enum just to fire an event.
type StageEmitter = Callable[[str, str, dict[str, object]], Awaitable[None]]

_STAGE_TYPE_BY_NAME: dict[str, TaskEventType] = {
    "stage_started": TaskEventType.STAGE_STARTED,
    "stage_progress": TaskEventType.STAGE_PROGRESS,
    "stage_completed": TaskEventType.STAGE_COMPLETED,
}


def make_stage_emitter(jc: JobContext) -> StageEmitter:
    """Return an async emitter that publishes stage events for `jc`'s task.

    The emitter is best-effort: if the bus rejects the publish, the error
    is logged at WARNING and swallowed so the underlying task body
    continues. Stage telemetry is observability, not correctness.
    """

    async def _emit(
        stage: str,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        kind = _STAGE_TYPE_BY_NAME.get(event_type)
        if kind is None:
            await jc.log.awarning(
                "stage_event_unknown_type",
                event_type=event_type,
                stage=stage,
            )
            return
        try:
            await jc.events.emit(
                TaskEvent(
                    library_id=jc.library_id,
                    task_id=jc.task_id,
                    seq=0,  # bus assigns the real seq atomically
                    timestamp=datetime.now(UTC),
                    type=kind,
                    stage_name=stage,
                    payload=payload,
                )
            )
        except Exception as exc:
            await jc.log.awarning(
                "stage_event_emit_failed",
                stage=stage,
                event_type=event_type,
                error=str(exc),
            )

    return _emit


__all__ = ["StageEmitter", "make_stage_emitter"]
