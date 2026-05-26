"""Eval Dashboard endpoints (ADR-0016 + ADR-0021).

Per-Library reads:

| Method | Path                                                          |
|--------|---------------------------------------------------------------|
| GET    | ``/v1/libraries/{lib}/eval/kpis?eval_set=smoke&days=7``        |
| GET    | ``/v1/libraries/{lib}/eval/trend?metric=var&days=30``          |
| GET    | ``/v1/libraries/{lib}/eval/failures?limit=20&days=30``         |
| GET    | ``/v1/libraries/{lib}/eval/alerts?status=active``              |

Cross-Library meta-view (PRD §16.6 L5 exception, ADR-0021 §6 / §9):

| Method | Path                                                          |
|--------|---------------------------------------------------------------|
| GET    | ``/v1/eval/alerts?status=active&library_ids=...``              |

The cross-Library aggregator iterates **at the route layer** —
``AlertEngine.list_active`` deliberately accepts only one ``library_id``
per call (ADR-0003 physical isolation). Aggregation is therefore
strictly an HTTP-layer concern.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api._eval_deps import (
    get_alert_engine,
    get_eval_snapshotter,
)
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.errors import LibraryNotFoundError
from packages.orchestration.adapters.postgres_alerts import PostgresAlertEngine
from packages.orchestration.adapters.postgres_eval_snapshots import (
    PostgresEvalSnapshotter,
)
from packages.orchestration.eval_models import (
    EvalAlert,
    EvalKPIs,
    EvalSet,
    EvalSnapshot,
    Metric,
)

router_lib = APIRouter(prefix="/v1/libraries/{library_id}/eval", tags=["eval"])
router_global = APIRouter(prefix="/v1/eval", tags=["eval"])


_LIB_DESC = "Library slug"
_DEFAULT_EVAL_SET: EvalSet = "smoke"


# ----------------------------------------------------------------------
# Response shapes (kept distinct from domain models per CODING_STANDARDS §13.1)
# ----------------------------------------------------------------------


class EvalKPIsResponse(BaseModel):
    """Wire shape for the Eval Dashboard KPI cards."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str
    eval_set: EvalSet
    var: float
    citation_f1: float
    p95_latency_s: float
    avg_cost_usd: str
    delta_1d: dict[Metric, float]
    delta_7d: dict[Metric, float]
    sample_size: int
    computed_at: datetime


class EvalSnapshotResponse(BaseModel):
    """Wire shape for trend / failure rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str
    date: str
    eval_set: EvalSet
    metric: Metric
    value: float
    sample_size: int
    computed_at: datetime


class EvalAlertResponse(BaseModel):
    """Wire shape for the alerts banner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    library_id: str
    rule: str
    severity: str
    status: str
    triggered_at: datetime
    recovered_at: datetime | None
    recovery_consecutive_days: int = Field(ge=0)
    payload: dict[str, object]
    notification_id: str | None


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


async def _ensure_library(container: AppContainer, library_id: str) -> None:
    if not await container.library_repo.exists(library_id):
        raise LibraryNotFoundError(library_id)


def _to_kpi_response(kpis: EvalKPIs) -> EvalKPIsResponse:
    return EvalKPIsResponse(
        library_id=kpis.library_id,
        eval_set=kpis.eval_set,
        var=kpis.var,
        citation_f1=kpis.citation_f1,
        p95_latency_s=kpis.p95_latency_s,
        avg_cost_usd=str(kpis.avg_cost_usd),
        delta_1d=dict(kpis.delta_1d),
        delta_7d=dict(kpis.delta_7d),
        sample_size=kpis.sample_size,
        computed_at=kpis.computed_at,
    )


def _to_snapshot_response(snap: EvalSnapshot) -> EvalSnapshotResponse:
    return EvalSnapshotResponse(
        library_id=snap.library_id,
        date=snap.date.isoformat(),
        eval_set=snap.eval_set,
        metric=snap.metric,
        value=snap.value,
        sample_size=snap.sample_size,
        computed_at=snap.computed_at,
    )


def _to_alert_response(alert: EvalAlert) -> EvalAlertResponse:
    return EvalAlertResponse(
        id=alert.id,
        library_id=alert.library_id,
        rule=alert.rule.value,
        severity=alert.severity,
        status=alert.status,
        triggered_at=alert.triggered_at,
        recovered_at=alert.recovered_at,
        recovery_consecutive_days=alert.recovery_consecutive_days,
        payload=dict(alert.payload),
        notification_id=alert.notification_id,
    )


# ----------------------------------------------------------------------
# Per-Library endpoints
# ----------------------------------------------------------------------


@router_lib.get(
    "/kpis",
    response_model=EvalKPIsResponse,
    summary="Latest KPI card row for a Library + eval_set",
)
async def get_kpis(
    library_id: str = Path(..., description=_LIB_DESC),
    eval_set: EvalSet = Query(default=_DEFAULT_EVAL_SET),
    days: int = Query(default=7, ge=1, le=30),
    container: AppContainer = Depends(get_container),
    snapshots: PostgresEvalSnapshotter = Depends(get_eval_snapshotter),
    _principal: Principal = Depends(get_current_principal),
) -> EvalKPIsResponse:
    del days  # `days` is a future-proof param; current aggregator hard-codes 7d/14d
    await _ensure_library(container, library_id)
    kpis = await snapshots.get_kpis(library_id, eval_set=eval_set)
    if kpis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No eval snapshots found for library_id={library_id!r}, eval_set={eval_set!r}"
            ),
        )
    return _to_kpi_response(kpis)


@router_lib.get(
    "/trend",
    response_model=list[EvalSnapshotResponse],
    summary="Day-by-day trend for a (metric, eval_set)",
)
async def get_trend(
    library_id: str = Path(..., description=_LIB_DESC),
    metric: Metric = Query(default="var"),
    eval_set: EvalSet = Query(default=_DEFAULT_EVAL_SET),
    days: int = Query(default=30, ge=1, le=365),
    container: AppContainer = Depends(get_container),
    snapshots: PostgresEvalSnapshotter = Depends(get_eval_snapshotter),
    _principal: Principal = Depends(get_current_principal),
) -> list[EvalSnapshotResponse]:
    await _ensure_library(container, library_id)
    rows = await snapshots.get_trend(library_id, metric=metric, eval_set=eval_set, days=days)
    return [_to_snapshot_response(r) for r in rows]


@router_lib.get(
    "/failures",
    response_model=list[EvalSnapshotResponse],
    summary="Days with VAR < 0.5 — Eval Dashboard failure feed",
)
async def get_failures(
    library_id: str = Path(..., description=_LIB_DESC),
    limit: int = Query(default=20, ge=1, le=200),
    days: int = Query(default=30, ge=1, le=365),
    container: AppContainer = Depends(get_container),
    snapshots: PostgresEvalSnapshotter = Depends(get_eval_snapshotter),
    _principal: Principal = Depends(get_current_principal),
) -> list[EvalSnapshotResponse]:
    await _ensure_library(container, library_id)
    rows = await snapshots.list_failures(library_id, days=days, limit=limit)
    return [_to_snapshot_response(r) for r in rows]


@router_lib.get(
    "/alerts",
    response_model=list[EvalAlertResponse],
    summary="Eval alerts for one Library",
)
async def list_library_alerts(
    library_id: str = Path(..., description=_LIB_DESC),
    alert_status: Literal["active", "all"] = Query(default="active", alias="status"),
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=50, ge=1, le=200),
    container: AppContainer = Depends(get_container),
    engine: PostgresAlertEngine = Depends(get_alert_engine),
    _principal: Principal = Depends(get_current_principal),
) -> list[EvalAlertResponse]:
    await _ensure_library(container, library_id)
    if alert_status == "active":
        alerts = await engine.list_active(library_id)
    else:
        alerts = await engine.list_recent(library_id, days=days, limit=limit)
    return [_to_alert_response(a) for a in alerts]


# ----------------------------------------------------------------------
# Cross-Library meta-endpoint (§16.6 example)
# ----------------------------------------------------------------------


@router_global.get(
    "/alerts",
    response_model=list[EvalAlertResponse],
    summary="Cross-Library alerts aggregated at the route layer",
)
async def list_global_alerts(
    library_ids: list[str] = Query(
        default_factory=list,
        description=(
            "Repeated query param; when empty, every Library known to the metadata repo is scanned."
        ),
    ),
    alert_status: Literal["active", "all"] = Query(default="active", alias="status"),
    days: int = Query(default=30, ge=1, le=180),
    limit: int = Query(default=50, ge=1, le=200),
    container: AppContainer = Depends(get_container),
    engine: PostgresAlertEngine = Depends(get_alert_engine),
    _principal: Principal = Depends(get_current_principal),
) -> list[EvalAlertResponse]:
    """Aggregate alerts across multiple Libraries.

    Per ADR-0003 / ADR-0021 §6 the engine is per-Library; this handler
    fans out the calls and merges results. The Protocol surface
    intentionally never accepts a list — aggregation must be visible at
    the boundary.
    """
    target_ids: tuple[str, ...]
    if library_ids:
        target_ids = tuple(dict.fromkeys(library_ids))
    else:
        libs = await container.library_repo.list_all()
        target_ids = tuple(lib.library_id for lib in libs)
    aggregated: list[EvalAlertResponse] = []
    for lib_id in target_ids:
        try:
            if alert_status == "active":
                alerts = await engine.list_active(lib_id)
            else:
                alerts = await engine.list_recent(lib_id, days=days, limit=limit)
        except Exception:
            continue
        aggregated.extend(_to_alert_response(a) for a in alerts)
    aggregated.sort(key=lambda a: a.triggered_at, reverse=True)
    return aggregated[:limit]


# ----------------------------------------------------------------------
# Module-level router (FastAPI app pulls just `router`).
# ----------------------------------------------------------------------


router = APIRouter()
router.include_router(router_lib)
router.include_router(router_global)


__all__ = ["router"]
