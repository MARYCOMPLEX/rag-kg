"""Conversation + memory endpoints (M8.B1).

Surfaces:
  /v1/libraries/{library_id}/conversations            CRUD
  /v1/libraries/{library_id}/conversations/{cid}/...  detail / compact / turns
  /v1/libraries/{library_id}/memory*                  memory CRUD

Wire shape is snake_case throughout; the frontend's
`endpoints/conversations.ts` is responsible for any camelCase mapping.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from apps.api.sse import SSE_HEADERS, SSE_MEDIA_TYPE, encode_event
from packages.context.protocols import (
    Conversation,
    MemoryEntry,
    MemoryKind,
    Turn,
)
from packages.core.errors import LibraryNotFoundError
from packages.orchestration.protocols import AnsweredQuery, Citation
from packages.orchestration.tasks.qa_task import ContextRuntimeSettings

router = APIRouter(prefix="/v1/libraries", tags=["conversations"])

_DEFAULT_CONVERSATION_LIST_LIMIT = 50
_DEFAULT_MEMORY_LIST_LIMIT = 200
_SSE_TOKEN_CHUNK = 48
_SSE_TOKEN_DELAY_S = 0.02


# === Pydantic wire models ===================================================


class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    title: str = Field(default="", max_length=200)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    conversation_id: str
    title: str
    summary: str
    created_at: datetime
    updated_at: datetime


class TurnResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    conversation_id: str
    turn_id: str
    role: str
    content: str
    citations: list[dict[str, object]]
    rewritten_query: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    conversation: ConversationResponse
    turns: list[TurnResponse]


class TurnRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    question: str = Field(min_length=1, max_length=2000)


class CompactResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    summary_tokens: int
    kept_tokens: int
    dropped_turns: int


class MemoryEntryResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    library_id: str
    entry_id: str
    kind: str
    title: str
    content: str
    created_at: datetime
    updated_at: datetime


class MemoryCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: MemoryKind
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=8000)


class MemoryUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: MemoryKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=8000)


# === Helpers ================================================================


def _to_conv_response(conv: Conversation) -> ConversationResponse:
    return ConversationResponse(
        library_id=conv.library_id,
        conversation_id=conv.conversation_id,
        title=conv.title,
        summary=conv.summary,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


def _citation_to_dict(c: Citation) -> dict[str, object]:
    return {
        "chunk_id": c.chunk_id,
        "doc_id": c.doc_id,
        "page": c.page,
        "snippet": c.snippet,
    }


def _to_turn_response(turn: Turn) -> TurnResponse:
    return TurnResponse(
        conversation_id=turn.conversation_id,
        turn_id=turn.turn_id,
        role=turn.role,
        content=turn.content,
        citations=[_citation_to_dict(c) for c in turn.citations],
        rewritten_query=turn.rewritten_query,
        model=turn.model,
        input_tokens=turn.input_tokens,
        output_tokens=turn.output_tokens,
        created_at=turn.created_at,
    )


def _to_memory_response(entry: MemoryEntry) -> MemoryEntryResponse:
    return MemoryEntryResponse(
        library_id=entry.library_id,
        entry_id=entry.entry_id,
        kind=entry.kind,
        title=entry.title,
        content=entry.content,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


async def _load_conversation(
    container: AppContainer, library_id: str, conversation_id: str
) -> Conversation:
    conv = await container.conversation_repo.get_conversation(library_id, conversation_id)
    if conv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"conversation {conversation_id} not found in {library_id}",
        )
    return conv


def _settings_snapshot(container: AppContainer) -> ContextRuntimeSettings:
    s = container.settings
    return ContextRuntimeSettings(
        recent_turns_window=s.context_recent_turns_window,
        memory_max_entries_in_prompt=s.context_memory_max_entries_in_prompt,
        compact_summary_max_tokens=s.context_compact_summary_max_tokens,
        rewrite_enabled=s.rewrite_enabled,
    )


def _library_card_for(container: AppContainer, library_id: str) -> str:
    """Best-effort short library card; empty when the library is unreachable."""
    return f"library_id={library_id}"


# === Conversation endpoints =================================================


@router.post(
    "/{library_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    library_id: str,
    body: ConversationCreateRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> ConversationResponse:
    await _ensure_library(container, library_id)
    conv = await container.context_service.open(
        library_id=library_id,
        autocreate_title=body.title,
    )
    return _to_conv_response(conv)


@router.get(
    "/{library_id}/conversations",
    response_model=list[ConversationResponse],
)
async def list_conversations(
    library_id: str,
    limit: int = _DEFAULT_CONVERSATION_LIST_LIMIT,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> list[ConversationResponse]:
    await _ensure_library(container, library_id)
    convs = await container.context_service.list(library_id, limit=limit)
    return [_to_conv_response(c) for c in convs]


@router.get(
    "/{library_id}/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
async def get_conversation(
    library_id: str,
    conversation_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> ConversationDetailResponse:
    await _ensure_library(container, library_id)
    conv = await _load_conversation(container, library_id, conversation_id)
    turns = await container.context_service.history(conversation_id)
    return ConversationDetailResponse(
        conversation=_to_conv_response(conv),
        turns=[_to_turn_response(t) for t in turns],
    )


@router.delete(
    "/{library_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    library_id: str,
    conversation_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> None:
    await _ensure_library(container, library_id)
    # Verify existence so we surface a 404 envelope rather than silent no-op.
    await _load_conversation(container, library_id, conversation_id)
    await container.context_service.delete(library_id, conversation_id)


@router.post(
    "/{library_id}/conversations/{conversation_id}/compact",
    response_model=CompactResponse,
)
async def compact_conversation(
    library_id: str,
    conversation_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> CompactResponse:
    await _ensure_library(container, library_id)
    conv = await _load_conversation(container, library_id, conversation_id)
    turns = await container.context_service.history(conversation_id)
    result = await container.turn_compactor.fit_auto(conv.summary, turns)
    if result.summary != conv.summary:
        await container.context_service.update_summary(conversation=conv, summary=result.summary)
    return CompactResponse(
        summary_tokens=result.summary_tokens,
        kept_tokens=result.kept_tokens,
        dropped_turns=result.dropped_turns,
    )


@router.post(
    "/{library_id}/conversations/{conversation_id}/turns",
    response_model=TurnResponse,
)
async def append_turn(
    library_id: str,
    conversation_id: str,
    body: TurnRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> TurnResponse:
    await _ensure_library(container, library_id)
    conv = await _load_conversation(container, library_id, conversation_id)
    answered = await _run_conversation_turn(
        container=container,
        library_id=library_id,
        conversation=conv,
        question=body.question,
    )
    # The assistant turn was just persisted; fetch the freshest one so the
    # caller gets the canonical row (with assigned turn_id and timestamp).
    turns = await container.context_service.history(conversation_id)
    assistant = next(
        (t for t in reversed(turns) if t.role == "assistant"),
        None,
    )
    if assistant is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assistant turn was not persisted by the answer pipeline",
        )
    response = _to_turn_response(assistant)
    if not response.citations and answered.citations:
        response = response.model_copy(
            update={"citations": [_citation_to_dict(c) for c in answered.citations]}
        )
    return response


@router.get("/{library_id}/conversations/{conversation_id}/turns/stream")
async def stream_turn(
    library_id: str,
    conversation_id: str,
    request: Request,
    question: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    """SSE stream: meta → (rewritten?) → token → citations → done.

    Mirrors `qa_stream`'s client-side fan-out for now; each event is a
    JSON payload. The full conversation pipeline runs in the background
    and persists user + assistant turns just like the buffered variant.
    """
    await _ensure_library(container, library_id)
    if not question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="question must not be empty",
        )
    conv = await _load_conversation(container, library_id, conversation_id)
    return StreamingResponse(
        _stream_turn_events(
            container=container,
            request=request,
            library_id=library_id,
            conversation_id=conversation_id,
            conversation=conv,
            question=question,
        ),
        media_type=SSE_MEDIA_TYPE,
        headers=SSE_HEADERS,
    )


async def _stream_turn_events(
    *,
    container: AppContainer,
    request: Request,
    library_id: str,
    conversation_id: str,
    conversation: Conversation,
    question: str,
) -> AsyncIterator[bytes]:
    try:
        answered = await _run_conversation_turn(
            container=container,
            library_id=library_id,
            conversation=conversation,
            question=question,
        )
    except Exception as exc:
        yield encode_event(
            "error",
            {
                "code": "INTERNAL_ERROR",
                "message": str(exc) or exc.__class__.__name__,
            },
        )
        return

    yield encode_event(
        "meta",
        {
            "library_id": library_id,
            "conversation_id": conversation_id,
            "model": answered.model,
        },
    )
    rewritten = await _last_rewritten_query(container, conversation_id)
    if rewritten is not None and rewritten != question:
        yield encode_event("rewritten", {"text": rewritten})

    async for frame in _stream_answer_body(answered.answer, request):
        yield frame

    for frame in _done_events(answered):
        yield frame


def _done_events(answered: AnsweredQuery) -> tuple[bytes, bytes]:
    """Encode the trailing `citations` + `done` SSE frames."""
    citations = encode_event("citations", [_citation_to_dict(c) for c in answered.citations])
    done = encode_event(
        "done",
        {
            "duration_ms": answered.duration_ms,
            "model": answered.model,
            "input_tokens": answered.tokens.input_tokens,
            "output_tokens": answered.tokens.output_tokens,
        },
    )
    return citations, done


async def _stream_answer_body(text: str, request: Request) -> AsyncIterator[bytes]:
    """Chunk `text` into token events, honoring client disconnects."""
    for i in range(0, len(text), _SSE_TOKEN_CHUNK):
        if await request.is_disconnected():
            return
        yield encode_event("token", {"text": text[i : i + _SSE_TOKEN_CHUNK]})
        await asyncio.sleep(_SSE_TOKEN_DELAY_S)


async def _run_conversation_turn(
    *,
    container: AppContainer,
    library_id: str,
    conversation: Conversation,
    question: str,
) -> AnsweredQuery:
    """Invoke the conversation-aware QA pipeline with container deps."""
    return await container.qa_task.answer_in_conversation(
        library_id=library_id,
        conversation=conversation,
        question=question,
        context_service=container.context_service,
        rewriter=container.query_rewriter,
        compactor=container.turn_compactor,
        memory=container.research_memory,
        composer=container.prompt_composer,
        settings_snapshot=_settings_snapshot(container),
        library_card=_library_card_for(container, library_id),
        budget=container.context_budget,
    )


async def _last_rewritten_query(container: AppContainer, conversation_id: str) -> str | None:
    """Look up the most recent user turn's rewritten_query, if any."""
    turns = await container.context_service.history(conversation_id)
    for turn in reversed(turns):
        if turn.role == "user":
            return turn.rewritten_query
    return None


# === Memory endpoints =======================================================


@router.get(
    "/{library_id}/memory",
    response_model=list[MemoryEntryResponse],
)
async def list_memory(
    library_id: str,
    limit: int = _DEFAULT_MEMORY_LIST_LIMIT,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> list[MemoryEntryResponse]:
    await _ensure_library(container, library_id)
    entries = await container.memory_store.list_entries(library_id, limit=limit)
    return [_to_memory_response(e) for e in entries]


@router.post(
    "/{library_id}/memory",
    response_model=MemoryEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_memory(
    library_id: str,
    body: MemoryCreateRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> MemoryEntryResponse:
    await _ensure_library(container, library_id)
    entry = await container.research_memory.create(library_id, body.kind, body.title, body.content)
    return _to_memory_response(entry)


@router.patch(
    "/{library_id}/memory/{entry_id}",
    response_model=MemoryEntryResponse,
)
async def update_memory(
    library_id: str,
    entry_id: str,
    body: MemoryUpdateRequest,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> MemoryEntryResponse:
    await _ensure_library(container, library_id)
    updated = await container.research_memory.update(
        library_id,
        entry_id,
        title=body.title,
        content=body.content,
        kind=body.kind,
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"memory entry {entry_id} not found in {library_id}",
        )
    return _to_memory_response(updated)


@router.delete(
    "/{library_id}/memory/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_memory(
    library_id: str,
    entry_id: str,
    container: AppContainer = Depends(get_container),
    _principal: Principal = Depends(get_current_principal),
) -> None:
    await _ensure_library(container, library_id)
    await container.research_memory.delete(library_id, entry_id)


__all__ = ["router"]
