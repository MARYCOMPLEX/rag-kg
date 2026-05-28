"""Integration tests for the frontend durable chat API adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import FilesystemLibraryRepository, make_library
from apps.api._task_deps import reset_task_bundle, set_task_bundle_for_testing
from apps.api.deps import get_container
from apps.api.main import app
from packages.context.budget import CharCountTokenCounter
from packages.context.compactor import TurnCompactor
from packages.context.conversation_repo import SqliteConversationRepo
from packages.context.memory import ResearchMemory, SqliteMemoryStore
from packages.context.prompt_composer import PromptComposer
from packages.context.protocols import ContextBudget
from packages.context.service import ContextService
from packages.core.config import Settings
from packages.llm.protocols import LLMResponse
from packages.orchestration.errors import QueueFullError
from packages.orchestration.queue import (
    TaskEvent,
    TaskEventBus,
    TaskEventType,
    TaskHandle,
    TaskQueue,
    TaskSpec,
    TaskState,
)


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised here."""


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


class _FakeTaskQueue(TaskQueue):
    def __init__(self) -> None:
        self.enqueued: list[TaskSpec] = []
        self.states: dict[tuple[str, str], TaskState] = {}
        self.fail_enqueue = False

    async def enqueue(self, library_id: str, spec: TaskSpec) -> TaskHandle:
        if self.fail_enqueue:
            raise QueueFullError("Chat task queue unavailable")
        self.enqueued.append(spec)
        task_id = f"chat-task-{len(self.enqueued)}"
        now = datetime.now(UTC)
        self.states[(library_id, task_id)] = TaskState(
            library_id=library_id,
            task_id=task_id,
            task_type=spec.task_type,
            status="queued",
            progress=0.0,
            current_stage=None,
            enqueued_at=now,
            started_at=None,
            finished_at=None,
            error=None,
            result_pointer=None,
            cost_usd=0.0,
        )
        return TaskHandle(library_id=library_id, task_id=task_id, enqueued_at=now)

    async def get(self, library_id: str, task_id: str) -> TaskState | None:
        return self.states.get((library_id, task_id))

    async def cancel(self, library_id: str, task_id: str) -> bool:
        _ = library_id, task_id
        return False

    async def list_active(self, library_id: str) -> tuple[TaskHandle, ...]:
        handles: list[TaskHandle] = []
        for state in self.states.values():
            if state.library_id == library_id and state.status in {"queued", "running"}:
                handles.append(
                    TaskHandle(
                        library_id=state.library_id,
                        task_id=state.task_id,
                        enqueued_at=state.enqueued_at,
                    )
                )
        return tuple(handles)


class _FakeTaskEventBus(TaskEventBus):
    def __init__(self) -> None:
        self.events: dict[tuple[str, str], list[TaskEvent]] = {}
        self.emitted: list[TaskEvent] = []

    async def emit(self, event: TaskEvent) -> None:
        self.emitted.append(event)

    def add(self, event: TaskEvent) -> None:
        self.events.setdefault((event.library_id, event.task_id), []).append(event)

    async def stream(
        self,
        library_id: str,
        task_id: str,
        *,
        since_seq: int | None = None,
    ) -> AsyncIterator[TaskEvent]:
        lower_bound = since_seq if since_seq is not None else -1
        for event in self.events.get((library_id, task_id), []):
            if event.seq > lower_bound:
                yield event


@dataclass(frozen=True)
class _Harness:
    client: AsyncClient
    queue: _FakeTaskQueue
    bus: _FakeTaskEventBus


def _build_container(tmp_path: Path) -> AppContainer:
    settings = Settings(data_dir=str(tmp_path / "data"))
    repo = FilesystemLibraryRepository(data_dir=tmp_path / "data")
    db_path = tmp_path / "context.sqlite"
    conversation_repo = SqliteConversationRepo(db_path)
    memory_store = SqliteMemoryStore(db_path)
    research_memory = ResearchMemory(store=memory_store, max_entries_in_prompt=5)
    context_service = ContextService(store=conversation_repo, memory_store=memory_store)
    counter = CharCountTokenCounter()
    budget = ContextBudget()
    return AppContainer(
        settings=settings,
        library_repo=repo,
        parser=_Sentinel(),
        chunker=_Sentinel(),
        embedder=_Sentinel(),
        raw_embedder=_Sentinel(),
        vector_index=_Sentinel(),
        bm25_index=_Sentinel(),
        graph_index=_Sentinel(),
        community_index=_Sentinel(),
        reranker=_Sentinel(),
        raw_llm=_Sentinel(),
        llm=_Sentinel(),
        planner=_Sentinel(),
        qa_task=_Sentinel(),
        review_task=_Sentinel(),
        reasoning_task=_Sentinel(),
        hypothesis_task=_Sentinel(),
        schema=None,
        extractor=None,
        linker=_Sentinel(),
        community_detector=_Sentinel(),
        community_summarizer=_Sentinel(),
        router=_Sentinel(),
        conversation_repo=conversation_repo,
        memory_store=memory_store,
        research_memory=research_memory,
        context_service=context_service,
        query_rewriter=_Sentinel(),
        prompt_composer=PromptComposer(counter=counter),
        turn_compactor=TurnCompactor(
            llm=_FakeLLM(),  # type: ignore[arg-type]
            counter=counter,
            budget=budget,
        ),
        context_budget=budget,
    )


@pytest.fixture
async def harness(tmp_path: Path) -> AsyncIterator[_Harness]:
    container = _build_container(tmp_path)
    await container.library_repo.create(make_library(library_id="chat-lib", name="Chat Lib"))
    queue = _FakeTaskQueue()
    bus = _FakeTaskEventBus()
    app.dependency_overrides[get_container] = lambda: container
    set_task_bundle_for_testing(queue, bus)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield _Harness(client=client, queue=queue, bus=bus)
    app.dependency_overrides.clear()
    await reset_task_bundle()


async def test_get_chat_session_returns_empty_frontend_shape(harness: _Harness) -> None:
    res = await harness.client.get("/api/libraries/chat-lib/chat/session")

    assert res.status_code == 200
    body = res.json()
    assert body["sessionId"]
    assert body["title"] == "New chat"
    assert body["createdAtLabel"]
    assert body["messages"] == []
    assert body["evidence"] == []


async def test_create_question_enqueues_durable_run_chat_task(harness: _Harness) -> None:
    res = await harness.client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={
            "question": "How does GraphRAG answer?",
            "context": {"evidenceIds": ["chunk-1"], "entityIds": ["method:graphrag"]},
        },
    )

    assert res.status_code == 202
    body = res.json()
    assert body["taskId"] == "chat-task-1"
    assert body["streamUrl"] == "/api/libraries/chat-lib/chat/questions/chat-task-1/events"
    assert body["userMessage"]["role"] == "user"
    assert body["userMessage"]["text"] == "How does GraphRAG answer?"
    assert body["assistantMessage"]["role"] == "assistant"
    assert body["assistantMessage"]["status"] == "streaming"
    assert body["assistantMessage"]["text"] == ""
    assert body["evidence"] == []

    assert len(harness.queue.enqueued) == 1
    spec = harness.queue.enqueued[0]
    assert spec.library_id == "chat-lib"
    assert spec.task_type == "run_chat"
    assert spec.input_payload["question"] == "How does GraphRAG answer?"
    assert isinstance(spec.input_payload["conversation_id"], str)
    assert spec.input_payload["context"] == {
        "evidenceIds": ["chunk-1"],
        "entityIds": ["method:graphrag"],
    }


async def test_stream_maps_durable_task_events_to_frontend_sse(harness: _Harness) -> None:
    await harness.client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={"question": "How does GraphRAG answer?"},
    )
    _add_event(harness.bus, "chat-lib", "chat-task-1", 0, TaskEventType.TASK_STARTED)
    _add_event(
        harness.bus,
        "chat-lib",
        "chat-task-1",
        1,
        TaskEventType.TOKEN,
        payload={"token": "GraphRAG combines graph retrieval "},
    )
    _add_event(
        harness.bus,
        "chat-lib",
        "chat-task-1",
        2,
        TaskEventType.TOKEN,
        payload={"token": "with grounded synthesis."},
    )
    _add_event(
        harness.bus,
        "chat-lib",
        "chat-task-1",
        3,
        TaskEventType.STAGE_COMPLETED,
        stage_name="evidence",
        payload={
            "evidence": [
                {
                    "id": "chunk-1",
                    "label": "[1]",
                    "type": "chunk",
                    "title": "2210.03629",
                    "meta": "p.2",
                    "score": "0.941",
                    "snippet": "Graph retrieval grounds the final synthesis.",
                }
            ]
        },
    )
    _add_event(
        harness.bus,
        "chat-lib",
        "chat-task-1",
        4,
        TaskEventType.CITATION_ADDED,
        payload={"citation_ids": ["chunk-1"]},
    )
    _add_event(harness.bus, "chat-lib", "chat-task-1", 5, TaskEventType.TASK_COMPLETED)

    stream = await harness.client.get("/api/libraries/chat-lib/chat/questions/chat-task-1/events")

    assert stream.status_code == 200
    payload = stream.text
    assert "event: status" in payload
    assert '"status": "streaming"' in payload
    assert "event: token" in payload
    assert '"token": "GraphRAG combines graph retrieval "' in payload
    assert '"token": "with grounded synthesis."' in payload
    assert "event: evidence" in payload
    assert '"id": "chunk-1"' in payload
    assert "event: citations" in payload
    assert '"chunk-1"' in payload
    assert '"status": "done"' in payload
    assert "event: done" in payload


async def test_stream_missing_task_uses_not_found(harness: _Harness) -> None:
    res = await harness.client.get("/api/libraries/chat-lib/chat/questions/missing-task/events")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["details"] == {"library_id": "chat-lib", "task_id": "missing-task"}


async def test_create_question_queue_unavailable_uses_upstream_error(
    harness: _Harness,
) -> None:
    harness.queue.fail_enqueue = True

    res = await harness.client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={"question": "Will this enqueue?"},
    )

    assert res.status_code == 503
    body = res.json()
    assert body["code"] == "UPSTREAM_ERROR"
    assert body["message"] == "Chat task queue unavailable"


async def test_create_question_whitespace_returns_validation_envelope(
    harness: _Harness,
) -> None:
    res = await harness.client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={"question": "   "},
    )

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "question must not be empty"


async def test_create_question_invalid_body_returns_validation_envelope(
    harness: _Harness,
) -> None:
    res = await harness.client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={"sessionId": "session-1"},
    )

    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"


async def test_chat_missing_library_uses_library_error(harness: _Harness) -> None:
    res = await harness.client.post(
        "/api/libraries/missing-lib/chat/questions",
        json={"question": "What changed?"},
    )

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["details"] == {"library_id": "missing-lib"}
    assert harness.queue.enqueued == []


async def test_create_question_invalid_session_uses_not_found(harness: _Harness) -> None:
    res = await harness.client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={"question": "What changed?", "sessionId": "missing-session"},
    )

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "Chat session not found: missing-session"
    assert harness.queue.enqueued == []


def _add_event(
    bus: _FakeTaskEventBus,
    library_id: str,
    task_id: str,
    seq: int,
    event_type: TaskEventType,
    *,
    stage_name: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    bus.add(
        TaskEvent(
            library_id=library_id,
            task_id=task_id,
            seq=seq,
            timestamp=datetime.now(UTC),
            type=event_type,
            stage_name=stage_name,
            payload=payload or {},
        )
    )
