"""Frontend-facing evaluation dashboard endpoint."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from apps._shared.factories import AppContainer
from apps.api._eval_deps import get_alert_engine, get_eval_snapshotter
from apps.api.auth import Principal, get_current_principal
from apps.api.deps import get_container
from packages.core.errors import LibraryNotFoundError
from packages.core.models import Library
from packages.orchestration.adapters.postgres_alerts import PostgresAlertEngine
from packages.orchestration.adapters.postgres_eval_snapshots import PostgresEvalSnapshotter
from packages.orchestration.eval_models import EvalAlert, EvalKPIs, EvalSnapshot, Metric

router = APIRouter(prefix="/api/libraries/{library_id}/evaluation", tags=["libraries"])

type FrontendEvaluationDataset = Literal["smoke", "multihop", "review"]
type FrontendEvaluationTimeRange = Literal["7d", "30d", "90d"]
type FrontendEvaluationAlertTone = Literal["success", "info", "warning", "danger"]
type FrontendEvaluationKpiTone = Literal["success", "secondary", "danger"]
type FrontendEvaluationLegendTone = Literal["success", "secondary", "citation", "danger"]
type FrontendEvaluationFailureTone = Literal["danger", "warning", "neutral"]

_DATASETS: tuple[FrontendEvaluationDataset, ...] = ("smoke", "multihop", "review")
_TIME_RANGES: dict[FrontendEvaluationTimeRange, int] = {"7d": 7, "30d": 30, "90d": 90}
_TREND_METRICS: tuple[Metric, ...] = ("var", "var_judge", "citation_f1", "p95_latency_s")
_EVAL_STORE_TIMEOUT_SECONDS = 1.0


@dataclass(frozen=True, slots=True)
class _TimeWindow:
    days: int
    label: str
    start: Date | None = None
    end: Date | None = None


@dataclass(frozen=True, slots=True)
class _DashboardInputs:
    library: Library
    dataset: FrontendEvaluationDataset
    days: int
    time_range_label: str
    kpis_by_dataset: Mapping[FrontendEvaluationDataset, EvalKPIs]
    trends: Mapping[Metric, tuple[EvalSnapshot, ...]]
    alerts: tuple[EvalAlert, ...]


class FrontendEvaluationSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    library_id: str = Field(alias="libraryId")
    library_name: str = Field(alias="libraryName")
    dataset_summary_label: str = Field(alias="datasetSummaryLabel")
    time_range_label: str = Field(alias="timeRangeLabel")
    last_run_label: str | None = Field(default=None, alias="lastRunLabel")


class FrontendEvaluationDatasetFilter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: FrontendEvaluationDataset
    label: str
    count: int = Field(ge=0)
    active: bool | None = None


class FrontendEvaluationTimeRangeFilter(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: FrontendEvaluationTimeRange
    label: str
    active: bool | None = None


class FrontendEvaluationFilters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    datasets: list[FrontendEvaluationDatasetFilter]
    time_ranges: list[FrontendEvaluationTimeRangeFilter] = Field(alias="timeRanges")


class FrontendEvaluationBudgetAlert(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tone: FrontendEvaluationAlertTone
    title: str
    detail: str
    action: str | None = None
    dismissible: bool | None = None


class FrontendEvaluationKpi(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    value: str
    threshold: str
    tone: FrontendEvaluationKpiTone
    points: list[float]
    icon: str | None = None


class FrontendEvaluationTrendLegendItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    tone: FrontendEvaluationLegendTone


class FrontendEvaluationTrend(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    days: list[str]
    em: list[float]
    faithfulness: list[float]
    citation: list[float]
    latency: list[float]
    legend: list[FrontendEvaluationTrendLegendItem]


class FrontendEvaluationFailureReplayContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    library_id: str = Field(alias="libraryId")
    query: str


class FrontendEvaluationFailureCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str
    dataset: str
    question: str
    failure: str
    tone: FrontendEvaluationFailureTone
    em: str
    faithfulness: str
    citation: str
    latency: str
    replay_context: FrontendEvaluationFailureReplayContext | None = Field(
        default=None, alias="replayContext"
    )


class FrontendEvaluationModels(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    router_label: str = Field(alias="routerLabel")
    embedding_label: str = Field(alias="embeddingLabel")
    warning: str | None = None


class FrontendEvaluationBudgetLimit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    label: str
    value: str


class FrontendEvaluationDataActions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    can_export: bool | None = Field(default=None, alias="canExport")
    can_purge: bool | None = Field(default=None, alias="canPurge")


class FrontendEvaluationLibrarySettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    library_label: str = Field(alias="libraryLabel")
    models: FrontendEvaluationModels
    budget_limits: list[FrontendEvaluationBudgetLimit] = Field(alias="budgetLimits")
    data_actions: FrontendEvaluationDataActions | None = Field(default=None, alias="dataActions")


class FrontendEvaluationDashboard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    summary: FrontendEvaluationSummary
    filters: FrontendEvaluationFilters
    budget_alert: FrontendEvaluationBudgetAlert | None = Field(alias="budgetAlert")
    kpis: list[FrontendEvaluationKpi]
    trend: FrontendEvaluationTrend
    failure_cases: list[FrontendEvaluationFailureCase] = Field(alias="failureCases")
    library_settings: FrontendEvaluationLibrarySettings = Field(alias="librarySettings")


@router.get(
    "/dashboard",
    response_model=FrontendEvaluationDashboard,
)
async def get_frontend_evaluation_dashboard(
    library_id: str,
    dataset: str | None = Query(default=None),
    time_range: str | None = Query(default="30d", alias="timeRange"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    container: AppContainer = Depends(get_container),
    snapshots: PostgresEvalSnapshotter = Depends(get_eval_snapshotter),
    alerts: PostgresAlertEngine = Depends(get_alert_engine),
    _principal: Principal = Depends(get_current_principal),
) -> FrontendEvaluationDashboard:
    library = await _get_library(container, library_id)
    selected_dataset = _parse_dataset(dataset)
    window = _parse_time_window(time_range, from_date, to_date)
    inputs = await _load_dashboard_inputs(
        library=library,
        dataset=selected_dataset,
        window=window,
        snapshots=snapshots,
        alerts=alerts,
    )
    active_time_range = None if window.start is not None else time_range
    return _dashboard_from_inputs(container, inputs, active_time_range)


async def _get_library(container: AppContainer, library_id: str) -> Library:
    library = await container.library_repo.get(library_id)
    if library is None:
        raise LibraryNotFoundError(library_id)
    return library


def _parse_dataset(raw: str | None) -> FrontendEvaluationDataset:
    if raw is None or raw.strip() == "":
        return "smoke"
    value = raw.strip().lower()
    if value not in _DATASETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid evaluation dataset: {raw}",
        )
    return value  # type: ignore[return-value]


def _parse_time_window(
    raw_time_range: str | None,
    raw_from: str | None,
    raw_to: str | None,
) -> _TimeWindow:
    if raw_from is not None or raw_to is not None:
        if raw_from is None or raw_to is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both from and to dates are required for explicit evaluation ranges.",
            )
        start = _parse_iso_date(raw_from, label="from")
        end = _parse_iso_date(raw_to, label="to")
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Evaluation date range from must be on or before to.",
            )
        days = (end - start).days + 1
        if days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Evaluation date ranges cannot exceed 365 days.",
            )
        return _TimeWindow(
            days=365,
            label=f"{start.isoformat()} to {end.isoformat()}",
            start=start,
            end=end,
        )

    value = (raw_time_range or "30d").strip().lower()
    if value not in _TIME_RANGES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid evaluation time range: {raw_time_range}",
        )
    return _TimeWindow(days=_TIME_RANGES[value], label=_time_range_label(value))


def _parse_iso_date(raw: str, *, label: str) -> Date:
    try:
        return Date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid evaluation {label} date: {raw}",
        ) from exc


async def _load_dashboard_inputs(
    *,
    library: Library,
    dataset: FrontendEvaluationDataset,
    window: _TimeWindow,
    snapshots: PostgresEvalSnapshotter,
    alerts: PostgresAlertEngine,
) -> _DashboardInputs:
    kpis_task = _safe_load_dataset_kpis(snapshots, library.library_id)
    trends_task = _safe_load_trends(
        snapshots,
        library.library_id,
        eval_set=dataset,
        window=window,
    )
    alerts_task = _safe_list_alerts(alerts, library.library_id)
    kpis_by_dataset, trends, active_alerts = await asyncio.gather(
        kpis_task,
        trends_task,
        alerts_task,
    )
    return _DashboardInputs(
        library=library,
        dataset=dataset,
        days=window.days,
        time_range_label=window.label,
        kpis_by_dataset=kpis_by_dataset,
        trends=trends,
        alerts=active_alerts,
    )


async def _safe_eval_call[T](awaitable: Awaitable[T]) -> T | None:
    try:
        return await asyncio.wait_for(awaitable, timeout=_EVAL_STORE_TIMEOUT_SECONDS)
    except Exception:
        return None


async def _safe_load_dataset_kpis(
    snapshots: PostgresEvalSnapshotter,
    library_id: str,
) -> dict[FrontendEvaluationDataset, EvalKPIs]:
    async def _load_one(
        dataset: FrontendEvaluationDataset,
    ) -> tuple[FrontendEvaluationDataset, EvalKPIs | None]:
        kpis = await _safe_eval_call(snapshots.get_kpis(library_id, eval_set=dataset))
        return dataset, kpis

    results = await asyncio.gather(*(_load_one(dataset) for dataset in _DATASETS))
    return {dataset: kpis for dataset, kpis in results if kpis is not None}


async def _safe_load_trends(
    snapshots: PostgresEvalSnapshotter,
    library_id: str,
    *,
    eval_set: FrontendEvaluationDataset,
    window: _TimeWindow,
) -> dict[Metric, tuple[EvalSnapshot, ...]]:
    async def _load_one(metric: Metric) -> tuple[Metric, tuple[EvalSnapshot, ...]]:
        rows = await _safe_eval_call(
            snapshots.get_trend(
                library_id,
                metric=metric,
                eval_set=eval_set,
                days=window.days,
            )
        )
        return metric, _filter_rows_for_window(tuple(rows or ()), window)

    return dict(await asyncio.gather(*(_load_one(metric) for metric in _TREND_METRICS)))


def _filter_rows_for_window(
    rows: tuple[EvalSnapshot, ...],
    window: _TimeWindow,
) -> tuple[EvalSnapshot, ...]:
    if window.start is None or window.end is None:
        return rows
    return tuple(row for row in rows if window.start <= row.date <= window.end)


async def _safe_list_alerts(
    alerts: PostgresAlertEngine,
    library_id: str,
) -> tuple[EvalAlert, ...]:
    return tuple((await _safe_eval_call(alerts.list_active(library_id))) or ())


def _dashboard_from_inputs(
    container: AppContainer,
    inputs: _DashboardInputs,
    raw_time_range: str | None,
) -> FrontendEvaluationDashboard:
    has_eval_data = _has_eval_data(inputs)
    return FrontendEvaluationDashboard(
        summary=_summary_from_inputs(inputs, has_eval_data=has_eval_data),
        filters=_filters_from_inputs(
            inputs,
            has_eval_data=has_eval_data,
            raw_time_range=raw_time_range,
        ),
        budgetAlert=_budget_alert(inputs.alerts),
        kpis=_kpis_from_inputs(inputs) if has_eval_data else [],
        trend=_trend_from_inputs(inputs) if has_eval_data else _empty_trend(),
        failureCases=[],
        librarySettings=_library_settings(container, inputs.library),
    )


def _has_eval_data(inputs: _DashboardInputs) -> bool:
    if inputs.kpis_by_dataset:
        return True
    return any(inputs.trends.get(metric) for metric in _TREND_METRICS)


def _summary_from_inputs(
    inputs: _DashboardInputs,
    *,
    has_eval_data: bool,
) -> FrontendEvaluationSummary:
    selected_kpis = inputs.kpis_by_dataset.get(inputs.dataset)
    last_run = _last_run_label(selected_kpis, inputs.trends)
    return FrontendEvaluationSummary(
        libraryId=inputs.library.library_id,
        libraryName=inputs.library.name,
        datasetSummaryLabel=_dataset_summary_label(inputs.kpis_by_dataset)
        if has_eval_data
        else "No evaluation data",
        timeRangeLabel=inputs.time_range_label,
        lastRunLabel=last_run,
    )


def _filters_from_inputs(
    inputs: _DashboardInputs,
    *,
    has_eval_data: bool,
    raw_time_range: str | None,
) -> FrontendEvaluationFilters:
    if not has_eval_data:
        return FrontendEvaluationFilters(datasets=[], timeRanges=[])
    active_time_range = raw_time_range.strip().lower() if raw_time_range else None
    return FrontendEvaluationFilters(
        datasets=[
            FrontendEvaluationDatasetFilter(
                key=dataset,
                label=_dataset_label(dataset),
                count=_dataset_sample_size(inputs.kpis_by_dataset, dataset),
                active=dataset == inputs.dataset,
            )
            for dataset in _DATASETS
        ],
        timeRanges=[
            FrontendEvaluationTimeRangeFilter(
                key=time_range,
                label=_time_range_label(time_range),
                active=time_range == active_time_range,
            )
            for time_range in _TIME_RANGES
        ],
    )


def _dataset_sample_size(
    kpis_by_dataset: Mapping[FrontendEvaluationDataset, EvalKPIs],
    dataset: FrontendEvaluationDataset,
) -> int:
    kpis = kpis_by_dataset.get(dataset)
    if kpis is None:
        return 0
    return kpis.sample_size


def _budget_alert(alerts: tuple[EvalAlert, ...]) -> FrontendEvaluationBudgetAlert | None:
    if not alerts:
        return None
    alert = alerts[0]
    return FrontendEvaluationBudgetAlert(
        tone=_alert_tone(alert.severity),
        title=_alert_title(alert),
        detail=_alert_detail(alert),
        action="Review evaluation settings",
        dismissible=False,
    )


def _kpis_from_inputs(inputs: _DashboardInputs) -> list[FrontendEvaluationKpi]:
    selected = inputs.kpis_by_dataset.get(inputs.dataset)
    cards: list[FrontendEvaluationKpi] = []
    if selected is not None:
        cards.append(
            FrontendEvaluationKpi(
                title="Answer relevancy EM@1",
                value=_score_value(selected.var),
                threshold="(>= 0.80)",
                tone=_score_tone(selected.var, warn=0.8, danger=0.5),
                points=_metric_points(
                    inputs.trends.get("var", ()),
                    normalize=False,
                    fallback=selected.var,
                ),
            )
        )
        cards.append(
            FrontendEvaluationKpi(
                title="Citation precision C@1",
                value=_score_value(selected.citation_f1),
                threshold="(>= 0.80)",
                tone=_score_tone(selected.citation_f1, warn=0.8, danger=0.5),
                points=_metric_points(
                    inputs.trends.get("citation_f1", ()),
                    normalize=False,
                    fallback=selected.citation_f1,
                ),
            )
        )
        latency_point = _latency_point(selected.p95_latency_s)
        cards.append(
            FrontendEvaluationKpi(
                title="Latency p95",
                value=f"{selected.p95_latency_s:.2f}s",
                threshold="(<= 4.00s)",
                tone="danger" if selected.p95_latency_s > 4.0 else "success",
                points=_metric_points(
                    inputs.trends.get("p95_latency_s", ()),
                    normalize=True,
                    fallback=latency_point,
                ),
                icon="timer",
            )
        )
    faithfulness = _latest_value(inputs.trends.get("var_judge", ()))
    if faithfulness is not None:
        cards.insert(
            1,
            FrontendEvaluationKpi(
                title="Faithfulness FactScore",
                value=_score_value(faithfulness),
                threshold="(>= 0.85)",
                tone=_score_tone(faithfulness, warn=0.85, danger=0.5),
                points=_metric_points(inputs.trends.get("var_judge", ()), normalize=False),
            ),
        )
    return cards


def _trend_from_inputs(inputs: _DashboardInputs) -> FrontendEvaluationTrend:
    rows_by_metric = inputs.trends
    ordered_days = sorted(
        {row.date for metric in _TREND_METRICS for row in rows_by_metric.get(metric, ())}
    )
    if not ordered_days:
        return _empty_trend()
    labels = [_day_label(day) for day in ordered_days]
    return FrontendEvaluationTrend(
        days=labels,
        em=_values_for_days(rows_by_metric.get("var", ()), ordered_days, normalize=False),
        faithfulness=_values_for_days(
            rows_by_metric.get("var_judge", ()), ordered_days, normalize=False
        ),
        citation=_values_for_days(
            rows_by_metric.get("citation_f1", ()), ordered_days, normalize=False
        ),
        latency=_values_for_days(
            rows_by_metric.get("p95_latency_s", ()), ordered_days, normalize=True
        ),
        legend=[
            FrontendEvaluationTrendLegendItem(label="EM@1", tone="success"),
            FrontendEvaluationTrendLegendItem(label="Faithfulness", tone="secondary"),
            FrontendEvaluationTrendLegendItem(label="C@1", tone="citation"),
            FrontendEvaluationTrendLegendItem(label="Latency p95", tone="danger"),
        ],
    )


def _empty_trend() -> FrontendEvaluationTrend:
    return FrontendEvaluationTrend(
        days=[],
        em=[],
        faithfulness=[],
        citation=[],
        latency=[],
        legend=[],
    )


def _library_settings(
    container: AppContainer,
    library: Library,
) -> FrontendEvaluationLibrarySettings:
    settings = container.settings
    return FrontendEvaluationLibrarySettings(
        libraryLabel=library.name,
        models=FrontendEvaluationModels(
            routerLabel=f"Router: {settings.planner}",
            embeddingLabel=f"{settings.embedding_model} ({settings.embedding_dim}d)",
        ),
        budgetLimits=[
            FrontendEvaluationBudgetLimit(
                key="maxInputTokens",
                label="LLM input tokens",
                value=f"{settings.react_max_input_tokens:,}",
            ),
            FrontendEvaluationBudgetLimit(
                key="maxOutputTokens",
                label="LLM output tokens",
                value=f"{settings.react_max_output_tokens:,}",
            ),
            FrontendEvaluationBudgetLimit(
                key="maxLlmCalls",
                label="Max LLM calls",
                value=str(settings.react_max_llm_calls),
            ),
            FrontendEvaluationBudgetLimit(
                key="maxSteps",
                label="Max retrieval steps",
                value=str(settings.react_max_steps),
            ),
        ],
        dataActions=FrontendEvaluationDataActions(canExport=True, canPurge=True),
    )


def _dataset_summary_label(kpis_by_dataset: Mapping[FrontendEvaluationDataset, EvalKPIs]) -> str:
    parts = [
        f"{_dataset_label(dataset).lower()} ({kpis.sample_size})"
        for dataset, kpis in kpis_by_dataset.items()
    ]
    return " · ".join(parts) if parts else "No evaluation data"


def _last_run_label(
    kpis: EvalKPIs | None,
    trends: Mapping[Metric, tuple[EvalSnapshot, ...]],
) -> str | None:
    timestamps: list[datetime] = []
    if kpis is not None:
        timestamps.append(kpis.computed_at)
    for rows in trends.values():
        timestamps.extend(row.computed_at for row in rows)
    if not timestamps:
        return None
    latest = max(timestamps)
    return f"Updated {latest.date().isoformat()}"


def _score_tone(value: float, *, warn: float, danger: float) -> FrontendEvaluationKpiTone:
    if value < danger:
        return "danger"
    if value >= warn:
        return "success"
    return "secondary"


def _score_value(value: float) -> str:
    return f"{value:.3f}"


def _metric_points(
    rows: tuple[EvalSnapshot, ...],
    *,
    normalize: bool,
    fallback: float | None = None,
) -> list[float]:
    values = [_display_metric_value(row.value, normalize=normalize) for row in rows]
    if values:
        return values
    if fallback is None:
        return []
    return [round(fallback, 4)]


def _latest_value(rows: tuple[EvalSnapshot, ...]) -> float | None:
    if not rows:
        return None
    return max(rows, key=lambda row: row.date).value


def _values_for_days(
    rows: tuple[EvalSnapshot, ...],
    days: list[Date],
    *,
    normalize: bool,
) -> list[float]:
    by_day = {row.date: row.value for row in rows}
    return [_display_metric_value(by_day.get(day, 0.0), normalize=normalize) for day in days]


def _display_metric_value(value: float, *, normalize: bool) -> float:
    if normalize:
        return _latency_point(value)
    return round(max(0.0, min(value, 1.0)), 4)


def _latency_point(seconds: float) -> float:
    return round(max(0.0, min(seconds / 4.0, 1.0)), 4)


def _alert_tone(severity: str) -> FrontendEvaluationAlertTone:
    if severity == "danger":
        return "danger"
    if severity == "warning":
        return "warning"
    return "info"


def _alert_title(alert: EvalAlert) -> str:
    rule = alert.rule.value.replace("_", " ")
    return f"Evaluation alert: {rule}"


def _alert_detail(alert: EvalAlert) -> str:
    metric = alert.payload.get("metric")
    delta = alert.payload.get("delta_pp")
    if isinstance(metric, str) and isinstance(delta, (int, float)):
        return f"{metric} changed by {float(delta):.1f}pp."
    return "An evaluation guardrail is active for this library."


def _day_label(day: Date) -> str:
    return f"{day.strftime('%b')} {day.day}"


def _dataset_label(dataset: FrontendEvaluationDataset) -> str:
    labels: dict[FrontendEvaluationDataset, str] = {
        "smoke": "Smoke",
        "multihop": "Multihop",
        "review": "Review",
    }
    return labels[dataset]


def _time_range_label(time_range: str) -> str:
    labels = {"7d": "Last 7 days", "30d": "Last 30 days", "90d": "Last 90 days"}
    return labels.get(time_range, time_range)
