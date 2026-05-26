"""Eval domain models for M7 dashboard (ADR-0016 + ADR-0021).

All models are pure pydantic. Computation contracts live in
`packages/orchestration/eval_protocols.py`.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ----------------------------------------------------------------------
# User feedback (ADR-0016 §AnswerFeedback)
# ----------------------------------------------------------------------


class AnswerFeedback(BaseModel):
    """User-submitted judgment on a single answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    answer_id: str = Field(min_length=1)
    user_id: str | None = None  # NULL = anonymous
    useful: bool
    citations_correct: bool
    comment: str | None = Field(default=None, max_length=2000)
    created_at: datetime
    revoked_at: datetime | None = None  # support soft revoke


# ----------------------------------------------------------------------
# KPI / Snapshot / Trend (ADR-0016 + ADR-0021)
# ----------------------------------------------------------------------


type EvalSet = Literal["smoke", "multihop", "review"]
type Metric = Literal[
    "var",
    "var_feedback",
    "var_judge",
    "citation_f1",
    "p95_latency_s",
    "avg_cost_usd",
]


class EvalKPIs(BaseModel):
    """Latest aggregate metrics for an Eval Dashboard card row."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    eval_set: EvalSet
    var: float = Field(ge=0.0, le=1.0)
    citation_f1: float = Field(ge=0.0, le=1.0)
    p95_latency_s: float = Field(ge=0.0)
    avg_cost_usd: Decimal
    delta_1d: dict[Metric, float] = Field(default_factory=dict)
    delta_7d: dict[Metric, float] = Field(default_factory=dict)
    sample_size: int = Field(ge=0)
    computed_at: datetime


class EvalSnapshot(BaseModel):
    """One row in `eval_snapshots` table — daily quantitative pin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    date: Date
    eval_set: EvalSet
    metric: Metric
    value: float
    sample_size: int = Field(ge=0)
    computed_at: datetime


# ----------------------------------------------------------------------
# Alert (ADR-0021)
# ----------------------------------------------------------------------


class AlertRule(StrEnum):
    """Stable rule names; append only."""

    VAR_DROP_5PP = "var_drop_5pp"
    CITATION_F1_DROP_5PP = "citation_f1_drop_5pp"
    P95_RISE_50PCT = "p95_rise_50pct"
    DAILY_COST_80PCT = "daily_cost_80pct"
    DAILY_COST_100PCT = "daily_cost_100pct"


type AlertStatus = Literal["active", "recovered"]
type AlertSeverity = Literal["info", "warning", "danger"]


class EvalAlert(BaseModel):
    """One row in `alerts` table.

    `notification_id` references `notifications(id)` — TEXT (ULID), per
    ADR_REVIEW R3 (overrides the UUID typo in ADR-0021).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)  # ULID
    library_id: str = Field(min_length=1)
    rule: AlertRule
    severity: AlertSeverity
    status: AlertStatus
    triggered_at: datetime
    recovered_at: datetime | None = None
    recovery_consecutive_days: int = Field(default=0, ge=0)
    payload: dict[str, object] = Field(default_factory=dict)
    notification_id: str | None = None  # FK -> notifications.id


# ----------------------------------------------------------------------
# Strategy report (ADR-0017 strategy auto-router calibration)
# ----------------------------------------------------------------------


class StrategyReport(BaseModel):
    """Compares a candidate strategy against ReAct baseline on an eval set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    strategy: str = Field(min_length=1)
    eval_set: EvalSet
    recall_at_10: float = Field(ge=0.0, le=1.0)
    citation_f1: float = Field(ge=0.0, le=1.0)
    avg_cost_usd: Decimal
    sample_size: int = Field(ge=0)
    computed_at: datetime
