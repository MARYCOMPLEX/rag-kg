"""Integration tests for ``/v1/libraries/{lib}/qa/{answer_id}/feedback``.

The feedback endpoints are scoped per (Library, answer, user). The
fixture below injects a fake ``FeedbackStore`` so the route can be
exercised without Postgres.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import (
    FilesystemLibraryRepository,
    make_library,
)
from apps.api._eval_deps import reset_eval_bundle, set_eval_bundle_for_testing
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
from packages.orchestration.eval_models import AnswerFeedback


class _Sentinel:
    """Fill-in for AppContainer fields the feedback routes don't touch."""


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="x", model="fake", input_tokens=1, output_tokens=1)


class _FakeFeedbackStore:
    """In-memory FeedbackStore used to exercise the routes."""

    def __init__(self) -> None:
        # Keyed by (library_id, answer_id, user_id|"") so the spam-guard pair is honored.
        self.rows: dict[tuple[str, str, str], AnswerFeedback] = {}
        self.revoke_calls: list[tuple[str, str, str | None]] = []

    async def submit(self, feedback: AnswerFeedback) -> None:
        key = (feedback.library_id, feedback.answer_id, feedback.user_id or "")
        self.rows[key] = feedback

    async def revoke(
        self,
        library_id: str,
        answer_id: str,
        user_id: str | None,
    ) -> None:
        self.revoke_calls.append((library_id, answer_id, user_id))
        key = (library_id, answer_id, user_id or "")
        existing = self.rows.get(key)
        if existing is not None:
            self.rows[key] = existing.model_copy(
                update={"revoked_at": datetime.now(existing.created_at.tzinfo)}
            )


def _build_test_container(tmp_path: Path) -> AppContainer:
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
async def test_container(tmp_path: Path) -> AppContainer:
    container = _build_test_container(tmp_path)
    await container.library_repo.create(make_library(library_id="lib-a", name="Lib A"))
    return container


@pytest.fixture
async def store() -> AsyncIterator[_FakeFeedbackStore]:
    fake = _FakeFeedbackStore()
    set_eval_bundle_for_testing(feedback=fake)  # type: ignore[arg-type]
    try:
        yield fake
    finally:
        await reset_eval_bundle()


@pytest.fixture
async def client(
    test_container: AppContainer,
    store: _FakeFeedbackStore,
) -> AsyncIterator[AsyncClient]:
    _ = store
    app.dependency_overrides[get_container] = lambda: test_container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()


async def test_submit_feedback_returns_201_and_persists_row(
    client: AsyncClient, store: _FakeFeedbackStore
) -> None:
    res = await client.post(
        "/v1/libraries/lib-a/qa/ans-001/feedback",
        json={
            "useful": True,
            "citations_correct": True,
            "comment": "great answer",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["library_id"] == "lib-a"
    assert body["answer_id"] == "ans-001"
    assert body["useful"] is True
    assert body["citations_correct"] is True
    assert body["comment"] == "great answer"
    assert body["revoked_at"] is None
    # The store recorded one row keyed by (lib, answer, user_id="" for anon).
    assert len(store.rows) == 1


async def test_submit_feedback_is_idempotent_per_answer_user_pair(
    client: AsyncClient, store: _FakeFeedbackStore
) -> None:
    first = await client.post(
        "/v1/libraries/lib-a/qa/ans-002/feedback",
        json={"useful": True, "citations_correct": False},
    )
    assert first.status_code == 201
    second = await client.post(
        "/v1/libraries/lib-a/qa/ans-002/feedback",
        json={"useful": False, "citations_correct": False, "comment": "changed mind"},
    )
    assert second.status_code == 201
    # Idempotent: still exactly one row, with the latest verdict.
    assert len(store.rows) == 1
    only = next(iter(store.rows.values()))
    assert only.useful is False
    assert only.comment == "changed mind"


async def test_revoke_feedback_returns_204_and_calls_store(
    client: AsyncClient, store: _FakeFeedbackStore
) -> None:
    submit = await client.post(
        "/v1/libraries/lib-a/qa/ans-003/feedback",
        json={"useful": True, "citations_correct": True},
    )
    assert submit.status_code == 201
    res = await client.delete("/v1/libraries/lib-a/qa/ans-003/feedback")
    assert res.status_code == 204
    assert res.text == ""
    assert len(store.revoke_calls) == 1
    assert store.revoke_calls[0][:2] == ("lib-a", "ans-003")


async def test_submit_rejects_unknown_library(client: AsyncClient) -> None:
    res = await client.post(
        "/v1/libraries/no-such-lib/qa/ans-x/feedback",
        json={"useful": True, "citations_correct": True},
    )
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"


async def test_submit_rejects_extra_body_fields(client: AsyncClient) -> None:
    """``extra='forbid'`` means unknown fields are 422 validation errors."""
    res = await client.post(
        "/v1/libraries/lib-a/qa/ans-004/feedback",
        json={
            "useful": True,
            "citations_correct": True,
            "rogue_field": "should be rejected",
        },
    )
    assert res.status_code == 422
