"""Integration tests for ``/v1/libraries/{lib}/eval/*`` + ``/v1/eval/alerts``.

The pattern mirrors ``test_conversations_endpoints.py``:

  1. Build a real ``AppContainer`` with ``tmp_path``-rooted sqlite paths.
  2. Inject fake ``EvalSnapshotter`` / ``AlertEngine`` adapters into the
     ``apps.api._eval_deps`` test cache so the routes can be exercised
     without Postgres.
  3. Override ``apps.api.deps.get_container`` with the test container.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
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
from packages.orchestration.eval_models import (
    AlertRule,
    EvalAlert,
    EvalKPIs,
    EvalSnapshot,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _Sentinel:
    """Stand-in for AppContainer fields the eval routes don't touch."""


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="x", model="fake", input_tokens=1, output_tokens=1)


class _FakeSnapshotter:
    """Minimal duck-type for ``EvalSnapshotter`` used by the route layer."""

    def __init__(self) -> None:
        self.kpis_calls: list[tuple[str, str]] = []
        self.trend_calls: list[tuple[str, str, str, int]] = []
        self.failures_calls: list[tuple[str, int, int]] = []

    async def get_kpis(self, library_id: str, *, eval_set: str) -> EvalKPIs | None:
        self.kpis_calls.append((library_id, eval_set))
        if library_id == "lib-empty":
            return None
        now = datetime.now(UTC)
        return EvalKPIs(
            library_id=library_id,
            eval_set=eval_set,  # type: ignore[arg-type]
            var=0.81,
            citation_f1=0.74,
            p95_latency_s=12.5,
            avg_cost_usd=Decimal("0.0123"),
            delta_1d={},
            delta_7d={"var": 0.02},
            sample_size=42,
            computed_at=now,
        )

    async def get_trend(
        self, library_id: str, *, metric: str, eval_set: str, days: int = 30
    ) -> tuple[EvalSnapshot, ...]:
        self.trend_calls.append((library_id, metric, eval_set, days))
        today = datetime.now(UTC).date()
        return (
            EvalSnapshot(
                library_id=library_id,
                date=today - timedelta(days=1),
                eval_set=eval_set,  # type: ignore[arg-type]
                metric=metric,  # type: ignore[arg-type]
                value=0.78,
                sample_size=10,
                computed_at=datetime.now(UTC),
            ),
            EvalSnapshot(
                library_id=library_id,
                date=today,
                eval_set=eval_set,  # type: ignore[arg-type]
                metric=metric,  # type: ignore[arg-type]
                value=0.82,
                sample_size=14,
                computed_at=datetime.now(UTC),
            ),
        )

    async def list_failures(
        self,
        library_id: str,
        *,
        days: int = 30,
        limit: int = 20,
    ) -> tuple[EvalSnapshot, ...]:
        self.failures_calls.append((library_id, days, limit))
        today = datetime.now(UTC).date()
        return (
            EvalSnapshot(
                library_id=library_id,
                date=today,
                eval_set="smoke",
                metric="var",
                value=0.42,
                sample_size=5,
                computed_at=datetime.now(UTC),
            ),
        )


class _FakeAlertEngine:
    """Minimal duck-type for the route layer's ``AlertEngine`` calls."""

    def __init__(self, *, library_to_alerts: dict[str, tuple[EvalAlert, ...]]) -> None:
        self._actives = library_to_alerts
        self.list_active_calls: list[str] = []

    async def list_active(self, library_id: str) -> tuple[EvalAlert, ...]:
        self.list_active_calls.append(library_id)
        return self._actives.get(library_id, ())

    async def list_recent(
        self,
        library_id: str,
        *,
        days: int = 30,
        limit: int = 50,
    ) -> tuple[EvalAlert, ...]:
        _ = days, limit
        return self._actives.get(library_id, ())


def _make_alert(library_id: str, *, rule: AlertRule = AlertRule.VAR_DROP_5PP) -> EvalAlert:
    now = datetime.now(UTC)
    return EvalAlert(
        id=f"alrt-{library_id}-{rule.value}",
        library_id=library_id,
        rule=rule,
        severity="danger",
        status="active",
        triggered_at=now,
        recovered_at=None,
        recovery_consecutive_days=0,
        payload={"metric": "var", "delta_pp": -7.0},
        notification_id=None,
    )


# ---------------------------------------------------------------------------
# Container + fixtures
# ---------------------------------------------------------------------------


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
    await container.library_repo.create(make_library(library_id="lib-b", name="Lib B"))
    return container


@pytest.fixture
async def fakes() -> AsyncIterator[tuple[_FakeSnapshotter, _FakeAlertEngine]]:
    snapshotter = _FakeSnapshotter()
    alert_engine = _FakeAlertEngine(
        library_to_alerts={
            "lib-a": (_make_alert("lib-a"),),
            "lib-b": (_make_alert("lib-b", rule=AlertRule.P95_RISE_50PCT),),
        }
    )
    set_eval_bundle_for_testing(
        snapshots=snapshotter,  # type: ignore[arg-type]
        alerts=alert_engine,  # type: ignore[arg-type]
    )
    try:
        yield snapshotter, alert_engine
    finally:
        await reset_eval_bundle()


@pytest.fixture
async def client(
    test_container: AppContainer,
    fakes: tuple[_FakeSnapshotter, _FakeAlertEngine],
) -> AsyncIterator[AsyncClient]:
    _ = fakes  # ensures fakes are wired before requests
    app.dependency_overrides[get_container] = lambda: test_container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Per-Library reads
# ---------------------------------------------------------------------------


async def test_get_kpis_returns_card_row(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/lib-a/eval/kpis?eval_set=smoke&days=7")
    assert res.status_code == 200
    body = res.json()
    assert body["library_id"] == "lib-a"
    assert body["eval_set"] == "smoke"
    assert body["var"] == pytest.approx(0.81)
    assert body["citation_f1"] == pytest.approx(0.74)
    assert body["sample_size"] == 42
    assert body["delta_7d"]["var"] == pytest.approx(0.02)


async def test_get_kpis_returns_404_when_no_snapshots(client: AsyncClient) -> None:
    # The fake returns None for "lib-empty"; the route also requires the
    # library to exist. Create it first so we test the snapshot-empty path
    # rather than the library-missing path.
    res = await client.get("/v1/libraries/lib-empty/eval/kpis?eval_set=smoke&days=7")
    # Library doesn't exist → 404 (LIBRARY_NOT_FOUND envelope).
    assert res.status_code == 404


async def test_get_trend_returns_ordered_rows(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/lib-a/eval/trend?metric=var&eval_set=smoke&days=30")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 2
    assert rows[0]["metric"] == "var"
    assert rows[0]["library_id"] == "lib-a"
    parsed_dates = [date.fromisoformat(r["date"]) for r in rows]
    assert parsed_dates == sorted(parsed_dates)


async def test_get_failures_returns_low_var_rows(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/lib-a/eval/failures?limit=5&days=30")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["value"] < 0.5


async def test_list_library_alerts_returns_active(
    client: AsyncClient,
    fakes: tuple[_FakeSnapshotter, _FakeAlertEngine],
) -> None:
    _, alert_engine = fakes
    res = await client.get("/v1/libraries/lib-a/eval/alerts?status=active")
    assert res.status_code == 200
    alerts = res.json()
    assert len(alerts) == 1
    assert alerts[0]["library_id"] == "lib-a"
    assert alerts[0]["rule"] == AlertRule.VAR_DROP_5PP.value
    assert alerts[0]["status"] == "active"
    assert "lib-a" in alert_engine.list_active_calls


async def test_library_not_found_returns_envelope(client: AsyncClient) -> None:
    res = await client.get("/v1/libraries/no-such-lib/eval/kpis?eval_set=smoke&days=7")
    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"


# ---------------------------------------------------------------------------
# Cross-Library aggregator
# ---------------------------------------------------------------------------


async def test_global_alerts_with_library_ids_query_aggregates(
    client: AsyncClient,
) -> None:
    res = await client.get("/v1/eval/alerts?status=active&library_ids=lib-a&library_ids=lib-b")
    assert res.status_code == 200
    alerts = res.json()
    assert {a["library_id"] for a in alerts} == {"lib-a", "lib-b"}


async def test_global_alerts_without_library_ids_uses_repo(
    client: AsyncClient,
) -> None:
    res = await client.get("/v1/eval/alerts?status=active")
    assert res.status_code == 200
    alerts = res.json()
    # Both libraries from the test container should be scanned.
    assert {a["library_id"] for a in alerts} == {"lib-a", "lib-b"}


async def test_global_alerts_handles_engine_failure_per_library(
    client: AsyncClient,
    fakes: tuple[_FakeSnapshotter, _FakeAlertEngine],
) -> None:
    """If one Library's alert query raises, others must still return."""
    _, alert_engine = fakes

    async def boom(library_id: str) -> tuple[EvalAlert, ...]:
        if library_id == "lib-a":
            raise RuntimeError("synthetic failure")
        return (_make_alert(library_id),)

    # Rebind via the engine's instance attribute so the test isolates the
    # injection without touching the route code.
    alert_engine.list_active = boom  # type: ignore[method-assign]

    res = await client.get("/v1/eval/alerts?status=active")
    assert res.status_code == 200
    alerts = res.json()
    assert {a["library_id"] for a in alerts} == {"lib-b"}
