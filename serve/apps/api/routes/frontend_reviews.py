"""Frontend `/api` review adapter backed by durable review tasks."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Literal, cast

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api._task_deps import get_task_event_bus, get_task_queue, get_task_store
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.middleware.sse_bridge import parse_last_event_id
from apps.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, encode_event
from packages.core.api_errors import ErrorCode, ErrorEnvelope
from packages.core.errors import LibraryNotFoundError
from packages.core.models import Library
from packages.orchestration.adapters.postgres_task_store import PostgresTaskStore
from packages.orchestration.errors import QueueFullError, TaskNotFoundError
from packages.orchestration.queue import (
    TaskEvent,
    TaskEventBus,
    TaskEventType,
    TaskHandle,
    TaskQueue,
    TaskSpec,
    TaskState,
)

router = APIRouter(prefix="/api/libraries/{library_id}/reviews", tags=["libraries"])

ReviewRunStatus = Literal[
    "idle", "queued", "running", "backgrounded", "cancelled", "failed", "done"
]
PipelineStepStatus = Literal["done", "active", "pending"]
PipelineDetailStatus = Literal["done", "active"]
FeedbackTone = Literal["success", "info", "warning", "danger"]

_REVIEW_DRAFT_TOKEN_LIMIT = 80_000
_STAGE_ORDER = (
    "subtopic_decompose",
    "subtopic_local_search",
    "subtopic_draft",
    "citation_check",
    "final_compose",
)
_STAGE_LABELS: dict[str, str] = {
    "subtopic_decompose": "Decompose into subtopics",
    "subtopic_local_search": "Retrieve evidence",
    "subtopic_draft": "Draft sections",
    "citation_check": "Check citations",
    "final_compose": "Compose final draft",
}


class ReviewPipelineDetail(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    status: PipelineDetailStatus


class ReviewPipelineStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    label: str
    status: PipelineStepStatus
    details: list[ReviewPipelineDetail] | None = None


class ReviewRunStat(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    value: str
    accent: bool | None = None


class ReviewCitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    type: str
    author: str
    is_new: bool | None = Field(default=None, alias="isNew")


class ReviewDraftSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    heading: str
    markdown: str
    citations: list[str]
    unsubstantiated: bool | None = None


class ReviewDraft(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    authors: list[str]
    generated_at_label: str = Field(alias="generatedAtLabel")
    badge_label: str = Field(alias="badgeLabel")
    total_tokens_label: str = Field(alias="totalTokensLabel")
    draft_tokens: int = Field(alias="draftTokens", ge=0)
    draft_token_limit: int = Field(alias="draftTokenLimit", ge=1)
    model_label: str = Field(alias="modelLabel")
    status_label: str = Field(alias="statusLabel")
    sections: list[ReviewDraftSection]


class ReviewRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    library_id: str = Field(alias="libraryId")
    status: ReviewRunStatus
    progress: int = Field(ge=0, le=100)
    task_id: str | None = Field(default=None, alias="taskId")
    stream_url: str | None = Field(default=None, alias="streamUrl")
    backgrounded: bool | None = None


class ReviewCurrentResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run: ReviewRun | None
    pipeline_steps: list[ReviewPipelineStep] | None = Field(default=None, alias="pipelineSteps")
    run_stats: list[ReviewRunStat] | None = Field(default=None, alias="runStats")
    citations: list[ReviewCitation] | None = None
    draft: ReviewDraft | None = None
    stream_url: str | None = Field(default=None, alias="streamUrl")


class ReviewAcceptedResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run: ReviewRun
    task_id: str = Field(alias="taskId")
    stream_url: str = Field(alias="streamUrl")
    pipeline_steps: list[ReviewPipelineStep] = Field(alias="pipelineSteps")
    run_stats: list[ReviewRunStat] = Field(alias="runStats")
    citations: list[ReviewCitation]
    draft: ReviewDraft


class ReviewCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    topic: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, max_length=2000)
    document_ids: list[str] = Field(default_factory=list, alias="documentIds", max_length=100)
    mode: str | None = Field(default=None, max_length=64)


class ReviewRegenerateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    instructions: str | None = Field(default=None, max_length=2000)
    keep_completed_sections: bool = Field(default=True, alias="keepCompletedSections")


class ReviewCancelRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    keep_generated_sections: bool = Field(default=True, alias="keepGeneratedSections")


class ReviewMutationFeedback(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tone: FeedbackTone
    title: str
    detail: str
    action: str | None = None
    run: ReviewRun | None = None


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


async def _get_library(container: AppContainer, library_id: str) -> Library:
    library = await container.library_repo.get(library_id)
    if library is None:
        raise LibraryNotFoundError(library_id)
    return library


async def _ensure_task_store_library(store: PostgresTaskStore, library: Library) -> None:
    try:
        await store.ensure_library(library)
    except QueueFullError:
        raise
    except Exception as exc:
        msg = f"Task store library sync failed: {exc}"
        raise QueueFullError(msg) from exc


@router.get(
    "/current",
    response_model=ReviewCurrentResponse,
    response_model_by_alias=True,
)
async def get_current_review_run(
    library_id: str = Path(..., description="Library slug"),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    _principal: Principal = Depends(get_current_principal),
) -> ReviewCurrentResponse | JSONResponse:
    await _ensure_library(container, library_id)
    state = await _latest_active_review_state(queue, library_id)
    if state is None:
        return JSONResponse(content={"run": None})
    return _current_response_from_state(state)


@router.post(
    "",
    response_model=ReviewAcceptedResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_review_run(
    body: ReviewCreateRequest = Body(default_factory=ReviewCreateRequest),
    library_id: str = Path(..., description="Library slug"),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    store: PostgresTaskStore = Depends(get_task_store),
    _principal: Principal = Depends(get_current_principal),
) -> ReviewAcceptedResponse:
    library = await _get_library(container, library_id)
    await _ensure_task_store_library(store, library)
    topic = _resolve_create_topic(library, body)
    handle = await queue.enqueue(
        library_id,
        TaskSpec(
            library_id=library_id,
            task_type="run_review",
            input_payload=_create_payload(topic, body),
            dedup_key=None,
        ),
    )
    return _accepted_response_from_handle(
        library_id=library_id,
        handle=handle,
        topic=topic,
        status_value="queued",
    )


@router.post(
    "/{review_run_id}/sections/{section_id}:regenerate",
    response_model=ReviewAcceptedResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def regenerate_review_section(
    body: ReviewRegenerateRequest = Body(default_factory=ReviewRegenerateRequest),
    library_id: str = Path(..., description="Library slug"),
    review_run_id: str = Path(..., description="Existing review run task id"),
    section_id: str = Path(..., description="Draft section identifier"),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    store: PostgresTaskStore = Depends(get_task_store),
    _principal: Principal = Depends(get_current_principal),
) -> ReviewAcceptedResponse:
    library = await _get_library(container, library_id)
    state = await queue.get(library_id, review_run_id)
    if state is None or state.task_type != "run_review":
        raise TaskNotFoundError(library_id, review_run_id)
    if state.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Review run is still active: {review_run_id}",
        )
    topic = _regeneration_topic(section_id, body)
    await _ensure_task_store_library(store, library)
    handle = await queue.enqueue(
        library_id,
        TaskSpec(
            library_id=library_id,
            task_type="run_review",
            input_payload={
                "topic": topic,
                "mode": "regenerate_section",
                "source_review_run_id": review_run_id,
                "section_id": section_id,
                "instructions": body.instructions or "",
                "keep_completed_sections": body.keep_completed_sections,
            },
        ),
    )
    return _accepted_response_from_handle(
        library_id=library_id,
        handle=handle,
        topic=topic,
        status_value="queued",
    )


@router.post(
    "/{review_run_id}:cancel",
    response_model=ReviewMutationFeedback,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_review_run(
    body: ReviewCancelRequest = Body(default_factory=ReviewCancelRequest),
    library_id: str = Path(..., description="Library slug"),
    review_run_id: str = Path(..., description="Existing review run task id"),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    _principal: Principal = Depends(get_current_principal),
) -> ReviewMutationFeedback:
    await _ensure_library(container, library_id)
    state = await queue.get(library_id, review_run_id)
    if state is None or state.task_type != "run_review":
        raise TaskNotFoundError(library_id, review_run_id)
    if state.status not in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Review run is already {state.status}: {review_run_id}",
        )
    cancelled = await queue.cancel(library_id, review_run_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Review run could not be cancelled: {review_run_id}",
        )
    detail = (
        "Review generation was cancelled and generated sections were kept."
        if body.keep_generated_sections
        else "Review generation was cancelled and generated sections can be discarded."
    )
    run = _run_from_state(state, override_status="cancelled")
    return ReviewMutationFeedback(
        tone="warning",
        title="Review cancelled",
        detail=detail,
        action="Refresh",
        run=run,
    )


@router.get("/{review_run_id}/events")
async def stream_review_events(
    request: Request,
    library_id: str = Path(..., description="Library slug"),
    review_run_id: str = Path(..., description="Review run task id"),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    bus: TaskEventBus = Depends(get_task_event_bus),
    _principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    await _ensure_library(container, library_id)
    state = await queue.get(library_id, review_run_id)
    if state is None or state.task_type != "run_review":
        raise TaskNotFoundError(library_id, review_run_id)
    return StreamingResponse(
        _stream_review_events(
            request=request,
            bus=bus,
            library_id=library_id,
            task_id=review_run_id,
            since_seq=parse_last_event_id(request),
        ),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )


async def _latest_active_review_state(queue: TaskQueue, library_id: str) -> TaskState | None:
    handles = await queue.list_active(library_id)
    states: list[TaskState] = []
    for handle in handles:
        state = await queue.get(library_id, handle.task_id)
        if state is not None and state.task_type == "run_review":
            states.append(state)
    if not states:
        return None
    return max(states, key=lambda state: state.enqueued_at)


def _resolve_create_topic(library: Library, body: ReviewCreateRequest) -> str:
    for candidate in (body.topic, body.instructions):
        if candidate is not None and candidate.strip():
            return candidate.strip()
    return library.name


def _create_payload(topic: str, body: ReviewCreateRequest) -> dict[str, object]:
    payload: dict[str, object] = {"topic": topic}
    if body.instructions is not None:
        payload["instructions"] = body.instructions.strip()
    if body.document_ids:
        payload["document_ids"] = body.document_ids
    if body.mode is not None:
        payload["mode"] = body.mode.strip()
    return payload


def _regeneration_topic(section_id: str, body: ReviewRegenerateRequest) -> str:
    instructions = (body.instructions or "").strip()
    if instructions:
        return instructions
    return f"Regenerate review section {section_id}"


def _current_response_from_state(state: TaskState) -> ReviewCurrentResponse:
    stream_url = _stream_url(state.library_id, state.task_id)
    return ReviewCurrentResponse(
        run=_run_from_state(state),
        pipelineSteps=_pipeline_for_state(state),
        runStats=_stats_for_state(state),
        citations=[],
        draft=_empty_draft(
            title="Review generation",
            status_label=_status_label(_run_status(state.status)),
            draft_tokens=0,
        ),
        streamUrl=stream_url if state.status in {"queued", "running"} else None,
    )


def _accepted_response_from_handle(
    *,
    library_id: str,
    handle: TaskHandle,
    topic: str,
    status_value: ReviewRunStatus,
) -> ReviewAcceptedResponse:
    stream_url = _stream_url(library_id, handle.task_id)
    run = ReviewRun(
        id=handle.task_id,
        libraryId=library_id,
        status=status_value,
        progress=0,
        taskId=handle.task_id,
        streamUrl=stream_url,
        backgrounded=False,
    )
    return ReviewAcceptedResponse(
        run=run,
        taskId=handle.task_id,
        streamUrl=stream_url,
        pipelineSteps=_initial_pipeline(),
        runStats=_initial_stats(),
        citations=[],
        draft=_empty_draft(
            title=topic,
            status_label=_status_label(status_value),
            draft_tokens=0,
        ),
    )


def _run_from_state(
    state: TaskState,
    *,
    override_status: ReviewRunStatus | None = None,
) -> ReviewRun:
    review_status = override_status or _run_status(state.status)
    return ReviewRun(
        id=state.task_id,
        libraryId=state.library_id,
        status=review_status,
        progress=_progress_percent(state),
        taskId=state.task_id,
        streamUrl=_stream_url(state.library_id, state.task_id)
        if state.status in {"queued", "running"}
        else None,
        backgrounded=False,
    )


def _run_status(status_value: str) -> ReviewRunStatus:
    if status_value == "completed":
        return "done"
    if status_value == "cancelled":
        return "cancelled"
    if status_value == "failed":
        return "failed"
    if status_value == "running":
        return "running"
    return "queued"


def _progress_percent(state: TaskState) -> int:
    return max(0, min(100, round(state.progress * 100)))


def _stream_url(library_id: str, task_id: str) -> str:
    return f"/api/libraries/{library_id}/reviews/{task_id}/events"


def _initial_pipeline() -> list[ReviewPipelineStep]:
    return [
        ReviewPipelineStep(
            id=stage,
            label=label,
            status="active" if index == 0 else "pending",
        )
        for index, (stage, label) in enumerate(_STAGE_LABELS.items())
    ]


def _pipeline_for_state(state: TaskState) -> list[ReviewPipelineStep]:
    if state.status == "completed":
        return _pipeline_from_stage("final_compose", "stage_completed")
    if state.status in {"failed", "cancelled"}:
        return _pipeline_from_stage(state.current_stage, "stage_completed")
    if state.current_stage:
        return _pipeline_from_stage(state.current_stage, "stage_started")
    return _initial_pipeline()


def _pipeline_from_stage(stage_name: str | None, event_kind: str) -> list[ReviewPipelineStep]:
    active_index = _STAGE_ORDER.index(stage_name) if stage_name in _STAGE_ORDER else 0
    steps: list[ReviewPipelineStep] = []
    for index, stage in enumerate(_STAGE_ORDER):
        if index < active_index or (index == active_index and event_kind == "stage_completed"):
            step_status: PipelineStepStatus = "done"
        elif index == active_index:
            step_status = "active"
        else:
            step_status = "pending"
        steps.append(
            ReviewPipelineStep(
                id=stage,
                label=_STAGE_LABELS[stage],
                status=step_status,
                details=_pipeline_details(stage, event_kind) if index == active_index else None,
            )
        )
    return steps


def _pipeline_details(stage_name: str, event_kind: str) -> list[ReviewPipelineDetail] | None:
    if stage_name != "subtopic_draft":
        return None
    return [
        ReviewPipelineDetail(
            label="Draft section",
            status="done" if event_kind == "stage_completed" else "active",
        )
    ]


def _initial_stats() -> list[ReviewRunStat]:
    return [
        ReviewRunStat(label="Progress", value="0%", accent=True),
        ReviewRunStat(label="Draft tokens", value=f"0 / {_REVIEW_DRAFT_TOKEN_LIMIT:,}"),
        ReviewRunStat(label="Cost", value="$0.00"),
    ]


def _stats_for_state(state: TaskState) -> list[ReviewRunStat]:
    return [
        ReviewRunStat(label="Progress", value=f"{_progress_percent(state)}%", accent=True),
        ReviewRunStat(label="Status", value=_status_label(_run_status(state.status))),
        ReviewRunStat(label="Cost", value=f"${state.cost_usd:.2f}"),
    ]


def _empty_draft(
    *,
    title: str,
    status_label: str,
    draft_tokens: int,
) -> ReviewDraft:
    return ReviewDraft(
        title=title,
        authors=[],
        generatedAtLabel="Not generated yet",
        badgeLabel="Draft",
        totalTokensLabel=f"{draft_tokens:,} / {_REVIEW_DRAFT_TOKEN_LIMIT:,} tokens",
        draftTokens=draft_tokens,
        draftTokenLimit=_REVIEW_DRAFT_TOKEN_LIMIT,
        modelLabel="Review generation",
        statusLabel=status_label,
        sections=[],
    )


async def _stream_review_events(
    *,
    request: Request,
    bus: TaskEventBus,
    library_id: str,
    task_id: str,
    since_seq: int | None,
) -> AsyncIterator[bytes]:
    async for event in bus.stream(library_id, task_id, since_seq=since_seq):
        if await request.is_disconnected():
            return
        for frame, terminal in _frames_for_task_event(event, task_id=task_id):
            yield frame
            if terminal:
                return


def _frames_for_task_event(event: TaskEvent, *, task_id: str) -> list[tuple[bytes, bool]]:
    if event.type == TaskEventType.TASK_QUEUED:
        return [(_encode_sse("status", {"status": "queued", "progress": 0}, event.seq), False)]
    if event.type == TaskEventType.TASK_STARTED:
        return [(_encode_sse("status", {"status": "running", "progress": 0}, event.seq), False)]
    if event.type in {
        TaskEventType.STAGE_STARTED,
        TaskEventType.STAGE_PROGRESS,
        TaskEventType.STAGE_COMPLETED,
    }:
        if event.stage_name == "draft_delta":
            return [
                (_encode_sse("draft_delta", _draft_delta_payload(event.payload), event.seq), False)
            ]
        pipeline = _pipeline_from_stage(event.stage_name, str(event.type))
        return [
            (
                _encode_sse(
                    "pipeline", [step.model_dump(mode="json") for step in pipeline], event.seq
                ),
                False,
            )
        ]
    if event.type == TaskEventType.CITATION_ADDED:
        citations = _citations_payload(event.payload)
        if not citations:
            return []
        return [(_encode_sse("citations", citations, event.seq), False)]
    if event.type == TaskEventType.COST_UPDATED:
        return [(_encode_sse("stats", _stats_payload(event.payload), event.seq), False)]
    if event.type == TaskEventType.TASK_CANCELLED:
        return [
            (_encode_sse("status", {"status": "cancelled", "progress": 100}, event.seq), False),
            (_encode_sse("done", {"status": "cancelled"}, event.seq), True),
        ]
    if event.type == TaskEventType.TASK_FAILED:
        envelope = ErrorEnvelope(
            code=ErrorCode.UPSTREAM_ERROR,
            message=str(event.payload.get("message") or "Review generation failed"),
            request_id=str(event.payload.get("request_id") or task_id),
            details={"type": event.payload.get("error_code") or "TaskFailed"},
        ).model_dump(mode="json")
        return [(_encode_sse("error", envelope, event.seq), True)]
    if event.type == TaskEventType.TASK_COMPLETED:
        return [
            (_encode_sse("status", {"status": "done", "progress": 100}, event.seq), False),
            (_encode_sse("done", {"status": "done"}, event.seq), True),
        ]
    return []


def _encode_sse(event: str, payload: object, seq: int) -> bytes:
    return f"id: {seq}\n".encode() + encode_event(event, payload)


def _draft_delta_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "sectionId": _payload_str(payload, "sectionId")
        or _payload_str(payload, "section_id")
        or "",
        "markdownDelta": _payload_str(payload, "markdownDelta")
        or _payload_str(payload, "markdown_delta")
        or "",
        "citations": _payload_string_list(payload, "citations"),
        "draftTokens": _payload_int(payload, "draftTokens")
        or _payload_int(payload, "draft_tokens")
        or 0,
    }


def _citations_payload(payload: dict[str, object]) -> list[dict[str, object]]:
    raw = payload.get("citations")
    if not isinstance(raw, list):
        return []
    items = cast("list[object]", raw)
    citations: list[dict[str, object]] = []
    for item in items:
        if isinstance(item, Mapping):
            mapped = cast("Mapping[object, object]", item)
            citation_id = mapped.get("id")
            citation_type = mapped.get("type")
            author = mapped.get("author")
            if (
                isinstance(citation_id, str)
                and isinstance(citation_type, str)
                and isinstance(author, str)
            ):
                citation: dict[str, object] = {
                    "id": citation_id,
                    "type": citation_type,
                    "author": author,
                }
                is_new = mapped.get("isNew", mapped.get("is_new"))
                if isinstance(is_new, bool):
                    citation["isNew"] = is_new
                citations.append(citation)
    return citations


def _stats_payload(payload: dict[str, object]) -> list[dict[str, object]]:
    tokens_in = _payload_int(payload, "tokens_in") or 0
    tokens_out = _payload_int(payload, "tokens_out") or 0
    cost = _payload_float(payload, "cost_usd") or 0.0
    return [
        {
            "label": "Draft tokens",
            "value": f"{tokens_out:,} / {_REVIEW_DRAFT_TOKEN_LIMIT:,}",
            "accent": True,
        },
        {"label": "Input tokens", "value": f"{tokens_in:,}"},
        {"label": "Cost", "value": f"${cost:.2f}"},
    ]


def _status_label(status_value: ReviewRunStatus) -> str:
    return {
        "idle": "Idle",
        "queued": "Queued",
        "running": "Running",
        "backgrounded": "Running in background",
        "cancelled": "Cancelled",
        "failed": "Failed",
        "done": "Done",
    }[status_value]


def _payload_str(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _payload_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _payload_float(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _payload_string_list(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    items = cast("list[object]", value)
    return [item for item in items if isinstance(item, str)]
