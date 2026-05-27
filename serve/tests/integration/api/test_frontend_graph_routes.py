"""Integration tests for frontend knowledge graph adapters."""

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
from packages.core.models import Entity, Triple
from packages.llm.protocols import LLMResponse


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised here."""


class _FakeGraphIndex:
    async def list_entities(self, library_id: str) -> list[Entity]:
        return [
            Entity(
                library_id=library_id,
                entity_id="method:graphrag",
                name="GraphRAG",
                aliases=("Graph RAG",),
                type="Method",
                description="Graph-augmented retrieval method.",
            ),
            Entity(
                library_id=library_id,
                entity_id="dataset:hotpotqa",
                name="HotpotQA",
                type="Dataset",
            ),
            Entity(
                library_id=library_id,
                entity_id="concept:community-summary",
                name="Community summary",
                type="Concept",
            ),
        ]

    async def list_all_triples(self, library_id: str) -> list[Triple]:
        return [
            Triple(
                library_id=library_id,
                head="method:graphrag",
                relation="evaluated_on",
                tail="dataset:hotpotqa",
                evidence=("doc-1::p1::0", "doc-2::p3::1"),
                confidence=0.92,
                source_model="fake",
            ),
            Triple(
                library_id=library_id,
                head="method:graphrag",
                relation="uses",
                tail="concept:community-summary",
                evidence=("doc-1::p2::0",),
                confidence=0.81,
                source_model="fake",
            ),
        ]


class _EmptyGraphIndex:
    async def list_entities(self, library_id: str) -> list[Entity]:
        _ = library_id
        return []

    async def list_all_triples(self, library_id: str) -> list[Triple]:
        _ = library_id
        return []


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


def _build_container(
    tmp_path: Path,
    *,
    graph_index: object | None = None,
) -> AppContainer:
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
        graph_index=graph_index or _FakeGraphIndex(),  # type: ignore[arg-type]
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
async def client(tmp_path: Path) -> AsyncIterator[AsyncClient]:
    container = _build_container(tmp_path)
    await container.library_repo.create(
        make_library(
            library_id="rag-lib",
            name="RAG Library",
            created_at=datetime(2026, 5, 27, tzinfo=UTC),
        )
    )
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()


async def test_graph_workspace_returns_filters_canvas_and_summary(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/rag-lib/graph")

    assert res.status_code == 200
    body = res.json()
    assert body["summary"] == {
        "entityCountLabel": "3 entities",
        "tripleCountLabel": "2 triples",
        "confidenceLabel": "Avg confidence 86%",
    }
    assert body["filters"]["minConfidence"] == 0.0
    assert {item["key"] for item in body["filters"]["entityTypes"]} == {
        "concept",
        "dataset",
        "method",
    }
    assert body["canvas"]["layout"] == "static"
    assert body["canvas"]["largeGraph"] is False
    assert {node["id"] for node in body["canvas"]["nodes"]} == {
        "method:graphrag",
        "dataset:hotpotqa",
        "concept:community-summary",
    }
    edge = body["canvas"]["edges"][0]
    assert edge["source"] == "method:graphrag"
    assert edge["target"] == "dataset:hotpotqa"
    assert edge["directed"] is True


async def test_graph_workspace_filters_entities_and_layout(client: AsyncClient) -> None:
    res = await client.get(
        "/api/libraries/rag-lib/graph",
        params={"entityTypes": "method,dataset", "minConfidence": 0.9, "layout": "force"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["canvas"]["layout"] == "force"
    assert {node["type"] for node in body["canvas"]["nodes"]} == {"method", "dataset"}
    assert len(body["canvas"]["edges"]) == 1
    filters = {item["key"]: item for item in body["filters"]["entityTypes"]}
    assert filters["concept"]["checked"] is False
    assert filters["method"]["checked"] is True


async def test_graph_workspace_allows_empty_graph(tmp_path: Path) -> None:
    container = _build_container(tmp_path, graph_index=_EmptyGraphIndex())
    await container.library_repo.create(make_library(library_id="empty-lib", name="Empty Lib"))
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        res = await instance.get("/api/libraries/empty-lib/graph")
    app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "filters": {"entityTypes": [], "minConfidence": 0.0},
        "canvas": {"nodes": [], "edges": [], "layout": "static", "largeGraph": False},
        "summary": {
            "entityCountLabel": "0 entities",
            "tripleCountLabel": "0 triples",
            "confidenceLabel": "No confidence data",
        },
    }


async def test_graph_workspace_invalid_type_filter_returns_400(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/rag-lib/graph", params={"entityTypes": "bad!"})

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Invalid entity type filter: bad!"


async def test_graph_workspace_invalid_layout_returns_400(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/rag-lib/graph", params={"layout": "circular"})

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Unsupported graph layout: circular"


async def test_graph_workspace_missing_library_returns_404(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/missing-lib/graph")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["details"] == {"library_id": "missing-lib"}


async def test_graph_entity_detail_returns_frontend_shape(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/rag-lib/graph/entities/method:graphrag")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "method:graphrag"
    assert body["label"] == "GraphRAG"
    assert body["kind"] == "Method"
    assert body["stableId"] == "method:graphrag"
    assert body["aliases"] == ["Graph RAG"]
    assert body["summary"] == "Graph-augmented retrieval method."
    assert body["degree"] == 2
    assert body["incoming"] == 0
    assert body["mentions"] == 3
    assert body["evidenceCount"] == 3
    assert body["mentionsTrend"] == {
        "points": [3],
        "startLabel": "Current",
        "endLabel": "Current",
    }
    assert body["coOccurring"] == [
        {"id": "dataset:hotpotqa", "name": "HotpotQA", "type": "dataset", "count": 1},
        {
            "id": "concept:community-summary",
            "name": "Community summary",
            "type": "concept",
            "count": 1,
        },
    ]


async def test_graph_entity_detail_missing_entity_returns_404(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/rag-lib/graph/entities/missing-entity")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "Graph entity not found: missing-entity"
