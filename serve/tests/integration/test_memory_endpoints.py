"""Integration tests for `/v1/libraries/{library_id}/memory*`.

Reuses the test-container pattern from `test_conversations_endpoints.py`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
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
from packages.context.protocols import ContextBudget
from packages.context.service import ContextService
from packages.core.config import Settings
from packages.llm.protocols import LLMResponse


class _Sentinel:
    """Stand-in for AppContainer fields the memory routes don't touch."""


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="x", model="fake", input_tokens=1, output_tokens=1)


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
    await container.library_repo.create(make_library(library_id="lib-a", name="A"))
    await container.library_repo.create(make_library(library_id="lib-b", name="B"))
    return container


@pytest.fixture
async def client(test_container: AppContainer) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_container] = lambda: test_container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()


async def test_get_empty_returns_empty_list(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/lib-a/memory")
    assert res.status_code == 200
    assert res.json() == []


async def test_post_then_get_lists_entry(client: AsyncClient) -> None:
    create = await client.post(
        "/v1/libraries/lib-a/memory",
        json={
            "kind": "user",
            "title": "Tone",
            "content": "Explain like a CS PhD",
        },
    )
    assert create.status_code == 201
    body = create.json()
    assert body["library_id"] == "lib-a"
    assert body["kind"] == "user"
    assert body["title"] == "Tone"
    assert body["entry_id"]

    res = await client.get("/v1/libraries/lib-a/memory")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["entry_id"] == body["entry_id"]


async def test_patch_partial_update_reflected_in_get(client: AsyncClient) -> None:
    create = await client.post(
        "/v1/libraries/lib-a/memory",
        json={"kind": "feedback", "title": "Cite", "content": "Cite originals"},
    )
    entry_id = create.json()["entry_id"]

    patch = await client.patch(
        f"/v1/libraries/lib-a/memory/{entry_id}",
        json={"content": "Always cite originals."},
    )
    assert patch.status_code == 200
    assert patch.json()["content"] == "Always cite originals."
    assert patch.json()["title"] == "Cite"  # unchanged

    listed = await client.get("/v1/libraries/lib-a/memory")
    assert listed.json()[0]["content"] == "Always cite originals."


async def test_delete_removes_entry(client: AsyncClient) -> None:
    create = await client.post(
        "/v1/libraries/lib-a/memory",
        json={"kind": "user", "title": "T", "content": "C"},
    )
    entry_id = create.json()["entry_id"]

    delete = await client.delete(f"/v1/libraries/lib-a/memory/{entry_id}")
    assert delete.status_code == 204

    after = await client.get("/v1/libraries/lib-a/memory")
    assert after.json() == []


async def test_cross_library_isolation(client: AsyncClient) -> None:
    await client.post(
        "/v1/libraries/lib-a/memory",
        json={"kind": "user", "title": "A entry", "content": "A only"},
    )
    await client.post(
        "/v1/libraries/lib-b/memory",
        json={"kind": "user", "title": "B entry", "content": "B only"},
    )

    a_items = (await client.get("/v1/libraries/lib-a/memory")).json()
    b_items = (await client.get("/v1/libraries/lib-b/memory")).json()
    assert len(a_items) == 1
    assert len(b_items) == 1
    assert a_items[0]["title"] == "A entry"
    assert b_items[0]["title"] == "B entry"
    assert a_items[0]["entry_id"] != b_items[0]["entry_id"]


async def test_patch_missing_returns_404(client: AsyncClient) -> None:
    res = await client.patch("/v1/libraries/lib-a/memory/no-such-id", json={"title": "x"})
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"


async def test_library_not_found_for_memory_returns_404_envelope(
    client: AsyncClient,
) -> None:
    res = await client.get("/v1/libraries/no-such-lib/memory")
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
