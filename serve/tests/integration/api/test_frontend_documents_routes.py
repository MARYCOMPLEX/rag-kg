"""Integration tests for the frontend `/api/libraries/*/documents` adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.factories.ingest_runner import _state_store
from apps._shared.persistence.library_fs import FilesystemLibraryRepository, make_library
from apps.api import _task_deps
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
from packages.ingestion.state import IngestRecord
from packages.llm.protocols import LLMResponse
from packages.orchestration.queue import (
    TaskEvent,
    TaskHandle,
    TaskId,
    TaskSpec,
    TaskState,
)


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised here."""


@dataclass(frozen=True, slots=True)
class _ChunkRow:
    chunk_id: str
    text: str
    page: int | None
    section: str | None


@dataclass(frozen=True, slots=True)
class _TripleRow:
    head: str
    tail: str


class _FakeVectorIndex:
    async def list_chunks_by_doc(
        self,
        library_id: str,
        doc_id: str,
        *,
        limit: int,
    ) -> tuple[_ChunkRow, ...]:
        _ = library_id, doc_id, limit
        return (
            _ChunkRow(
                chunk_id="chunk-1",
                text="Graph summaries ground the final response.",
                page=2,
                section="Methods",
            ),
        )


class _FakeGraphIndex:
    async def list_all_triples(self, library_id: str) -> tuple[_TripleRow, ...]:
        _ = library_id
        return (
            _TripleRow(head="GraphRAG", tail="community summaries"),
            _TripleRow(head="GraphRAG", tail="citations"),
        )


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


class _BrokenLibraryRepository:
    async def list_all(self) -> list[object]:
        return []

    async def create(self, library: object) -> None:
        _ = library

    async def get(self, library_id: str) -> object | None:
        _ = library_id
        return None

    async def delete(self, library_id: str) -> None:
        _ = library_id

    async def exists(self, library_id: str) -> bool:
        _ = library_id
        raise RuntimeError("repository unavailable")


class _FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[TaskSpec] = []

    async def enqueue(self, library_id: str, spec: TaskSpec) -> TaskHandle:
        self.enqueued.append(spec)
        return TaskHandle(
            library_id=library_id,
            task_id="01HZAAAAAAAAAAAAAAAAAAAAAA",
            enqueued_at=datetime.now(UTC),
        )

    async def get(self, library_id: str, task_id: TaskId) -> TaskState | None:
        _ = library_id, task_id
        return None

    async def cancel(self, library_id: str, task_id: TaskId) -> bool:
        _ = library_id, task_id
        return False

    async def list_active(self, library_id: str) -> tuple[TaskHandle, ...]:
        _ = library_id
        return ()


class _FakeBus:
    async def emit(self, event: TaskEvent) -> None:
        _ = event

    async def stream(
        self,
        library_id: str,
        task_id: TaskId,
        *,
        since_seq: int | None = None,
    ) -> AsyncIterator[TaskEvent]:
        _ = library_id, task_id, since_seq
        if False:
            yield  # pragma: no cover


def _build_container(
    tmp_path: Path,
    *,
    library_repo: object | None = None,
) -> AppContainer:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        ingest_state_dir=str(tmp_path / "data" / "ingest"),
    )
    repo = library_repo or FilesystemLibraryRepository(data_dir=tmp_path / "data")
    db_path = tmp_path / "context.sqlite"
    conversation_repo = SqliteConversationRepo(db_path)
    memory_store = SqliteMemoryStore(db_path)
    research_memory = ResearchMemory(store=memory_store, max_entries_in_prompt=5)
    context_service = ContextService(store=conversation_repo, memory_store=memory_store)
    counter = CharCountTokenCounter()
    budget = ContextBudget()
    return AppContainer(
        settings=settings,
        library_repo=repo,  # type: ignore[arg-type]
        parser=_Sentinel(),
        chunker=_Sentinel(),
        embedder=_Sentinel(),
        raw_embedder=_Sentinel(),
        vector_index=_FakeVectorIndex(),  # type: ignore[arg-type]
        bm25_index=_Sentinel(),
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


def _seed_record(
    container: AppContainer,
    *,
    doc_id: str,
    file_name: str,
    title: str | None,
    status: str,
    chunks: int,
    last_error: str | None = None,
) -> None:
    store = _state_store(container)
    try:
        store.put(
            IngestRecord(
                library_id="lib-docs",
                file_sha256=f"sha-{doc_id}",
                file_name=file_name,
                doc_id=doc_id,
                title=title,
                status=status,
                chunks_created=chunks,
                chunks_upserted=chunks,
                last_error=last_error,
                created_at=datetime(2026, 5, 20, 9, 30, tzinfo=UTC).isoformat(),
                updated_at=datetime(2026, 5, 21, 10, 45, tzinfo=UTC).isoformat(),
            )
        )
    finally:
        store.close()


@pytest.fixture
def queue() -> _FakeQueue:
    return _FakeQueue()


@pytest.fixture
async def client(tmp_path: Path, queue: _FakeQueue) -> AsyncIterator[AsyncClient]:
    container = _build_container(tmp_path)
    await container.library_repo.create(make_library(library_id="lib-docs", name="Docs Lib"))
    _seed_record(
        container,
        doc_id="doc-ready",
        file_name="graphrag.pdf",
        title="GraphRAG Paper",
        status="done",
        chunks=12,
    )
    _seed_record(
        container,
        doc_id="doc-failed",
        file_name="failed.pdf",
        title=None,
        status="failed",
        chunks=0,
        last_error="parse failed",
    )
    app.dependency_overrides[get_container] = lambda: container
    set_task_bundle_for_testing(
        queue=queue,  # type: ignore[arg-type]
        events=_FakeBus(),  # type: ignore[arg-type]
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()
    await reset_task_bundle()


async def test_list_documents_returns_frontend_workspace_shape(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/lib-docs/documents")

    assert res.status_code == 200
    body = res.json()
    assert body["summary"] == {
        "libraryId": "lib-docs",
        "documentCountLabel": "2 documents",
        "chunkCountLabel": "12 chunks",
        "lastSyncLabel": "Last sync 2026-05-21",
    }
    documents = {row["id"]: row for row in body["documents"]}
    assert set(documents) == {"doc-ready", "doc-failed"}
    ready = documents["doc-ready"]
    assert ready["libraryId"] == "lib-docs"
    assert ready["title"] == "GraphRAG Paper"
    assert ready["source"] == "graphrag.pdf"
    assert ready["year"] == 2026
    assert ready["status"]["kind"] == "ready"
    assert ready["chunks"] == 12
    assert ready["entities"] is None
    failed = documents["doc-failed"]
    assert failed["status"]["kind"] == "failed"
    assert failed["status"]["actionLabel"] == "Retry ingestion"


async def test_list_documents_allows_empty_library(tmp_path: Path) -> None:
    container = _build_container(tmp_path)
    await container.library_repo.create(make_library(library_id="empty-lib", name="Empty Lib"))
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        res = await instance.get("/api/libraries/empty-lib/documents")
    app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json() == {
        "summary": {
            "libraryId": "empty-lib",
            "documentCountLabel": "0 documents",
            "chunkCountLabel": "0 chunks",
            "lastSyncLabel": "No documents",
        },
        "documents": [],
    }


async def test_get_document_returns_frontend_detail_shape(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/lib-docs/documents/doc-ready")

    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "doc-ready"
    assert body["fileFormat"] == "PDF"
    assert body["fileSizeLabel"] == "Unknown"
    assert body["ingestedAtLabel"] == "2026-05-21 10:45"
    assert body["pageCount"] == 1
    assert body["selectedPage"] == 1
    assert body["statistics"] == [
        {"label": "chunks", "value": "12"},
        {"label": "entities", "value": "3"},
        {"label": "triples", "value": "2"},
        {"label": "pages", "value": "1"},
    ]
    assert body["sections"] == []
    assert body["chunksPreview"] == [
        {
            "id": "chunk-1",
            "locationLabel": "Methods / p.2",
            "text": "Graph summaries ground the final response.",
        }
    ]


async def test_get_document_missing_library_uses_error_envelope(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/missing-lib/documents")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["details"] == {"library_id": "missing-lib"}


async def test_get_document_missing_document_uses_error_envelope(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/lib-docs/documents/missing-doc")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "Document not found: missing-doc"


async def test_retry_failed_document_returns_frontend_feedback(
    client: AsyncClient,
    queue: _FakeQueue,
) -> None:
    res = await client.post("/api/libraries/lib-docs/documents/doc-failed:retry")

    assert res.status_code == 202
    assert res.json() == {
        "tone": "warning",
        "title": "Retry queued",
        "detail": "failed.pdf ingestion retry queued.",
        "action": "Logs",
    }
    assert len(queue.enqueued) == 1
    spec = queue.enqueued[0]
    assert spec.task_type == "ingest_document"
    assert spec.input_payload == {
        "doc_id": "doc-failed",
        "file_sha256": "sha-doc-failed",
        "file_name": "failed.pdf",
        "parser": "auto",
        "force": True,
    }


async def test_retry_ready_document_returns_conflict(client: AsyncClient) -> None:
    res = await client.post("/api/libraries/lib-docs/documents/doc-ready:retry")

    assert res.status_code == 409
    body = res.json()
    assert body["code"] == "CONFLICT"
    assert body["message"] == "Document is already ready: doc-ready"


async def test_retry_missing_document_uses_error_envelope(client: AsyncClient) -> None:
    res = await client.post("/api/libraries/lib-docs/documents/missing-doc:retry")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "Document not found: missing-doc"


async def test_retry_missing_library_does_not_initialize_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_build_bundle(container: AppContainer) -> NoReturn:
        _ = container
        raise AssertionError("queue should not initialize before missing-library response")

    await reset_task_bundle()
    monkeypatch.setattr(_task_deps, "_build_bundle", fail_build_bundle)
    container = _build_container(tmp_path)
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        res = await instance.post("/api/libraries/missing-lib/documents/missing-doc:retry")
    app.dependency_overrides.clear()
    await reset_task_bundle()

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["details"] == {"library_id": "missing-lib"}


async def test_retry_missing_document_does_not_initialize_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_build_bundle(container: AppContainer) -> NoReturn:
        _ = container
        raise AssertionError("queue should not initialize before missing-document response")

    await reset_task_bundle()
    monkeypatch.setattr(_task_deps, "_build_bundle", fail_build_bundle)
    container = _build_container(tmp_path)
    await container.library_repo.create(make_library(library_id="lib-docs", name="Docs Lib"))
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        res = await instance.post("/api/libraries/lib-docs/documents/missing-doc:retry")
    app.dependency_overrides.clear()
    await reset_task_bundle()

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "Document not found: missing-doc"


async def test_retry_queue_unavailable_uses_upstream_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_build_bundle(container: AppContainer) -> NoReturn:
        _ = container
        raise TimeoutError("redis unavailable")

    await reset_task_bundle()
    monkeypatch.setattr(_task_deps, "_build_bundle", fail_build_bundle)
    container = _build_container(tmp_path)
    await container.library_repo.create(make_library(library_id="lib-docs", name="Docs Lib"))
    _seed_record(
        container,
        doc_id="doc-failed",
        file_name="failed.pdf",
        title=None,
        status="failed",
        chunks=0,
        last_error="parse failed",
    )
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        res = await instance.post("/api/libraries/lib-docs/documents/doc-failed:retry")
    app.dependency_overrides.clear()
    await reset_task_bundle()

    assert res.status_code == 503
    body = res.json()
    assert body["code"] == "UPSTREAM_ERROR"
    assert body["message"] == "Document retry queue unavailable"


async def test_documents_server_failure_uses_error_envelope(tmp_path: Path) -> None:
    container = _build_container(tmp_path, library_repo=_BrokenLibraryRepository())
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        res = await instance.get("/api/libraries/lib-docs/documents")
    app.dependency_overrides.clear()

    assert res.status_code == 500
    body = res.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert body["details"] == {"type": "RuntimeError"}
