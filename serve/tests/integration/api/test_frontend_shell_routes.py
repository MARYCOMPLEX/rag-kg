"""Integration tests for frontend command search and shell metadata adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import FilesystemLibraryRepository, make_library
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
from packages.ingestion.state import IngestRecord, IngestStateStore
from packages.llm.protocols import LLMResponse
from packages.orchestration.search import SearchHit


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised here."""


class _FakeBM25Index:
    async def search_documents(
        self,
        library_id: str,
        q: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        _ = q, limit
        return (
            SearchHit(
                type="document",
                id="doc-ready",
                title="GraphRAG Survey Notes",
                subtitle="paper.pdf",
                library_id=library_id,
                score=0.9,
            ),
        )


class _FakeGraphIndex:
    async def search_entities(
        self,
        library_id: str,
        q: str,
        *,
        limit: int,
    ) -> tuple[SearchHit, ...]:
        _ = q, limit
        return (
            SearchHit(
                type="entity",
                id="entity-graphrag",
                title="GraphRAG",
                subtitle="Method entity",
                library_id=library_id,
                score=0.8,
            ),
        )


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


def _build_container(tmp_path: Path) -> AppContainer:
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
        bm25_index=_FakeBM25Index(),  # type: ignore[arg-type]
        graph_index=_FakeGraphIndex(),  # type: ignore[arg-type]
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
    container = _build_container(tmp_path)
    await container.library_repo.create(
        make_library(
            library_id="rag-lib",
            name="RAG Library",
            description="GraphRAG papers",
            created_at=datetime(2026, 5, 27, tzinfo=UTC),
        )
    )
    await container.library_repo.create(
        make_library(library_id="kg-lib", name="KG Library", description="knowledge graph")
    )
    await container.context_service.open(
        library_id="rag-lib",
        autocreate_title="Recent GraphRAG chat",
    )
    store = IngestStateStore(Path(container.settings.ingest_state_dir) / "ingest.sqlite")
    try:
        store.put(
            IngestRecord(
                library_id="rag-lib",
                file_sha256="sha-ready",
                file_name="paper.pdf",
                doc_id="doc-ready",
                title="GraphRAG Survey Notes",
                status="done",
                chunks_created=7,
                chunks_upserted=7,
                last_error=None,
                created_at=datetime(2026, 5, 27, tzinfo=UTC).isoformat(),
                updated_at=datetime(2026, 5, 27, tzinfo=UTC).isoformat(),
            )
        )
    finally:
        store.close()
    return container


@pytest.fixture
async def client(test_container: AppContainer) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_container] = lambda: test_container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()


async def test_search_returns_frontend_command_shape(client: AsyncClient) -> None:
    res = await client.get(
        "/api/libraries/rag-lib/search",
        params={"q": "graphrag", "scope": "documents,entities,libraries", "limit": 5},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "graphrag"
    assert {item["type"] for item in body["results"]} == {"document", "entity", "library"}
    document = next(item for item in body["results"] if item["type"] == "document")
    assert document["screen"] == "docs"
    assert document["target"] == {"libraryId": "rag-lib", "documentId": "doc-ready"}
    entity = next(item for item in body["results"] if item["type"] == "entity")
    assert entity["screen"] == "graph"
    assert entity["target"] == {"libraryId": "rag-lib", "entityId": "entity-graphrag"}


async def test_search_returns_action_result_with_target(client: AsyncClient) -> None:
    res = await client.get(
        "/api/libraries/rag-lib/search",
        params={"q": "review", "scope": "actions"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["results"][0]["type"] == "action"
    assert body["results"][0]["screen"] == "review"
    assert body["results"][0]["target"] == {"libraryId": "rag-lib", "query": "review"}


async def test_search_blank_query_returns_empty_results(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/rag-lib/search")

    assert res.status_code == 200
    assert res.json() == {"query": "", "results": []}


async def test_search_invalid_scope_returns_400_envelope(client: AsyncClient) -> None:
    res = await client.get(
        "/api/libraries/rag-lib/search",
        params={"q": "graph", "scope": "documents,unknown"},
    )

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "Unsupported search scope" in body["message"]


async def test_shell_metadata_returns_recent_sessions_and_real_stats(
    client: AsyncClient,
) -> None:
    res = await client.get("/api/libraries/rag-lib/shell/metadata")

    assert res.status_code == 200
    body = res.json()
    assert body["recentSessions"][0]["title"] == "Recent GraphRAG chat"
    assert body["recentSessions"][0]["screen"] == "chat"
    assert body["recentSessions"][0]["target"]["libraryId"] == "rag-lib"
    assert body["libraryStats"] == [
        {"label": "Documents", "value": "1"},
        {"label": "Chunks", "value": "7"},
    ]


async def test_shell_metadata_missing_library_returns_404_envelope(
    client: AsyncClient,
) -> None:
    res = await client.get("/api/libraries/missing-lib/shell/metadata")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["details"] == {"library_id": "missing-lib"}
