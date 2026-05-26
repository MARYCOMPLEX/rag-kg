"""Integration tests for the M7 notification routes (ADR-0011).

Strategy: inject a hand-rolled `NotificationStore` + `NotificationCrossReader`
into the orchestration deps cache, build a minimal `AppContainer`, and
drive the FastAPI app via httpx ASGI transport.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import (
    FilesystemLibraryRepository,
    make_library,
)
from apps.api._orchestration_deps import (
    reset_orchestration_bundle,
    set_orchestration_bundle_for_testing,
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
from packages.orchestration.notifications import (
    Notification,
    NotificationType,
)


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised in these tests."""


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


class _FakeStore:
    """In-memory `NotificationStore` for endpoint round-trip tests."""

    def __init__(self) -> None:
        self.rows: dict[str, Notification] = {}
        self.read_calls: list[tuple[str | None, str]] = []

    async def write(self, notification: Notification) -> None:
        self.rows[notification.id] = notification

    async def get(self, notification_id: str) -> Notification | None:
        return self.rows.get(notification_id)

    async def mark_read(self, library_id: str | None, notification_id: str) -> None:
        self.read_calls.append((library_id, notification_id))
        existing = self.rows.get(notification_id)
        if existing is not None:
            self.rows[notification_id] = existing.model_copy(
                update={"read": True, "read_at": datetime.now(UTC)}
            )

    async def list_for_library(
        self,
        library_id: str,
        *,
        unread_only: bool = False,
        since: datetime | None = None,
        limit: int = 50,
    ) -> tuple[Notification, ...]:
        rows = [n for n in self.rows.values() if n.library_id is None or n.library_id == library_id]
        if unread_only:
            rows = [n for n in rows if not n.read]
        if since is not None:
            rows = [n for n in rows if n.created_at >= since]
        rows.sort(key=lambda n: n.created_at, reverse=True)
        return tuple(rows[:limit])


class _FakeReader:
    """In-memory `NotificationCrossReader` for cross-library list endpoint."""

    def __init__(self, store: _FakeStore) -> None:
        self._store = store

    async def list_for_libraries(
        self,
        *,
        library_ids: Sequence[str],
        unread_only: bool = False,
        since: datetime | None = None,
        limit: int = 50,
    ) -> tuple[Notification, ...]:
        rows = [
            n
            for n in self._store.rows.values()
            if n.library_id is None or n.library_id in set(library_ids)
        ]
        if unread_only:
            rows = [n for n in rows if not n.read]
        if since is not None:
            rows = [n for n in rows if n.created_at >= since]
        rows.sort(key=lambda n: n.created_at, reverse=True)
        return tuple(rows[:limit])

    async def count_unread(self, *, library_ids: Sequence[str]) -> int:
        return sum(
            1
            for n in self._store.rows.values()
            if not n.read and (n.library_id is None or n.library_id in set(library_ids))
        )


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
async def setup(tmp_path: Path) -> AsyncIterator[tuple[AsyncClient, _FakeStore]]:
    container = _build_container(tmp_path)
    library = make_library(library_id="lib-a", name="Lib A")
    await container.library_repo.create(library)

    store = _FakeStore()
    reader = _FakeReader(store)

    set_orchestration_bundle_for_testing(
        notifications=store,  # type: ignore[arg-type]
        notification_reader=reader,  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, store

    app.dependency_overrides.clear()
    await reset_orchestration_bundle()


def _seed(
    store: _FakeStore,
    *,
    nid: str,
    library_id: str | None,
    read: bool = False,
    minutes_ago: int = 0,
) -> None:
    now = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    store.rows[nid] = Notification(
        id=nid,
        library_id=library_id,
        type=NotificationType.TASK_COMPLETED,
        severity="info",
        title=f"Notification {nid}",
        body=None,
        payload={},
        read=read,
        read_at=None,
        created_at=now,
        expires_at=now + timedelta(days=90),
    )


async def test_list_notifications_returns_global_and_scoped(
    setup: tuple[AsyncClient, _FakeStore],
) -> None:
    # Arrange
    client, store = setup
    _seed(store, nid="01HABC", library_id="lib-a", minutes_ago=5)
    _seed(store, nid="01HDEF", library_id=None, minutes_ago=2)
    _seed(store, nid="01HGHI", library_id="lib-other", minutes_ago=1)

    # Act
    res = await client.get("/v1/notifications", params={"library_ids": "lib-a"})

    # Assert
    assert res.status_code == 200
    body = res.json()
    ids = {row["id"] for row in body["items"]}
    assert ids == {"01HABC", "01HDEF"}
    assert body["unread_count"] == 2


async def test_mark_notification_read_idempotent(
    setup: tuple[AsyncClient, _FakeStore],
) -> None:
    # Arrange
    client, store = setup
    _seed(store, nid="01HONE", library_id="lib-a")

    # Act — mark twice
    res1 = await client.post("/v1/notifications/01HONE/read", params={"library_id": "lib-a"})
    res2 = await client.post("/v1/notifications/01HONE/read", params={"library_id": "lib-a"})

    # Assert
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json() == {"id": "01HONE", "marked": True}
    assert store.rows["01HONE"].read is True


async def test_per_library_list_uses_store_not_reader(
    setup: tuple[AsyncClient, _FakeStore],
) -> None:
    # Arrange
    client, store = setup
    _seed(store, nid="01HLA", library_id="lib-a")
    _seed(store, nid="01HOTHER", library_id="lib-other")

    # Act
    res = await client.get("/v1/libraries/lib-a/notifications")

    # Assert
    assert res.status_code == 200
    ids = [row["id"] for row in res.json()["items"]]
    assert ids == ["01HLA"]
