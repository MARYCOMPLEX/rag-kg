"""Frontend `/api` chat adapter backed by durable tasks and task events."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator, Mapping
from datetime import datetime
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api._task_deps import get_task_event_bus, get_task_queue
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.middleware.sse_bridge import parse_last_event_id
from apps.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, encode_event
from packages.context.protocols import Conversation, Turn
from packages.core.api_errors import ErrorCode, ErrorEnvelope
from packages.core.errors import LibraryNotFoundError
from packages.orchestration.errors import TaskNotFoundError
from packages.orchestration.protocols import Citation
from packages.orchestration.queue import (
    TaskEvent,
    TaskEventBus,
    TaskEventType,
    TaskQueue,
    TaskSpec,
)

router = APIRouter(prefix="/api/libraries/{library_id}/chat", tags=["libraries"])

ChatRole = Literal["user", "assistant"]
ChatMessageStatus = Literal["idle", "streaming", "done", "interrupted", "unsubstantiated"]


class ChatEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    label: str
    type: str
    title: str
    meta: str
    score: str
    snippet: str


def _empty_chat_evidence() -> list[ChatEvidence]:
    return []


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    role: ChatRole
    text: str
    status: ChatMessageStatus | None = None
    citations: list[str] | None = None


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: str = Field(alias="sessionId")
    title: str
    created_at_label: str = Field(alias="createdAtLabel")
    messages: list[ChatMessage]
    evidence: list[ChatEvidence]


class ChatQuestionContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    evidence_ids: list[str] = Field(default_factory=list, alias="evidenceIds")
    entity_ids: list[str] = Field(default_factory=list, alias="entityIds")


class ChatQuestionRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, alias="sessionId", min_length=1, max_length=64)
    context: ChatQuestionContext | None = None


class ChatQuestionResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(alias="taskId")
    stream_url: str = Field(alias="streamUrl")
    user_message: ChatMessage = Field(alias="userMessage")
    assistant_message: ChatMessage = Field(alias="assistantMessage")
    evidence: list[ChatEvidence] = Field(default_factory=_empty_chat_evidence)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


@router.get("/session", response_model=ChatSessionResponse, response_model_by_alias=True)
async def get_current_chat_session(
    library_id: str = Path(..., description="Library slug"),
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> ChatSessionResponse:
    await _ensure_library(container, library_id)
    conversations = await container.context_service.list(library_id, limit=1)
    conversation = (
        conversations[0]
        if conversations
        else await container.context_service.open(
            library_id=library_id,
            autocreate_title="New chat",
        )
    )
    turns = await container.context_service.history(conversation.conversation_id)
    return _session_response(conversation, turns)


@router.post(
    "/questions",
    response_model=ChatQuestionResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_chat_question(
    body: ChatQuestionRequest,
    library_id: str = Path(..., description="Library slug"),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    _principal: Principal = Depends(get_current_principal),
) -> ChatQuestionResponse:
    await _ensure_library(container, library_id)
    question = body.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question must not be empty",
        )

    created_new_session = body.session_id is None
    conversation = await _open_or_create_conversation(container, library_id, body, question)

    try:
        handle = await queue.enqueue(
            library_id,
            TaskSpec(
                library_id=library_id,
                task_type="run_chat",
                input_payload=_chat_task_payload(
                    conversation_id=conversation.conversation_id,
                    question=question,
                    context=body.context,
                ),
            ),
        )
    except Exception:
        if created_new_session:
            with contextlib.suppress(Exception):
                await container.context_service.delete(library_id, conversation.conversation_id)
        raise

    return ChatQuestionResponse(
        taskId=handle.task_id,
        streamUrl=f"/api/libraries/{library_id}/chat/questions/{handle.task_id}/events",
        userMessage=ChatMessage(
            id=_new_id("user"),
            role="user",
            text=question,
        ),
        assistantMessage=ChatMessage(
            id=_new_id("assistant"),
            role="assistant",
            text="",
            status="streaming",
            citations=[],
        ),
        evidence=[],
    )


@router.get("/questions/{task_id}/events")
async def stream_chat_question_events(
    request: Request,
    library_id: str = Path(..., description="Library slug"),
    task_id: str = Path(..., description="Task identifier"),
    container: AppContainer = Depends(get_container),
    queue: TaskQueue = Depends(get_task_queue),
    bus: TaskEventBus = Depends(get_task_event_bus),
    _principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    await _ensure_library(container, library_id)
    state = await queue.get(library_id, task_id)
    if state is None:
        raise TaskNotFoundError(library_id, task_id)
    return StreamingResponse(
        _stream_chat_events(
            request=request,
            bus=bus,
            library_id=library_id,
            task_id=task_id,
            since_seq=parse_last_event_id(request),
        ),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )


async def _open_or_create_conversation(
    container: AppContainer,
    library_id: str,
    body: ChatQuestionRequest,
    question: str,
) -> Conversation:
    if body.session_id is None:
        return await container.context_service.open(
            library_id=library_id,
            autocreate_title=_title_from_question(question),
        )
    try:
        return await container.context_service.open(
            library_id=library_id,
            conversation_id=body.session_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {body.session_id}",
        ) from exc


async def _stream_chat_events(
    *,
    request: Request,
    bus: TaskEventBus,
    library_id: str,
    task_id: str,
    since_seq: int | None,
) -> AsyncIterator[bytes]:
    citations_seen: list[str] = []
    async for event in bus.stream(library_id, task_id, since_seq=since_seq):
        if await request.is_disconnected():
            return
        for frame, terminal in _frames_for_task_event(
            event,
            citations_seen=citations_seen,
            task_id=task_id,
        ):
            yield frame
            if terminal:
                return


def _frames_for_task_event(
    event: TaskEvent,
    *,
    citations_seen: list[str],
    task_id: str,
) -> list[tuple[bytes, bool]]:
    if event.type == TaskEventType.TASK_STARTED:
        return [(_encode_sse("status", {"status": "streaming"}, event.seq), False)]
    if event.type == TaskEventType.TOKEN:
        token = _payload_str(event.payload, "token")
        if token is None:
            return []
        return [(_encode_sse("token", {"token": token}, event.seq), False)]
    if event.type == TaskEventType.STAGE_COMPLETED and event.stage_name == "evidence":
        evidence = _payload_evidence(event.payload)
        if not evidence:
            return []
        return [(_encode_sse("evidence", evidence, event.seq), False)]
    if event.type == TaskEventType.CITATION_ADDED:
        citation_ids = _payload_string_list(event.payload, "citation_ids")
        if not citation_ids:
            citation_ids = _payload_string_list(event.payload, "citations")
        if not citation_ids:
            return []
        citations_seen[:] = citation_ids
        return [(_encode_sse("citations", citation_ids, event.seq), False)]
    if event.type == TaskEventType.TASK_CANCELLED:
        frame = _encode_sse("status", {"status": "interrupted"}, event.seq)
        done = _encode_sse("done", {"status": "interrupted"}, event.seq)
        return [(frame, False), (done, True)]
    if event.type == TaskEventType.TASK_FAILED:
        payload = event.payload
        envelope = ErrorEnvelope(
            code=ErrorCode.UPSTREAM_ERROR,
            message=str(payload.get("message") or "Chat answer generation failed"),
            request_id=str(payload.get("request_id") or task_id),
            details={"type": payload.get("error_code") or "TaskFailed"},
        ).model_dump(mode="json")
        return [(_encode_sse("error", envelope, event.seq), True)]
    if event.type == TaskEventType.TASK_COMPLETED:
        status_value = "done" if citations_seen else "unsubstantiated"
        status_frame = _encode_sse("status", {"status": status_value}, event.seq)
        done_frame = _encode_sse("done", {"status": status_value}, event.seq)
        return [(status_frame, False), (done_frame, True)]
    return []


def _encode_sse(event: str, payload: object, seq: int) -> bytes:
    return f"id: {seq}\n".encode() + encode_event(event, payload)


def _payload_str(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _payload_string_list(payload: dict[str, object], key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    items: list[object] = cast("list[object]", value)
    return [item for item in items if isinstance(item, str)]


def _payload_evidence(payload: dict[str, object]) -> list[dict[str, object]]:
    value = payload.get("evidence")
    if not isinstance(value, list):
        return []
    items: list[object] = cast("list[object]", value)
    evidence: list[dict[str, object]] = []
    for item in items:
        if isinstance(item, Mapping):
            mapped = cast("Mapping[object, object]", item)
            evidence.append({str(key): item_value for key, item_value in mapped.items()})
    return evidence


def _chat_task_payload(
    *,
    conversation_id: str,
    question: str,
    context: ChatQuestionContext | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "conversation_id": conversation_id,
        "question": question,
    }
    if context is not None:
        payload["context"] = context.model_dump(mode="json", by_alias=True)
    return payload


def _session_response(conversation: Conversation, turns: tuple[Turn, ...]) -> ChatSessionResponse:
    return ChatSessionResponse(
        sessionId=conversation.conversation_id,
        title=conversation.title or "New chat",
        createdAtLabel=_format_datetime_label(conversation.created_at),
        messages=[_message_from_turn(turn) for turn in turns],
        evidence=_evidence_from_turns(turns),
    )


def _message_from_turn(turn: Turn) -> ChatMessage:
    role = turn.role
    if role == "user":
        return ChatMessage(
            id=turn.turn_id,
            role="user",
            text=turn.content,
        )
    citation_ids = [citation.chunk_id for citation in turn.citations]
    return ChatMessage(
        id=turn.turn_id,
        role="assistant",
        text=turn.content,
        status="done" if citation_ids else "unsubstantiated",
        citations=citation_ids,
    )


def _evidence_from_turns(turns: tuple[Turn, ...]) -> list[ChatEvidence]:
    seen: set[str] = set()
    evidence: list[ChatEvidence] = []
    for turn in turns:
        for citation in turn.citations:
            chunk_id = citation.chunk_id
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            evidence.append(_evidence_from_citation(citation, len(evidence) + 1))
    return evidence


def _evidence_from_citation(citation: Citation, index: int) -> ChatEvidence:
    page = citation.page
    meta = f"p.{page}" if page is not None else "Page unknown"
    return ChatEvidence(
        id=citation.chunk_id,
        label=f"[{index}]",
        type="chunk",
        title=citation.doc_id,
        meta=meta,
        score="cited",
        snippet=citation.snippet,
    )


def _title_from_question(question: str) -> str:
    text = question.strip()
    if len(text) <= 48:
        return text or "New chat"
    return f"{text[:45].rstrip()}..."


def _format_datetime_label(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


async def clear_chat_streams_for_testing() -> None:
    """Compatibility test hook for older process-local chat tests."""
