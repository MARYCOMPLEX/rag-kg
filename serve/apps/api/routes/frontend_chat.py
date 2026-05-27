"""Frontend `/api` chat adapter.

This route keeps the frontend-facing ChatView contract separate from the
existing `/v1/libraries/*/conversations` surfaces. The current backend does
not have a durable chat task type registered with Arq, so question streams are
process-local SSE streams backed by the real QA task output.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, encode_event
from packages.context.protocols import Conversation, Turn
from packages.core.errors import LibraryNotFoundError
from packages.orchestration.errors import TaskNotFoundError
from packages.orchestration.protocols import AnsweredQuery, Citation

router = APIRouter(prefix="/api/libraries/{library_id}/chat", tags=["libraries"])

ChatRole = Literal["user", "assistant"]
ChatMessageStatus = Literal["idle", "streaming", "done", "interrupted", "unsubstantiated"]
_TOKEN_CHUNK_SIZE = 48
_TOKEN_DELAY_S = 0.02
_STREAM_HEARTBEAT_S = 15.0
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


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


def _empty_stream_events() -> list[tuple[str, object]]:
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


@dataclass(slots=True)
class _StreamRecord:
    library_id: str
    session_id: str
    task_id: str
    assistant_message_id: str
    events: list[tuple[str, object]] = field(default_factory=_empty_stream_events)
    done: bool = False
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)

    async def add(self, event: str, payload: object, *, terminal: bool = False) -> None:
        async with self.condition:
            self.events.append((event, payload))
            if terminal:
                self.done = True
            self.condition.notify_all()


_STREAMS: dict[str, _StreamRecord] = {}


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


@router.get(
    "/session",
    response_model=ChatSessionResponse,
    response_model_by_alias=True,
)
async def get_current_chat_session(
    library_id: str,
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
    library_id: str,
    body: ChatQuestionRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> ChatQuestionResponse:
    await _ensure_library(container, library_id)
    question = body.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question must not be empty",
        )
    conversation = await _open_or_create_conversation(container, library_id, body, question)
    user_turn = await container.context_service.append_user_turn(
        conversation=conversation,
        content=question,
    )

    task_id = _new_id("chat")
    assistant_message_id = _new_id("assistant")
    record = _StreamRecord(
        library_id=library_id,
        session_id=conversation.conversation_id,
        task_id=task_id,
        assistant_message_id=assistant_message_id,
    )
    _STREAMS[task_id] = record
    background = asyncio.create_task(
        _run_answer_task(
            container=container,
            record=record,
            question=question,
            conversation=conversation,
        )
    )
    _BACKGROUND_TASKS.add(background)
    background.add_done_callback(_BACKGROUND_TASKS.discard)

    return ChatQuestionResponse(
        taskId=task_id,
        streamUrl=f"/api/libraries/{library_id}/chat/questions/{task_id}/events",
        userMessage=ChatMessage(id=user_turn.turn_id, role="user", text=question),
        assistantMessage=ChatMessage(
            id=assistant_message_id,
            role="assistant",
            text="",
            status="streaming",
            citations=[],
        ),
        evidence=[],
    )


@router.get("/questions/{task_id}/events")
async def stream_chat_question_events(
    library_id: str,
    task_id: str,
    request: Request,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    await _ensure_library(container, library_id)
    record = _STREAMS.get(task_id)
    if record is None or record.library_id != library_id:
        raise TaskNotFoundError(library_id, task_id)
    return StreamingResponse(
        _stream_events(request, record),
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


async def _run_answer_task(
    *,
    container: AppContainer,
    record: _StreamRecord,
    question: str,
    conversation: Conversation,
) -> None:
    try:
        answered = await container.qa_task.answer(record.library_id, question)
    except Exception as exc:
        await record.add(
            "error",
            {
                "code": "UPSTREAM_ERROR",
                "message": "Chat answer generation failed",
                "request_id": record.task_id,
                "details": {"type": type(exc).__name__},
            },
            terminal=True,
        )
        return

    for chunk in _chunk_text(answered.answer):
        await record.add("token", {"token": chunk})
        await asyncio.sleep(_TOKEN_DELAY_S)

    evidence = _evidence_from_answer(answered)
    if evidence:
        await record.add("evidence", [item.model_dump() for item in evidence])
    citation_ids = [item.id for item in evidence]
    await record.add("citations", citation_ids)
    final_status: ChatMessageStatus = "done" if citation_ids else "unsubstantiated"
    await record.add("status", {"status": final_status})
    try:
        await container.context_service.append_assistant_turn(
            conversation=conversation,
            content=answered.answer,
            citations=answered.citations,
            model=answered.model,
            input_tokens=answered.tokens.input_tokens,
            output_tokens=answered.tokens.output_tokens,
        )
    except Exception as exc:
        await record.add(
            "error",
            {
                "code": "INTERNAL_ERROR",
                "message": "Chat answer persistence failed",
                "request_id": record.task_id,
                "details": {"type": type(exc).__name__},
            },
            terminal=True,
        )
        return
    await record.add("done", {"status": final_status}, terminal=True)


async def _stream_events(request: Request, record: _StreamRecord) -> AsyncIterator[bytes]:
    cursor = 0
    while True:
        if await request.is_disconnected():
            return
        frame: bytes | None = None
        async with record.condition:
            while cursor >= len(record.events) and not record.done:
                try:
                    await asyncio.wait_for(record.condition.wait(), timeout=_STREAM_HEARTBEAT_S)
                except TimeoutError:
                    break
            if cursor >= len(record.events):
                if record.done:
                    return
                frame = b": keep-alive\n\n"
            else:
                event, payload = record.events[cursor]
                cursor += 1
                frame = encode_event(event, payload)
        yield frame


def _session_response(conversation: Conversation, turns: tuple[Turn, ...]) -> ChatSessionResponse:
    return ChatSessionResponse(
        sessionId=conversation.conversation_id,
        title=conversation.title or "New chat",
        createdAtLabel=_format_datetime_label(conversation.created_at),
        messages=[_message_from_turn(turn) for turn in turns],
        evidence=_evidence_from_turns(turns),
    )


def _message_from_turn(turn: Turn) -> ChatMessage:
    if turn.role == "user":
        return ChatMessage(id=turn.turn_id, role="user", text=turn.content)
    citation_ids = [citation.chunk_id for citation in turn.citations]
    return ChatMessage(
        id=turn.turn_id,
        role="assistant",
        text=turn.content,
        status=("done" if citation_ids else "unsubstantiated"),
        citations=citation_ids,
    )


def _evidence_from_turns(turns: tuple[Turn, ...]) -> list[ChatEvidence]:
    seen: set[str] = set()
    evidence: list[ChatEvidence] = []
    for turn in turns:
        for citation in turn.citations:
            if citation.chunk_id in seen:
                continue
            seen.add(citation.chunk_id)
            evidence.append(_evidence_from_citation(citation, len(evidence) + 1))
    return evidence


def _evidence_from_answer(answered: AnsweredQuery) -> list[ChatEvidence]:
    return [
        _evidence_from_citation(citation, index)
        for index, citation in enumerate(answered.citations, start=1)
    ]


def _evidence_from_citation(citation: Citation, index: int) -> ChatEvidence:
    page = f"p.{citation.page}" if citation.page is not None else "Page unknown"
    return ChatEvidence(
        id=citation.chunk_id,
        label=f"[{index}]",
        type="chunk",
        title=citation.doc_id,
        meta=page,
        score="cited",
        snippet=citation.snippet,
    )


def _chunk_text(text: str) -> list[str]:
    if not text:
        return []
    return [
        text[index : index + _TOKEN_CHUNK_SIZE] for index in range(0, len(text), _TOKEN_CHUNK_SIZE)
    ]


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _title_from_question(question: str) -> str:
    compact = " ".join(question.split())
    return compact[:80] if compact else "New chat"


def _format_datetime_label(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


async def clear_chat_streams_for_testing() -> None:
    for task in tuple(_BACKGROUND_TASKS):
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    _BACKGROUND_TASKS.clear()
    _STREAMS.clear()


__all__ = ["clear_chat_streams_for_testing", "router"]
