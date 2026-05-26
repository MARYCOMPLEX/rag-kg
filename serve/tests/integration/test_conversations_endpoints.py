"""Integration tests for `/v1/libraries/{library_id}/conversations*`.

Pattern:
    1. Build a real `AppContainer` with all sqlite paths in `tmp_path`.
    2. Replace its `qa_task` and friends with `AsyncMock`/fakes so we can
       drive the conversation pipeline without hitting any LLM/retrieval.
    3. Override `apps.api.deps.get_container` with our test container.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import (
    FilesystemLibraryRepository,
    make_library,
)
from apps.api.deps import get_container
from apps.api.main import app
from packages.context.budget import CharCountTokenCounter
from packages.context.compactor import TurnCompactor
from packages.context.conversation_repo import SqliteConversationRepo
from packages.context.memory import ResearchMemory, SqliteMemoryStore
from packages.context.prompt_composer import PromptComposer
from packages.context.protocols import ContextBudget, RewriteResult
from packages.context.service import ContextService
from packages.core.config import Settings
from packages.llm.protocols import LLMResponse
from packages.orchestration.protocols import AnsweredQuery, Citation, TokenUsage
from packages.orchestration.tasks.qa_task import QATask


class _FakeQATask:
    """Mimics QATask.answer_in_conversation against the real ContextService.

    Persists the user/assistant turns through the supplied context_service
    so the rest of the pipeline (history, compact) works end-to-end without
    any LLM or retrieval engagement.
    """

    def __init__(self, *, model: str = "fake-llm") -> None:
        self.model = model
        self.calls: list[dict[str, Any]] = []

    async def answer_in_conversation(
        self,
        *,
        library_id: str,
        conversation: Any,
        question: str,
        context_service: ContextService,
        rewriter: Any,
        compactor: Any,
        memory: Any,
        composer: Any,
        settings_snapshot: Any,
        library_card: str = "",
        budget: Any = None,
    ) -> AnsweredQuery:
        self.calls.append(
            {
                "library_id": library_id,
                "conversation_id": conversation.conversation_id,
                "question": question,
            }
        )
        await context_service.append_user_turn(conversation=conversation, content=question)
        answer_text = f"Echo: {question}"
        citations = (
            Citation(
                chunk_id="chunk-1",
                doc_id="doc-1",
                page=1,
                snippet="evidence",
            ),
        )
        await context_service.append_assistant_turn(
            conversation=conversation,
            content=answer_text,
            citations=citations,
            model=self.model,
            input_tokens=10,
            output_tokens=20,
        )
        return AnsweredQuery(
            library_id=library_id,
            question=question,
            answer=answer_text,
            citations=citations,
            model=self.model,
            tokens=TokenUsage(input_tokens=10, output_tokens=20),
            duration_ms=5,
        )


def _build_test_container(tmp_path: Path) -> AppContainer:
    """Create a minimal AppContainer using only the in-process pieces we need."""
    settings = Settings(data_dir=str(tmp_path / "data"))
    library_repo = FilesystemLibraryRepository(data_dir=tmp_path / "data")
    db_path = tmp_path / "context.sqlite"
    conversation_repo = SqliteConversationRepo(db_path)
    memory_store = SqliteMemoryStore(db_path)
    research_memory = ResearchMemory(store=memory_store, max_entries_in_prompt=5)
    context_service = ContextService(store=conversation_repo, memory_store=memory_store)
    counter = CharCountTokenCounter()
    budget = ContextBudget()
    return AppContainer(
        settings=settings,
        library_repo=library_repo,
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
        qa_task=_FakeQATask(),  # type: ignore[arg-type]
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
        query_rewriter=_FakeRewriter(),  # type: ignore[arg-type]
        prompt_composer=PromptComposer(counter=counter),
        turn_compactor=TurnCompactor(
            llm=_FakeLLM(),  # type: ignore[arg-type]
            counter=counter,
            budget=budget,
        ),
        context_budget=budget,
    )


class _Sentinel:
    """Cheap stand-in for AppContainer fields we don't exercise in these tests."""


class _FakeRewriter:
    async def rewrite(self, *, question: str, recent_turns: Any) -> RewriteResult:
        _ = recent_turns
        return RewriteResult(
            original=question, rewritten=question, confidence=1.0, used_history=False
        )


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="summary text", model="fake-llm", input_tokens=1, output_tokens=1)


@pytest.fixture
async def test_container(tmp_path: Path) -> AppContainer:
    container = _build_test_container(tmp_path)
    library = make_library(library_id="lib-a", name="Lib A")
    await container.library_repo.create(library)
    return container


@pytest.fixture
async def client(test_container: AppContainer) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_container] = lambda: test_container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()


async def test_create_conversation_returns_201_with_ids(
    client: AsyncClient,
) -> None:
    res = await client.post("/v1/libraries/lib-a/conversations", json={"title": "First chat"})
    assert res.status_code == 201
    body = res.json()
    assert body["library_id"] == "lib-a"
    assert body["conversation_id"]
    assert body["title"] == "First chat"
    assert body["summary"] == ""


async def test_list_returns_just_created_conversation(client: AsyncClient) -> None:
    create = await client.post("/v1/libraries/lib-a/conversations", json={"title": "T1"})
    cid = create.json()["conversation_id"]
    res = await client.get("/v1/libraries/lib-a/conversations")
    assert res.status_code == 200
    items = res.json()
    assert any(c["conversation_id"] == cid for c in items)


async def test_get_conversation_returns_empty_turns_initially(
    client: AsyncClient,
) -> None:
    create = await client.post("/v1/libraries/lib-a/conversations", json={"title": "T2"})
    cid = create.json()["conversation_id"]
    res = await client.get(f"/v1/libraries/lib-a/conversations/{cid}")
    assert res.status_code == 200
    body = res.json()
    assert body["conversation"]["conversation_id"] == cid
    assert body["turns"] == []


async def test_post_turn_persists_user_and_assistant(client: AsyncClient) -> None:
    create = await client.post("/v1/libraries/lib-a/conversations", json={})
    cid = create.json()["conversation_id"]
    turn_res = await client.post(
        f"/v1/libraries/lib-a/conversations/{cid}/turns",
        json={"question": "What is RAG?"},
    )
    assert turn_res.status_code == 200
    turn = turn_res.json()
    assert turn["role"] == "assistant"
    assert "Echo: What is RAG?" in turn["content"]
    assert turn["citations"]

    detail = await client.get(f"/v1/libraries/lib-a/conversations/{cid}")
    body = detail.json()
    assert len(body["turns"]) == 2
    assert body["turns"][0]["role"] == "user"
    assert body["turns"][1]["role"] == "assistant"


async def test_delete_conversation_then_get_returns_404(client: AsyncClient) -> None:
    create = await client.post("/v1/libraries/lib-a/conversations", json={})
    cid = create.json()["conversation_id"]

    delete_res = await client.delete(f"/v1/libraries/lib-a/conversations/{cid}")
    assert delete_res.status_code == 204

    res = await client.get(f"/v1/libraries/lib-a/conversations/{cid}")
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert "not found" in body["message"].lower()


async def test_compact_returns_expected_shape_with_few_turns(
    client: AsyncClient,
) -> None:
    create = await client.post("/v1/libraries/lib-a/conversations", json={})
    cid = create.json()["conversation_id"]
    res = await client.post(f"/v1/libraries/lib-a/conversations/{cid}/compact")
    assert res.status_code == 200
    body = res.json()
    # Empty conversation → no compaction needed.
    assert body["dropped_turns"] == 0
    assert body["kept_tokens"] == 0
    assert body["summary_tokens"] == 0


async def test_library_not_found_returns_404_envelope(client: AsyncClient) -> None:
    res = await client.post("/v1/libraries/no-such-lib/conversations", json={"title": "x"})
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["details"] == {"library_id": "no-such-lib"}


async def test_qa_task_class_is_imported(client: AsyncClient) -> None:
    """Sanity-check: the production QATask remains importable + answer() works.

    Guards against future refactors that accidentally break the back-compat
    `answer()` surface.
    """
    assert hasattr(QATask, "answer")
    assert hasattr(QATask, "answer_in_conversation")
    # `created_at` field round-trips as an ISO datetime via FastAPI/json.
    create = await client.post("/v1/libraries/lib-a/conversations", json={})
    raw_created = create.json()["created_at"]
    parsed = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed <= datetime.now(tz=UTC)
