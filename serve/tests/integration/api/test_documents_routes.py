"""Integration tests for `/v1/libraries/{lib}/docs/*`.

Pattern:
- Build a real `FilesystemLibraryRepository` and a real `IngestStateStore`
  so the document detail / chunks / pdf / delete endpoints can read
  actual records.
- The retry endpoint requires the task queue. We inject a fake via
  `apps.api._task_deps.set_task_bundle_for_testing`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.factories.ingest_runner import _state_store
from apps._shared.persistence.library_fs import (
    FilesystemLibraryRepository,
    make_library,
)
from apps.api._task_deps import reset_task_bundle, set_task_bundle_for_testing
from apps.api.deps import get_container
from apps.api.main import app
from packages.core.config import Settings
from packages.ingestion.state import IngestRecord
from packages.orchestration.queue import (
    TaskEvent,
    TaskHandle,
    TaskId,
    TaskSpec,
    TaskState,
)


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised here."""


def _build_test_container(tmp_path: Path) -> AppContainer:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        ingest_state_dir=str(tmp_path / "data" / "ingest"),
    )
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
        return None

    async def cancel(self, library_id: str, task_id: TaskId) -> bool:
        return False

    async def list_active(self, library_id: str) -> tuple[TaskHandle, ...]:
        return ()


class _FakeBus:
    async def emit(self, event: TaskEvent) -> None:
        return None

    async def stream(
        self, library_id: str, task_id: TaskId, *, since_seq: int | None = None
    ) -> object:
        async def _empty() -> AsyncIterator[TaskEvent]:
            if False:
                yield  # pragma: no cover

        return _empty()


@pytest.fixture
async def test_container(tmp_path: Path) -> AppContainer:
    container = _build_test_container(tmp_path)
    await container.library_repo.create(make_library(library_id="lib-d", name="Lib D"))

    # Seed an ingest record for doc-001
    store = _state_store(container)
    try:
        store.put(
            IngestRecord(
                library_id="lib-d",
                file_sha256="sha-doc-001",
                file_name="paper.pdf",
                doc_id="doc-001",
                title="Test Paper",
                status="done",
                chunks_created=5,
                chunks_upserted=5,
                last_error=None,
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
        store.put(
            IngestRecord(
                library_id="lib-d",
                file_sha256="sha-doc-002",
                file_name="failed.pdf",
                doc_id="doc-002",
                title="Failed Paper",
                status="failed",
                chunks_created=0,
                chunks_upserted=0,
                last_error="parse error",
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
    finally:
        store.close()

    return container


@pytest.fixture
async def client(test_container: AppContainer) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_container] = lambda: test_container
    queue = _FakeQueue()
    bus = _FakeBus()
    set_task_bundle_for_testing(
        queue=queue,  # type: ignore[arg-type]
        events=bus,  # type: ignore[arg-type]
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()
    await reset_task_bundle()


@pytest.mark.asyncio
async def test_get_document_returns_detail(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/lib-d/docs/doc-001")
    assert res.status_code == 200
    body = res.json()
    assert body["library_id"] == "lib-d"
    assert body["doc_id"] == "doc-001"
    assert body["title"] == "Test Paper"
    assert body["chunks_count"] == 5
    assert body["ingest_status"] == "ready"


@pytest.mark.asyncio
async def test_get_document_404_for_unknown_doc(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/lib-d/docs/missing")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_chunks_endpoint_returns_envelope(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/lib-d/docs/doc-001/chunks")
    assert res.status_code == 200
    body = res.json()
    assert body["library_id"] == "lib-d"
    assert body["doc_id"] == "doc-001"
    assert isinstance(body["chunks"], list)


@pytest.mark.asyncio
async def test_pdf_endpoint_returns_presigned_url(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/lib-d/docs/doc-001/pdf")
    assert res.status_code == 200
    body = res.json()
    assert body["library_id"] == "lib-d"
    assert body["doc_id"] == "doc-001"
    assert body["url"].startswith("http://")
    assert body["expires_at"]


@pytest.mark.asyncio
async def test_retry_failed_doc_enqueues_task(client: AsyncClient) -> None:
    res = await client.post(
        "/v1/libraries/lib-d/docs/doc-002/retry",
        params={"parser": "mineru"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["task_id"]
    assert body["parser"] == "mineru"


@pytest.mark.asyncio
async def test_delete_document_removes_record(client: AsyncClient) -> None:
    res = await client.delete("/v1/libraries/lib-d/docs/doc-001")
    assert res.status_code == 204
    follow = await client.get("/v1/libraries/lib-d/docs/doc-001")
    assert follow.status_code == 404
