"""Integration tests for frontend evaluation dashboard adapter."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from apps._shared.factories import AppContainer
from apps._shared.persistence.library_fs import FilesystemLibraryRepository, make_library
from apps.api._eval_deps import reset_eval_bundle, set_eval_bundle_for_testing
from apps.api.deps import get_container
from apps.api.main import app
from apps.api.routes import frontend_evaluation
from packages.context.budget import CharCountTokenCounter
from packages.context.compactor import TurnCompactor
from packages.context.conversation_repo import SqliteConversationRepo
from packages.context.memory import ResearchMemory, SqliteMemoryStore
from packages.context.prompt_composer import PromptComposer
from packages.context.protocols import ContextBudget
from packages.context.service import ContextService
from packages.core.config import Settings
from packages.llm.protocols import LLMResponse
from packages.orchestration.eval_models import AlertRule, EvalAlert, EvalKPIs, EvalSnapshot


class _Sentinel:
    """Cheap stand-in for AppContainer fields not exercised here."""


class _FakeLLM:
    async def complete(self, messages: Any, **kwargs: Any) -> LLMResponse:
        _ = messages, kwargs
        return LLMResponse(text="ok", model="fake", input_tokens=1, output_tokens=1)


class _FakeSnapshotter:
    def __init__(self, *, empty: bool = False, failing: bool = False) -> None:
        self._empty = empty
        self._failing = failing
        self.kpis_calls: list[tuple[str, str]] = []
        self.trend_calls: list[tuple[str, str, str, int]] = []

    async def get_kpis(self, library_id: str, *, eval_set: str) -> EvalKPIs | None:
        self.kpis_calls.append((library_id, eval_set))
        if self._failing:
            raise RuntimeError("snapshotter unavailable")
        if self._empty or eval_set != "smoke":
            return None
        return EvalKPIs(
            library_id=library_id,
            eval_set="smoke",
            var=0.84,
            citation_f1=0.78,
            p95_latency_s=2.4,
            avg_cost_usd=Decimal("0.021"),
            delta_1d={},
            delta_7d={"var": 0.04},
            sample_size=12,
            computed_at=datetime(2026, 5, 27, 8, 0, tzinfo=UTC),
        )

    async def get_trend(
        self,
        library_id: str,
        *,
        metric: str,
        eval_set: str,
        days: int = 30,
    ) -> tuple[EvalSnapshot, ...]:
        self.trend_calls.append((library_id, metric, eval_set, days))
        if self._failing:
            raise RuntimeError("snapshotter unavailable")
        if self._empty:
            return ()
        today = date(2026, 5, 27)
        value_by_metric = {
            "var": 0.84,
            "var_judge": 0.91,
            "citation_f1": 0.78,
            "p95_latency_s": 2.4,
        }
        return (
            EvalSnapshot(
                library_id=library_id,
                date=today - timedelta(days=1),
                eval_set=eval_set,  # type: ignore[arg-type]
                metric=metric,  # type: ignore[arg-type]
                value=max(value_by_metric[metric] - 0.05, 0.0),
                sample_size=9,
                computed_at=datetime(2026, 5, 26, 8, 0, tzinfo=UTC),
            ),
            EvalSnapshot(
                library_id=library_id,
                date=today,
                eval_set=eval_set,  # type: ignore[arg-type]
                metric=metric,  # type: ignore[arg-type]
                value=value_by_metric[metric],
                sample_size=12,
                computed_at=datetime(2026, 5, 27, 8, 0, tzinfo=UTC),
            ),
        )


class _FakeAlertEngine:
    def __init__(self, *, empty: bool = False, failing: bool = False) -> None:
        self._empty = empty
        self._failing = failing

    async def list_active(self, library_id: str) -> tuple[EvalAlert, ...]:
        if self._failing or self._empty:
            if self._failing:
                raise RuntimeError("alerts unavailable")
            return ()
        return (
            EvalAlert(
                id="alert-1",
                library_id=library_id,
                rule=AlertRule.VAR_DROP_5PP,
                severity="warning",
                status="active",
                triggered_at=datetime(2026, 5, 27, 8, 0, tzinfo=UTC),
                recovered_at=None,
                recovery_consecutive_days=0,
                payload={"metric": "var", "delta_pp": -6.5},
                notification_id=None,
            ),
        )


class _HangingSnapshotter:
    async def get_kpis(self, library_id: str, *, eval_set: str) -> EvalKPIs | None:
        _ = library_id, eval_set
        await asyncio.sleep(60)
        return None

    async def get_trend(
        self,
        library_id: str,
        *,
        metric: str,
        eval_set: str,
        days: int = 30,
    ) -> tuple[EvalSnapshot, ...]:
        _ = library_id, metric, eval_set, days
        await asyncio.sleep(60)
        return ()


class _HangingAlertEngine:
    async def list_active(self, library_id: str) -> tuple[EvalAlert, ...]:
        _ = library_id
        await asyncio.sleep(60)
        return ()


def _build_container(tmp_path: Path) -> AppContainer:
    settings = Settings(
        data_dir=str(tmp_path / "data"),
        planner="routed",
        embedding_model="text-embedding-3-small",
        embedding_dim=1536,
    )
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
async def container(tmp_path: Path) -> AppContainer:
    test_container = _build_container(tmp_path)
    await test_container.library_repo.create(
        make_library(
            library_id="rag-lib",
            name="RAG Library",
            created_at=datetime(2026, 5, 27, tzinfo=UTC),
        )
    )
    return test_container


async def _client(
    container: AppContainer,
    *,
    snapshotter: object,
    alert_engine: object,
) -> AsyncIterator[AsyncClient]:
    set_eval_bundle_for_testing(
        snapshots=snapshotter,  # type: ignore[arg-type]
        alerts=alert_engine,  # type: ignore[arg-type]
    )
    app.dependency_overrides[get_container] = lambda: container
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as instance:
        yield instance
    app.dependency_overrides.clear()
    await reset_eval_bundle()


@pytest.fixture
async def client(container: AppContainer) -> AsyncIterator[AsyncClient]:
    async for instance in _client(
        container,
        snapshotter=_FakeSnapshotter(),
        alert_engine=_FakeAlertEngine(),
    ):
        yield instance


async def test_evaluation_dashboard_returns_frontend_shape(client: AsyncClient) -> None:
    res = await client.get(
        "/api/libraries/rag-lib/evaluation/dashboard",
        params={"dataset": "smoke", "timeRange": "7d"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["summary"] == {
        "libraryId": "rag-lib",
        "libraryName": "RAG Library",
        "datasetSummaryLabel": "smoke (12)",
        "timeRangeLabel": "Last 7 days",
        "lastRunLabel": "Updated 2026-05-27",
    }
    assert body["filters"]["datasets"][0] == {
        "key": "smoke",
        "label": "Smoke",
        "count": 12,
        "active": True,
    }
    assert body["filters"]["timeRanges"][0] == {
        "key": "7d",
        "label": "Last 7 days",
        "active": True,
    }
    assert body["budgetAlert"] == {
        "tone": "warning",
        "title": "Evaluation alert: var drop 5pp",
        "detail": "var changed by -6.5pp.",
        "action": "Review evaluation settings",
        "dismissible": False,
    }
    assert [item["title"] for item in body["kpis"]] == [
        "Answer relevancy EM@1",
        "Faithfulness FactScore",
        "Citation precision C@1",
        "Latency p95",
    ]
    assert body["trend"]["days"] == ["May 26", "May 27"]
    assert body["trend"]["legend"][-1] == {"label": "Latency p95", "tone": "danger"}
    assert body["failureCases"] == []
    assert body["librarySettings"]["libraryLabel"] == "RAG Library"
    assert body["librarySettings"]["models"] == {
        "routerLabel": "Router: routed",
        "embeddingLabel": "text-embedding-3-small (1536d)",
        "warning": None,
    }


async def test_evaluation_dashboard_empty_data_returns_contracted_empty_shape(
    container: AppContainer,
) -> None:
    async for client in _client(
        container,
        snapshotter=_FakeSnapshotter(empty=True),
        alert_engine=_FakeAlertEngine(empty=True),
    ):
        res = await client.get("/api/libraries/rag-lib/evaluation/dashboard")

    assert res.status_code == 200
    body = res.json()
    assert body["summary"] == {
        "libraryId": "rag-lib",
        "libraryName": "RAG Library",
        "datasetSummaryLabel": "No evaluation data",
        "timeRangeLabel": "Last 30 days",
        "lastRunLabel": None,
    }
    assert body["filters"] == {"datasets": [], "timeRanges": []}
    assert body["budgetAlert"] is None
    assert body["kpis"] == []
    assert body["trend"] == {
        "days": [],
        "em": [],
        "faithfulness": [],
        "citation": [],
        "latency": [],
        "legend": [],
    }
    assert body["failureCases"] == []


async def test_evaluation_dashboard_store_failures_degrade_to_empty_dashboard(
    container: AppContainer,
) -> None:
    async for client in _client(
        container,
        snapshotter=_FakeSnapshotter(failing=True),
        alert_engine=_FakeAlertEngine(failing=True),
    ):
        res = await client.get("/api/libraries/rag-lib/evaluation/dashboard")

    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["datasetSummaryLabel"] == "No evaluation data"
    assert body["budgetAlert"] is None
    assert body["kpis"] == []


async def test_evaluation_dashboard_slow_stores_degrade_to_empty_dashboard(
    container: AppContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(frontend_evaluation, "_EVAL_STORE_TIMEOUT_SECONDS", 0.01)
    async for client in _client(
        container,
        snapshotter=_HangingSnapshotter(),
        alert_engine=_HangingAlertEngine(),
    ):
        res = await client.get("/api/libraries/rag-lib/evaluation/dashboard")

    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["datasetSummaryLabel"] == "No evaluation data"
    assert body["filters"] == {"datasets": [], "timeRanges": []}
    assert body["budgetAlert"] is None
    assert body["kpis"] == []
    assert body["trend"] == {
        "days": [],
        "em": [],
        "faithfulness": [],
        "citation": [],
        "latency": [],
        "legend": [],
    }


async def test_evaluation_dashboard_rejects_invalid_dataset(client: AsyncClient) -> None:
    res = await client.get(
        "/api/libraries/rag-lib/evaluation/dashboard",
        params={"dataset": "unknown"},
    )

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Invalid evaluation dataset: unknown"


async def test_evaluation_dashboard_rejects_invalid_time_range(client: AsyncClient) -> None:
    res = await client.get(
        "/api/libraries/rag-lib/evaluation/dashboard",
        params={"timeRange": "14d"},
    )

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Invalid evaluation time range: 14d"


async def test_evaluation_dashboard_rejects_invalid_explicit_range(
    client: AsyncClient,
) -> None:
    res = await client.get(
        "/api/libraries/rag-lib/evaluation/dashboard",
        params={"from": "2026-05-28", "to": "2026-05-27"},
    )

    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Evaluation date range from must be on or before to."


async def test_evaluation_dashboard_missing_library_returns_404(client: AsyncClient) -> None:
    res = await client.get("/api/libraries/missing-lib/evaluation/dashboard")

    assert res.status_code == 404
    body = res.json()
    assert body["code"] == "LIBRARY_NOT_FOUND"
    assert body["details"] == {"library_id": "missing-lib"}
