"""Task lifecycle endpoints (ADR-0009 §5, ADR-0010 §3).

All routes are scoped under `/v1/libraries/{library_id}/tasks`. They map
the `TaskQueue` Protocol behaviour onto HTTP verbs:

| Method | Path                                           | Purpose                          |
|--------|------------------------------------------------|----------------------------------|
| GET    | /v1/libraries/{lib}/tasks                      | list active (queued + running)   |
| GET    | /v1/libraries/{lib}/tasks/{task_id}            | snapshot                         |
| GET    | /v1/libraries/{lib}/tasks/{task_id}/events     | SSE stream (ADR-0010 wire)       |
| POST   | /v1/libraries/{lib}/tasks/{task_id}/cancel     | cooperative cancel               |

Per CODING_STANDARDS §13.5 every endpoint is library-scoped — there is no
implicit "current library".
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api._task_deps import get_task_event_bus, get_task_queue
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.middleware.sse_bridge import parse_last_event_id, stream_task_events
from apps.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE
from packages.core.errors import LibraryNotFoundError
from packages.orchestration.errors import TaskNotFoundError
from packages.orchestration.queue import (
    TaskEventBus,
    TaskHandle,
    TaskQueue,
    TaskState,
)

router = APIRouter(prefix="/v1/libraries/{library_id}/tasks", tags=["tasks"])

_TASK_ID_DESC = "ULID returned by the original enqueue call"


class TaskHandleResponse(BaseModel):
    """Wire shape of `TaskHandle` for API consumers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str
    task_id: str
    enqueued_at: datetime


class TaskStateResponse(BaseModel):
    """Wire shape of `TaskState` (matches `packages.orchestration.queue.TaskState`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str
    task_id: str
    task_type: str
    status: str
    progress: float = Field(ge=0.0, le=1.0)
    current_stage: str | None
    enqueued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    result_pointer: str | None
    cost_usd: float


class CancelResponse(BaseModel):
    """Result of a cancel attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cancelled: bool
    library_id: str
    task_id: str


def _to_handle_response(handle: TaskHandle) -> TaskHandleResponse:
    return TaskHandleResponse(
        library_id=handle.library_id,
        task_id=handle.task_id,
        enqueued_at=handle.enqueued_at,
    )


def _to_state_response(state: TaskState) -> TaskStateResponse:
    return TaskStateResponse(
        library_id=state.library_id,
        task_id=state.task_id,
        task_type=state.task_type,
        status=state.status,
        progress=state.progress,
        current_stage=state.current_stage,
        enqueued_at=state.enqueued_at,
        started_at=state.started_at,
        finished_at=state.finished_at,
        error=state.error,
        result_pointer=state.result_pointer,
        cost_usd=state.cost_usd,
    )


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


@router.get(
    "",
    response_model=list[TaskHandleResponse],
    summary="List active tasks for a library",
    response_description="Tasks in queued or running status, oldest first.",
)
async def list_active_tasks(
    library_id: str = Path(..., description="Library slug"),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    _principal: Principal = Depends(get_current_principal),
) -> list[TaskHandleResponse]:
    await _ensure_library(container, library_id)
    handles = await queue.list_active(library_id)
    return [_to_handle_response(h) for h in handles]


@router.get(
    "/{task_id}",
    response_model=TaskStateResponse,
    summary="Get a task snapshot",
)
async def get_task(
    library_id: str = Path(..., description="Library slug"),
    task_id: str = Path(..., description=_TASK_ID_DESC),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    _principal: Principal = Depends(get_current_principal),
) -> TaskStateResponse:
    await _ensure_library(container, library_id)
    state = await queue.get(library_id, task_id)
    if state is None:
        raise TaskNotFoundError(library_id, task_id)
    return _to_state_response(state)


@router.get(
    "/{task_id}/events",
    summary="SSE stream of task events (ADR-0010 wire format)",
)
async def stream_events(
    request: Request,
    library_id: str = Path(..., description="Library slug"),
    task_id: str = Path(..., description=_TASK_ID_DESC),
    since_seq: int | None = Query(
        default=None,
        ge=0,
        description="Replay events with seq > this. Overrides `Last-Event-ID`.",
    ),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    bus: TaskEventBus = Depends(get_task_event_bus),
    _principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    """Server-Sent Events stream of `TaskEvent`s for a task.

    Reconnect protocol (ADR-0010 §5):
    - Browser EventSource sends `Last-Event-ID: <seq>` on auto-reconnect.
    - Explicit `?since_seq=N` query parameter overrides the header.
    """
    await _ensure_library(container, library_id)
    state = await queue.get(library_id, task_id)
    if state is None:
        raise TaskNotFoundError(library_id, task_id)
    last_event_id = parse_last_event_id(request) if since_seq is None else None
    effective_since = since_seq if since_seq is not None else last_event_id
    return StreamingResponse(
        stream_task_events(
            request,
            bus,
            library_id=library_id,
            task_id=task_id,
            since_seq=effective_since,
        ),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )


@router.post(
    "/{task_id}/cancel",
    response_model=CancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cooperative cancel of a queued or running task",
)
async def cancel_task(
    library_id: str = Path(..., description="Library slug"),
    task_id: str = Path(..., description=_TASK_ID_DESC),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    _principal: Principal = Depends(get_current_principal),
) -> CancelResponse:
    await _ensure_library(container, library_id)
    state = await queue.get(library_id, task_id)
    if state is None:
        raise TaskNotFoundError(library_id, task_id)
    if state.status not in {"queued", "running"}:
        # Already terminal — surface 409 with details so the client can refresh.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task already {state.status}",
        )
    cancelled = await queue.cancel(library_id, task_id)
    return CancelResponse(cancelled=cancelled, library_id=library_id, task_id=task_id)
