"""Integration tests for the M7 library_settings routes (ADR-0012, ADR-0015)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
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
from packages.orchestration.cost import CostCheckResult, LibraryDailyCost
from packages.orchestration.library_config import (
    EmbedderSpec,
    LibraryConfig,
    LibraryConfigPatch,
)


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised in these tests."""


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


class _FakeConfigStore:
    """In-memory `LibraryConfigStore` for endpoint round-trip tests."""

    def __init__(self) -> None:
        self.rows: dict[str, LibraryConfig] = {}

    async def get(self, library_id: str) -> LibraryConfig:
        existing = self.rows.get(library_id)
        if existing is not None:
            return existing
        return LibraryConfig(library_id=library_id, updated_at=datetime.now(UTC))

    async def update(
        self,
        library_id: str,
        patch: LibraryConfigPatch,
        *,
        updated_by: str,
    ) -> LibraryConfig:
        current = await self.get(library_id)
        set_fields = patch.model_fields_set
        updates: dict[str, Any] = {
            "updated_at": datetime.now(UTC),
            "updated_by": updated_by,
        }
        for field in set_fields:
            updates[field] = getattr(patch, field)
        merged = current.model_copy(update=updates)
        self.rows[library_id] = merged
        return merged

    async def init_library(self, library_id: str) -> None:
        if library_id not in self.rows:
            self.rows[library_id] = LibraryConfig(
                library_id=library_id, updated_at=datetime.now(UTC)
            )

    async def purge_library(self, library_id: str) -> None:
        self.rows.pop(library_id, None)


class _FakeCostEnforcer:
    """In-memory cost enforcer for the `/cost` endpoint."""

    def __init__(self) -> None:
        self.history_rows: tuple[LibraryDailyCost, ...] = ()

    async def check(self, library_id: str) -> CostCheckResult:
        return CostCheckResult(
            library_id=library_id,
            decision="allow",
            spent_usd=Decimal("0"),
            cap_usd=None,
            pct_used=0.0,
            next_reset_at=datetime.now(UTC),
        )

    async def record(
        self,
        library_id: str,
        cost_usd: Decimal,
        llm_calls: int = 1,
    ) -> CostCheckResult:
        return await self.check(library_id)

    async def history(self, library_id: str, *, days: int = 30) -> tuple[LibraryDailyCost, ...]:
        return self.history_rows

    async def purge_library(self, library_id: str) -> None:
        self.history_rows = ()


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
async def setup(
    tmp_path: Path,
) -> AsyncIterator[tuple[AsyncClient, _FakeConfigStore, _FakeCostEnforcer]]:
    container = _build_container(tmp_path)
    library = make_library(library_id="lib-a", name="Lib A")
    await container.library_repo.create(library)

    config = _FakeConfigStore()
    cost = _FakeCostEnforcer()
    set_orchestration_bundle_for_testing(
        config=config,  # type: ignore[arg-type]
        cost=cost,  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, config, cost

    app.dependency_overrides.clear()
    await reset_orchestration_bundle()


async def test_get_returns_default_overrides_for_fresh_library(
    setup: tuple[AsyncClient, _FakeConfigStore, _FakeCostEnforcer],
) -> None:
    # Arrange
    client, _config, _cost = setup

    # Act
    res = await client.get("/v1/libraries/lib-a/settings")

    # Assert
    assert res.status_code == 200
    body = res.json()
    assert body["library_id"] == "lib-a"
    assert body["llm_router_override"] is None
    assert body["embedder_override"] is None
    assert body["daily_cost_cap_usd"] is None
    assert body["timezone"] == "UTC"


async def test_put_persists_embedder_and_cost_cap(
    setup: tuple[AsyncClient, _FakeConfigStore, _FakeCostEnforcer],
) -> None:
    # Arrange
    client, config, _cost = setup
    payload = {
        "embedder_override": {
            "name": "qwen3-embedding",
            "dim": 4096,
        },
        "daily_cost_cap_usd": "5.50",
    }

    # Act
    res = await client.put("/v1/libraries/lib-a/settings", json=payload)

    # Assert
    assert res.status_code == 200
    body = res.json()
    assert body["embedder_override"]["name"] == "qwen3-embedding"
    assert body["embedder_override"]["dim"] == 4096
    assert Decimal(body["daily_cost_cap_usd"]) == Decimal("5.50")
    stored = config.rows["lib-a"]
    assert isinstance(stored.embedder_override, EmbedderSpec)
    assert stored.embedder_override.name == "qwen3-embedding"
    assert stored.daily_cost_cap_usd == Decimal("5.50")


async def test_get_settings_round_trip_after_put(
    setup: tuple[AsyncClient, _FakeConfigStore, _FakeCostEnforcer],
) -> None:
    # Arrange
    client, _config, _cost = setup
    await client.put(
        "/v1/libraries/lib-a/settings",
        json={"timezone": "Asia/Shanghai", "cost_cap_warn_pct": 0.5},
    )

    # Act
    res = await client.get("/v1/libraries/lib-a/settings")

    # Assert
    assert res.status_code == 200
    body = res.json()
    assert body["timezone"] == "Asia/Shanghai"
    assert body["cost_cap_warn_pct"] == 0.5


async def test_cost_endpoint_returns_today_default_when_empty(
    setup: tuple[AsyncClient, _FakeConfigStore, _FakeCostEnforcer],
) -> None:
    # Arrange
    client, _config, _cost = setup

    # Act
    res = await client.get("/v1/libraries/lib-a/cost", params={"days": 7})

    # Assert
    assert res.status_code == 200
    body = res.json()
    assert body["library_id"] == "lib-a"
    assert body["cap_usd"] is None
    assert Decimal(body["today"]["cost_usd"]) == Decimal("0")
    assert body["history"] == []
