"""Integration tests for `GET /v1/search` (ADR-0023).

Pattern:
- Build a real `FilesystemLibraryRepository` so library-metadata search has
  rows to find.
- Stub the rest of the AppContainer fields (vector / bm25 / graph / llm
  etc.) — search degrades gracefully when those backends don't expose
  the optional `search_*` helpers.
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
from packages.core.config import Settings


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised in these tests."""


def _build_test_container(tmp_path: Path) -> AppContainer:
    settings = Settings(data_dir=str(tmp_path / "data"))
    library_repo = FilesystemLibraryRepository(data_dir=tmp_path / "data")
    fields: dict[str, Any] = {
        "settings": settings,
        "library_repo": library_repo,
        "parser": _Sentinel(),
        "chunker": _Sentinel(),
        "embedder": _Sentinel(),
        "raw_embedder": _Sentinel(),
        "vector_index": _Sentinel(),
        "bm25_index": _Sentinel(),
        "graph_index": _Sentinel(),
        "community_index": _Sentinel(),
        "reranker": _Sentinel(),
        "raw_llm": _Sentinel(),
        "llm": _Sentinel(),
        "planner": _Sentinel(),
        "qa_task": _Sentinel(),
        "review_task": _Sentinel(),
        "reasoning_task": _Sentinel(),
        "hypothesis_task": _Sentinel(),
        "schema": None,
        "extractor": None,
        "linker": _Sentinel(),
        "community_detector": _Sentinel(),
        "community_summarizer": _Sentinel(),
        "router": _Sentinel(),
        "conversation_repo": _Sentinel(),
        "memory_store": _Sentinel(),
        "research_memory": _Sentinel(),
        "context_service": _Sentinel(),
        "query_rewriter": _Sentinel(),
        "prompt_composer": _Sentinel(),
        "turn_compactor": _Sentinel(),
        "context_budget": _Sentinel(),
    }
    return AppContainer(**fields)  # type: ignore[arg-type]


@pytest.fixture
async def test_container(tmp_path: Path) -> AppContainer:
    container = _build_test_container(tmp_path)
    await container.library_repo.create(
        make_library(library_id="rag-lib", name="RAG Library", description="rag papers")
    )
    await container.library_repo.create(
        make_library(library_id="kg-lib", name="KG Library", description="kg studies")
    )
    return container


@pytest.fixture
async def client(test_container: AppContainer) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_container] = lambda: test_container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_rejects_short_query(client: AsyncClient) -> None:
    res = await client.get("/v1/search", params={"q": "a"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_search_returns_library_hit_for_metadata_match(
    client: AsyncClient,
) -> None:
    res = await client.get("/v1/search", params={"q": "rag", "types": "library"})
    assert res.status_code == 200
    body = res.json()
    types = {hit["type"] for hit in body["hits"]}
    assert types == {"library"}
    assert any(hit["id"] == "rag-lib" for hit in body["hits"])
    assert "library" in body["timing_ms"]


@pytest.mark.asyncio
async def test_search_returns_action_hits_when_library_id_present(
    client: AsyncClient,
) -> None:
    res = await client.get(
        "/v1/search",
        params={"q": "review", "library_id": "rag-lib", "types": "action,library"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["library_id"] == "rag-lib"
    types_seen = {h["type"] for h in body["hits"]}
    # Action paths should be present for `review`
    assert "action" in types_seen


@pytest.mark.asyncio
async def test_search_with_library_id_current_treated_as_global(
    client: AsyncClient,
) -> None:
    res = await client.get("/v1/search", params={"q": "rag", "library_id": "current"})
    assert res.status_code == 200
    body = res.json()
    # `current` is a UI affordance; backend resolves it to None.
    assert body["library_id"] is None


@pytest.mark.asyncio
async def test_search_returns_empty_for_nonsense_query(client: AsyncClient) -> None:
    res = await client.get("/v1/search", params={"q": "zxqvbnm-no-match"})
    assert res.status_code == 200
    body = res.json()
    assert body["hits"] == []


@pytest.mark.asyncio
async def test_search_respects_limit(client: AsyncClient) -> None:
    res = await client.get("/v1/search", params={"q": "library", "types": "library", "limit": 1})
    assert res.status_code == 200
    body = res.json()
    assert len(body["hits"]) <= 1
