"""Async task queue contracts (ADR-0009 + ADR-0010).

Models and Protocols for the long-task system that powers ingest,
KG extraction, community rebuild, review, reason, hypothesize, eval
snapshot, chat, and library status checks.

Implementations live in `packages/orchestration/_internal/queue/` and
`packages/orchestration/adapters/arq_queue.py` (per CODING_STANDARDS §2.3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.retrieval.protocols import RetrievalBudget

# ----------------------------------------------------------------------
# Core task types
# ----------------------------------------------------------------------

type TaskId = str  # ULID; sortable
type TaskType = Literal[
    "ingest_document",
    "ingest_batch",
    "extract_kg",
    "rebuild_community",
    "run_review",
    "run_chat",
    "run_reason",
    "run_hypothesize",
    "library_status_check",
    "eval_snapshot",
    "library_purge",
]


class BudgetSpec(BaseModel):
    """Polymorphic budget reference for queued tasks (ADR_REVIEW §3 R4).

    Discriminated by `TaskSpec.task_type` at the call site; queue layer
    only stores and forwards. Workers extract the relevant inner budget.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    retrieval: RetrievalBudget | None = None
    task: TaskBudgetRef | None = None


class TaskBudgetRef(BaseModel):
    """Per-task long-running ceilings (mirror of `protocols.TaskBudget`).

    Defined here to break the cycle (queue layer cannot import the full
    TaskBudget model from protocols.py since protocols depends on this
    file via `__init__.py` re-exports). Keep both in sync.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_subtopics: int = Field(default=8, ge=1, le=30)
    max_chunks_per_subtopic: int = Field(default=6, ge=1, le=50)
    max_llm_calls: int = Field(default=30, ge=1, le=300)
    max_total_tokens: int = Field(default=80_000, ge=1000)
    timeout_s: float = Field(default=600.0, ge=10.0)


class TaskSpec(BaseModel):
    """Input to TaskQueue.enqueue — what to do, scoped to a library."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    task_type: TaskType
    input_payload: dict[str, object] = Field(default_factory=dict)
    budget: BudgetSpec | None = None
    priority: int = Field(default=0, ge=0, le=10)
    created_by: str | None = None
    dedup_key: str | None = None


class TaskHandle(BaseModel):
    """Returned by `TaskQueue.enqueue` — opaque pointer for clients."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    task_id: TaskId
    enqueued_at: datetime


class TaskState(BaseModel):
    """Snapshot of task lifecycle (ADR-0009 §tasks-table)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    task_id: TaskId
    task_type: TaskType
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    current_stage: str | None = None
    enqueued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    result_pointer: str | None = None  # MinIO key or postgres row ref
    cost_usd: float = 0.0


# ----------------------------------------------------------------------
# Task event stream (ADR-0010)
# ----------------------------------------------------------------------


class TaskEventType(StrEnum):
    """Event types emitted onto the task event bus.

    The protocol is append-only: new types may be added but never removed
    or renamed (ADR-0010 §schema_version).
    """

    TASK_QUEUED = "task_queued"
    TASK_STARTED = "task_started"
    STAGE_STARTED = "stage_started"
    STAGE_PROGRESS = "stage_progress"
    STAGE_COMPLETED = "stage_completed"
    TOKEN = "token"
    CITATION_ADDED = "citation_added"
    COST_UPDATED = "cost_updated"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"


class TaskEvent(BaseModel):
    """A single event on the task event bus.

    `seq` is monotonic per-task starting at 0; clients may reconnect via
    `Last-Event-ID: <seq>` to backfill (ADR-0010).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    task_id: TaskId
    seq: int = Field(ge=0)
    timestamp: datetime
    type: TaskEventType
    stage_name: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    schema_version: int = 1


# ----------------------------------------------------------------------
# Protocols
# ----------------------------------------------------------------------


@runtime_checkable
class TaskQueue(Protocol):
    """Contract for the long-task scheduler (ADR-0009).

    All methods take `library_id` as the first positional arg per
    CODING_STANDARDS §6.5 / §7.1.
    """

    async def enqueue(self, library_id: str, spec: TaskSpec) -> TaskHandle: ...

    async def get(self, library_id: str, task_id: TaskId) -> TaskState | None: ...

    async def cancel(self, library_id: str, task_id: TaskId) -> bool: ...

    async def list_active(self, library_id: str) -> tuple[TaskHandle, ...]: ...


@runtime_checkable
class TaskEventBus(Protocol):
    """Contract for the SSE-backing event stream (ADR-0010).

    Implementations (Redis pub/sub + Stream) must guarantee monotonic
    `seq` per task and durable replay window for reconnect.
    """

    async def emit(self, event: TaskEvent) -> None: ...

    def stream(
        self,
        library_id: str,
        task_id: TaskId,
        *,
        since_seq: int | None = None,
    ) -> AsyncIterator[TaskEvent]: ...
