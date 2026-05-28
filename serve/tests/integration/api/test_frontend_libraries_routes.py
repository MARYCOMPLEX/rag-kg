"""Integration tests for the frontend `/api/libraries` adapter."""

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
from packages.llm.protocols import LLMResponse


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised here."""


class _FakeVectorIndex:
    def __init__(self) -> None:
        self.init_calls: list[str] = []

    async def init_library(self, library_id: str) -> None:
        self.init_calls.append(library_id)

    async def purge_library(self, library_id: str) -> None:
        _ = library_id


class _FailingVectorIndex(_FakeVectorIndex):
    async def init_library(self, library_id: str) -> None:
        _ = library_id
        raise RuntimeError("qdrant unavailable")


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


class _BrokenLibraryRepository:
    async def list_all(self) -> list[object]:
        raise RuntimeError("repository unavailable")

    async def create(self, library: object) -> None:
        _ = library
        raise RuntimeError("repository unavailable")

    async def get(self, library_id: str) -> object | None:
        _ = library_id
        return None

    async def delete(self, library_id: str) -> None:
        _ = library_id

    async def exists(self, library_id: str) -> bool:
        _ = library_id
        return False


def _build_container(
    tmp_path: Path,
    *,
    library_repo: object | None = None,
    vector_index: _FakeVectorIndex | None = None,
) -> AppContainer:
    settings = Settings(data_dir=str(tmp_path / "data"))
    repo = library_repo or FilesystemLibraryRepository(data_dir=tmp_path / "data")
    db_path = tmp_path / "context.sqlite"
    conversation_repo = SqliteConversationRepo(db_path)
    memory_store = SqliteMemoryStore(db_path)
    research_memory = ResearchMemory(store=memory_store, max_entries_in_prompt=5)
    context_service = ContextService(store=conversation_repo, memory_store=memory_store)
    counter = CharCountTokenCounter()
    budget = ContextBudget()
    fake_vector = vector_index or _FakeVectorIndex()
    return AppContainer(
        settings=settings,
        library_repo=repo,  # type: ignore[arg-type]
        parser=_Sentinel(),
        chunker=_Sentinel(),
        embedder=_Sentinel(),
        raw_embedder=_Sentinel(),
        vector_index=fake_vector,  # type: ignore[arg-type]
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
async def setup(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, AppContainer, _FakeVectorIndex]]:
    vector_index = _FakeVectorIndex()
    container = _build_container(tmp_path, vector_index=vector_index)
    await container.library_repo.create(
        make_library(
            library_id="alpha-lib",
            name="Alpha Library",
            description="Seeded",
            created_at=datetime(2026, 5, 27, tzinfo=UTC),
            language="en",
        )
    )
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, container, vector_index
    app.dependency_overrides.clear()


async def test_get_libraries_returns_frontend_summary_shape(
    setup: tuple[AsyncClient, AppContainer, _FakeVectorIndex],
) -> None:
    client, _container, _vector = setup

    res = await client.get("/api/libraries")

    assert res.status_code == 200
    body = res.json()
    assert body == [
        {
            "id": "alpha-lib",
            "name": "Alpha Library",
            "documentCountLabel": "0 documents",
            "chunkCountLabel": "0 chunks",
            "entityCountLabel": "0 entities",
            "activityLabel": "Created 2026-05-27",
            "statusLabel": "Healthy",
            "status": "healthy",
            "accent": body[0]["accent"],
        }
    ]
    assert body[0]["accent"] in {"concept", "method", "dataset", "citation", "author"}


async def test_libraries_allows_vite_dev_origin(
    setup: tuple[AsyncClient, AppContainer, _FakeVectorIndex],
) -> None:
    client, _container, _vector = setup

    res = await client.options(
        "/api/libraries",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_libraries_allows_vite_fallback_dev_origin(
    setup: tuple[AsyncClient, AppContainer, _FakeVectorIndex],
) -> None:
    client, _container, _vector = setup

    res = await client.options(
        "/api/libraries",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:5174"


async def test_post_libraries_creates_library_and_redirect(
    setup: tuple[AsyncClient, AppContainer, _FakeVectorIndex],
) -> None:
    client, container, vector = setup

    res = await client.post(
        "/api/libraries",
        json={
            "name": "New Library",
            "slug": "new-lib",
            "description": "Created from frontend",
            "language": "multi",
            "template": "blank",
        },
    )

    assert res.status_code == 201
    body = res.json()
    assert body["library"]["id"] == "new-lib"
    assert body["library"]["name"] == "New Library"
    assert body["library"]["documentCountLabel"] == "0 documents"
    assert body["library"]["status"] == "healthy"
    assert body["redirectTo"] == "/libraries/new-lib/docs?onboarding=1"
    assert vector.init_calls == ["new-lib"]
    stored = await container.library_repo.get("new-lib")
    assert stored is not None
    assert stored.language == "mixed"


async def test_post_libraries_succeeds_when_vector_init_is_unavailable(tmp_path: Path) -> None:
    container = _build_container(tmp_path, vector_index=_FailingVectorIndex())
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/libraries",
            json={
                "name": "Frontend Smoke",
                "slug": "frontend-smoke",
                "description": "Created while Qdrant is unavailable",
                "language": "en",
                "template": "blank",
            },
        )
    app.dependency_overrides.clear()

    assert res.status_code == 201
    body = res.json()
    assert body["library"]["id"] == "frontend-smoke"
    assert body["redirectTo"] == "/libraries/frontend-smoke/docs?onboarding=1"
    stored = await container.library_repo.get("frontend-smoke")
    assert stored is not None


async def test_post_libraries_duplicate_slug_uses_error_envelope(
    setup: tuple[AsyncClient, AppContainer, _FakeVectorIndex],
) -> None:
    client, _container, _vector = setup

    res = await client.post(
        "/api/libraries",
        json={
            "name": "Duplicate",
            "slug": "alpha-lib",
            "description": "",
            "language": "en",
            "template": "blank",
        },
    )

    assert res.status_code == 409
    body = res.json()
    assert body["code"] == "LIBRARY_ALREADY_EXISTS"
    assert body["details"] == {"library_id": "alpha-lib"}


async def test_post_libraries_invalid_slug_returns_400_envelope(
    setup: tuple[AsyncClient, AppContainer, _FakeVectorIndex],
) -> None:
    client, _container, _vector = setup

    res = await client.post(
        "/api/libraries",
        json={
            "name": "Invalid",
            "slug": "BadSlug",
            "description": "",
            "language": "zh",
            "template": "blank",
        },
    )

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "Invalid slug" in body["message"]


async def test_post_libraries_validation_failure_returns_422_envelope(
    setup: tuple[AsyncClient, AppContainer, _FakeVectorIndex],
) -> None:
    client, _container, _vector = setup

    res = await client.post(
        "/api/libraries",
        json={
            "name": "Missing Template",
            "slug": "missing-template",
            "description": "",
            "language": "en",
        },
    )

    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body["details"], list)


async def test_get_libraries_server_failure_uses_error_envelope(tmp_path: Path) -> None:
    container = _build_container(tmp_path, library_repo=_BrokenLibraryRepository())
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/libraries")
    app.dependency_overrides.clear()

    assert res.status_code == 500
    body = res.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert body["message"] == "Internal server error"
    assert body["details"] == {"type": "RuntimeError"}
