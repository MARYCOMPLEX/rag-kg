"""Shared fakes for worker job integration tests.

The job lifecycle (`apps.worker.jobs.base.job_lifecycle`) only touches
two adapters: a `task_store` and a `task_events` bus. Both are loaded
from the `ctx` dict via duck typing, so we can swap real adapters for
in-memory fakes without standing up Postgres / Redis containers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from packages.orchestration.queue import TaskEvent


class FakeTaskStore:
    """In-memory replacement for `PostgresTaskStore` covering the
    methods the lifecycle helper exercises.
    """

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], dict[str, Any]] = {}
        self.update_calls: list[dict[str, Any]] = []

    async def get(self, library_id: str, task_id: str) -> Any | None:
        row = self.rows.get((library_id, task_id))
        if row is None:
            return None
        return _DotDict(row)

    async def update_status(
        self,
        library_id: str,
        task_id: str,
        *,
        status: str,
        progress: float | None = None,
        current_stage: str | None = None,
        result_pointer: str | None = None,
        error: str | None = None,
        cost_usd: float | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> bool:
        key = (library_id, task_id)
        row = self.rows.setdefault(
            key,
            {
                "library_id": library_id,
                "task_id": task_id,
                "task_type": "test",
                "status": status,
                "progress": 0.0,
                "current_stage": None,
                "started_at": None,
                "finished_at": None,
                "result_pointer": None,
                "error": None,
                "cost_usd": 0.0,
            },
        )
        row["status"] = status
        if progress is not None:
            row["progress"] = progress
        if current_stage is not None:
            row["current_stage"] = current_stage
        if started_at is not None:
            row["started_at"] = started_at
        if finished_at is not None:
            row["finished_at"] = finished_at
        if result_pointer is not None:
            row["result_pointer"] = result_pointer
        if error is not None:
            row["error"] = error
        if cost_usd is not None:
            row["cost_usd"] = cost_usd
        self.update_calls.append({"status": status, **dict(row.items())})
        return True


class FakeTaskEventBus:
    """Captures every emitted `TaskEvent` so tests can assert on them."""

    def __init__(self) -> None:
        self.events: list[TaskEvent] = []

    async def emit(self, event: TaskEvent) -> None:
        self.events.append(event)

    async def stream(
        self,
        library_id: str,
        task_id: str,
        *,
        since_seq: int | None = None,
    ) -> Any:
        return iter([])

    def stage_events(self) -> list[tuple[str | None, str]]:
        return [(e.stage_name, e.type.value) for e in self.events]


class _DotDict(dict[str, Any]):
    """Dict that also supports attribute access — matches `TaskState`-ish duck typing."""

    def __getattr__(self, item: str) -> Any:
        if item in self:
            return self[item]
        msg = f"missing attribute: {item!r}"
        raise AttributeError(msg)


@pytest.fixture
def fake_task_store() -> FakeTaskStore:
    return FakeTaskStore()


@pytest.fixture
def fake_event_bus() -> FakeTaskEventBus:
    return FakeTaskEventBus()


@pytest.fixture
def base_ctx(fake_task_store: FakeTaskStore, fake_event_bus: FakeTaskEventBus) -> dict[str, Any]:
    """Minimal `ctx` accepted by `JobContext.from_arq`."""
    # Pre-seed a `queued` row so `job_lifecycle` finds a non-terminal state.
    return {
        "task_store": fake_task_store,
        "task_events": fake_event_bus,
        "_now": datetime.now(UTC),
    }
