"""Integration tests for the frontend `/api/libraries/*/chat` adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import FilesystemLibraryRepository, make_library
from apps.api.deps import get_container
from apps.api.main import app
from apps.api.routes.frontend_chat import clear_chat_streams_for_testing
from packages.context.budget import CharCountTokenCounter
from packages.context.compactor import TurnCompactor
from packages.context.conversation_repo import SqliteConversationRepo
from packages.context.memory import ResearchMemory, SqliteMemoryStore
from packages.context.prompt_composer import PromptComposer
from packages.context.protocols import ContextBudget
from packages.context.service import ContextService
from packages.core.config import Settings
from packages.llm.protocols import LLMResponse
from packages.orchestration.protocols import AnsweredQuery, Citation, TokenUsage


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised here."""


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


class _FakeQATask:
    async def answer(self, library_id: str, question: str) -> AnsweredQuery:
        return AnsweredQuery(
            library_id=library_id,
            question=question,
            answer="GraphRAG combines graph retrieval with grounded synthesis [chunk-1].",
            citations=(
                Citation(
                    chunk_id="chunk-1",
                    doc_id="2210.03629",
                    page=2,
                    snippet="Graph retrieval grounds the final synthesis.",
                ),
            ),
            model="fake-chat",
            tokens=TokenUsage(input_tokens=12, output_tokens=8, cost_usd=0.001),
            duration_ms=42,
        )


class _NoEvidenceQATask:
    async def answer(self, library_id: str, question: str) -> AnsweredQuery:
        return AnsweredQuery(
            library_id=library_id,
            question=question,
            answer="I could not find any relevant evidence in this library.",
        )


class _FailingQATask:
    async def answer(self, library_id: str, question: str) -> AnsweredQuery:
        _ = library_id, question
        raise RuntimeError("llm unavailable")


def _build_container(tmp_path: Path, *, qa_task: object | None = None) -> AppContainer:
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
        qa_task=qa_task or _FakeQATask(),  # type: ignore[arg-type]
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
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    container = _build_container(tmp_path)
    await container.library_repo.create(make_library(library_id="chat-lib", name="Chat Lib"))
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()
    await clear_chat_streams_for_testing()


async def test_get_chat_session_returns_empty_frontend_shape(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/chat-lib/chat/session")

    assert res.status_code == 200
    body = res.json()
    assert body["sessionId"]
    assert body["title"] == "New chat"
    assert body["createdAtLabel"]
    assert body["messages"] == []
    assert body["evidence"] == []


async def test_create_question_returns_placeholders_and_streams_real_answer(
    client: AsyncClient,
) -> None:
    create = await client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={
            "question": "How does GraphRAG answer?",
            "context": {"evidenceIds": ["chunk-1"], "entityIds": ["method:graphrag"]},
        },
    )

    assert create.status_code == 202
    body = create.json()
    assert body["taskId"].startswith("chat-")
    assert body["streamUrl"] == f"/api/libraries/chat-lib/chat/questions/{body['taskId']}/events"
    assert body["userMessage"]["role"] == "user"
    assert body["userMessage"]["text"] == "How does GraphRAG answer?"
    assert body["assistantMessage"] == {
        "id": body["assistantMessage"]["id"],
        "role": "assistant",
        "text": "",
        "status": "streaming",
        "citations": [],
    }
    assert body["evidence"] == []

    stream = await client.get(body["streamUrl"])

    assert stream.status_code == 200
    payload = stream.text
    assert "event: token" in payload
    assert '"token": "GraphRAG combines graph retrieval with grounded "' in payload
    assert '"token": "synthesis [chunk-1]."' in payload
    assert "event: evidence" in payload
    assert '"id": "chunk-1"' in payload
    assert "event: citations" in payload
    assert '"chunk-1"' in payload
    assert "event: status" in payload
    assert '"status": "done"' in payload
    assert "event: done" in payload

    session = await client.get("/api/libraries/chat-lib/chat/session")
    assert session.status_code == 200
    messages = session.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["status"] == "done"
    assert messages[1]["citations"] == ["chunk-1"]


async def test_create_question_whitespace_returns_validation_envelope(client: AsyncClient) -> None:
    res = await client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={"question": "   "},
    )

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "question must not be empty"


async def test_create_question_invalid_session_uses_not_found(client: AsyncClient) -> None:
    res = await client.post(
        "/api/libraries/chat-lib/chat/questions",
        json={"question": "What changed?", "sessionId": "missing-session"},
    )

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "Chat session not found: missing-session"


async def test_chat_missing_library_uses_library_error(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/missing-lib/chat/session")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["details"] == {"library_id": "missing-lib"}


async def test_stream_missing_task_uses_not_found(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/chat-lib/chat/questions/missing-task/events")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert "missing-task" in body["message"]


async def test_no_evidence_answer_streams_unsubstantiated_status(tmp_path: Path) -> None:
    container = _build_container(tmp_path, qa_task=_NoEvidenceQATask())
    await container.library_repo.create(make_library(library_id="chat-lib", name="Chat Lib"))
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        create = await instance.post(
            "/api/libraries/chat-lib/chat/questions",
            json={"question": "What evidence exists?"},
        )
        stream = await instance.get(create.json()["streamUrl"])
    app.dependency_overrides.clear()
    await clear_chat_streams_for_testing()

    assert create.status_code == 202
    assert stream.status_code == 200
    assert "event: citations" in stream.text
    assert "event: status" in stream.text
    assert '"status": "unsubstantiated"' in stream.text


async def test_upstream_failure_streams_error_event(tmp_path: Path) -> None:
    container = _build_container(tmp_path, qa_task=_FailingQATask())
    await container.library_repo.create(make_library(library_id="chat-lib", name="Chat Lib"))
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        create = await instance.post(
            "/api/libraries/chat-lib/chat/questions",
            json={"question": "Will this fail?"},
        )
        stream = await instance.get(create.json()["streamUrl"])
    app.dependency_overrides.clear()
    await clear_chat_streams_for_testing()

    assert create.status_code == 202
    assert stream.status_code == 200
    assert "event: error" in stream.text
    assert '"code": "UPSTREAM_ERROR"' in stream.text
    assert '"type": "RuntimeError"' in stream.text
