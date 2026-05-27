"""Arq-backed implementation of `TaskQueue` (ADR-0009).

Architecture:

- ``ArqTaskQueue.enqueue`` mints a ULID, persists a ``queued`` row in
  Postgres ``tasks``, then forwards to ``arq.connections.ArqRedis.enqueue_job``
  using the canonical job name (`run_<task_type>`).
- ``get`` / ``list_active`` / ``cancel`` go through ``PostgresTaskStore``;
  Arq's Redis state is treated as ephemeral.
- Cooperative cancel: the worker job polls ``PostgresTaskStore.get(...)`` at
  every stage boundary; ``cancel`` writes ``status=cancelled`` and emits a
  ``task_cancelled`` event so any in-flight stage can surface the signal.

Idempotency: when ``TaskSpec.dedup_key`` is set, a re-enqueue with the same
key returns the existing ``TaskHandle`` instead of creating a duplicate row
or new Arq job (ADR-0009 R-Q3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

import structlog

from packages.observability import with_span
from packages.orchestration._internal.ulid import new_ulid
from packages.orchestration.adapters.postgres_task_store import PostgresTaskStore
from packages.orchestration.errors import QueueFullError
from packages.orchestration.queue import (
    TaskEvent,
    TaskEventBus,
    TaskEventType,
    TaskHandle,
    TaskId,
    TaskSpec,
    TaskState,
)

logger = structlog.get_logger(__name__)

# Job name = "run_<task_type>", matching `apps/worker/jobs/<task_type>.run`.
_JOB_NAME_PREFIX = "run_"


class _ArqLike(Protocol):
    """Minimum surface area we need from `arq.connections.ArqRedis`.

    Tests inject a fake; production wires `arq.create_pool(...)`.
    """

    async def enqueue_job(
        self,
        function: str,
        *args: object,
        _job_id: str | None = None,
        _queue_name: str | None = None,
        **kwargs: object,
    ) -> object: ...


def _job_name_for(task_type: str) -> str:
    return f"{_JOB_NAME_PREFIX}{task_type}"


class ArqTaskQueue:
    """Concrete `TaskQueue` (ADR-0009) using Arq + Postgres."""

    def __init__(
        self,
        *,
        arq: _ArqLike,
        store: PostgresTaskStore,
        events: TaskEventBus,
        queue_name: str = "arq:queue",
    ) -> None:
        self._arq = arq
        self._store = store
        self._events = events
        self._queue_name = queue_name

    async def enqueue(self, library_id: str, spec: TaskSpec) -> TaskHandle:
        """Persist + enqueue. Returns a fresh handle (or the dedup match)."""
        if library_id != spec.library_id:
            msg = f"library_id mismatch: route={library_id!r} spec={spec.library_id!r}"
            raise ValueError(msg)
        async with with_span(
            "orchestration.arq.enqueue",
            library_id=spec.library_id,
            task_type=spec.task_type,
        ):
            if spec.dedup_key:
                existing = await self._store.find_by_dedup_key(library_id, spec.dedup_key)
                if existing is not None:
                    await logger.ainfo(
                        "task_enqueue_dedup_hit",
                        library_id=library_id,
                        task_id=existing.task_id,
                        dedup_key=spec.dedup_key,
                    )
                    return TaskHandle(
                        library_id=existing.library_id,
                        task_id=existing.task_id,
                        enqueued_at=existing.enqueued_at,
                    )

            task_id: TaskId = new_ulid()
            enqueued_at = datetime.now(UTC)
            try:
                handle = await self._store.insert(
                    task_id=task_id,
                    spec=spec,
                    enqueued_at=enqueued_at,
                )
            except Exception as exc:
                await logger.aerror(
                    "task_store_insert_failed",
                    library_id=library_id,
                    task_id=task_id,
                    error=str(exc),
                )
                raise QueueFullError(f"Task store unavailable: {exc}") from exc
            try:
                await self._arq.enqueue_job(
                    _job_name_for(spec.task_type),
                    library_id=library_id,
                    task_id=task_id,
                    input_payload=spec.input_payload,
                    _job_id=task_id,
                    _queue_name=self._queue_name,
                )
            except Exception as exc:
                await logger.aerror(
                    "task_enqueue_failed",
                    library_id=library_id,
                    task_id=task_id,
                    error=str(exc),
                )
                raise QueueFullError(f"Arq enqueue rejected job: {exc}") from exc

            await self._events.emit(
                TaskEvent(
                    library_id=library_id,
                    task_id=task_id,
                    seq=0,  # bus reassigns via INCR
                    timestamp=enqueued_at,
                    type=TaskEventType.TASK_QUEUED,
                    stage_name=None,
                    payload={
                        "task_type": spec.task_type,
                        "input_summary": _summarise(spec.input_payload),
                    },
                )
            )
            return handle

    async def get(self, library_id: str, task_id: TaskId) -> TaskState | None:
        return await self._store.get(library_id, task_id)

    async def cancel(self, library_id: str, task_id: TaskId) -> bool:
        """Cooperative cancel: flag DB row, broadcast event, return success."""
        async with with_span(
            "orchestration.arq.cancel",
            library_id=library_id,
            task_id=task_id,
        ):
            cancelled = await self._store.cancel_if_active(library_id, task_id)
            if not cancelled:
                return False
            await self._events.emit(
                TaskEvent(
                    library_id=library_id,
                    task_id=task_id,
                    seq=0,
                    timestamp=datetime.now(UTC),
                    type=TaskEventType.TASK_CANCELLED,
                    stage_name=None,
                    payload={"reason": "user_cancel", "by": "api"},
                )
            )
            return True

    async def list_active(self, library_id: str) -> tuple[TaskHandle, ...]:
        return await self._store.list_active(library_id)


def _summarise(payload: dict[str, object]) -> str:
    """Cheap one-line summary for the `task_queued` event payload."""
    if not payload:
        return ""
    parts: list[str] = []
    for key, value in payload.items():
        rendered = repr(value) if not isinstance(value, str) else value
        if len(rendered) > 80:
            rendered = rendered[:77] + "..."
        parts.append(f"{key}={rendered}")
        if len(parts) >= 3:
            parts.append("...")
            break
    return " ".join(parts)
