"""Eval alerting engine (ADR-0021).

Five rules at v1:

  * VAR_DROP_5PP            — current 7-day VAR  vs prior 7-day  ≤ -5pp
  * CITATION_F1_DROP_5PP    — current 7-day Cit. F1            ≤ -5pp
  * P95_RISE_50PCT          — current 7-day P95 / prior         ≥ +50%
  * DAILY_COST_80PCT         — today's cost ≥ 80% of cap
  * DAILY_COST_100PCT        — today's cost ≥ 100% of cap

Cold-start (ADR-0021 §7): the first 14 days after Library creation skip the
weekly-comparison rules (only daily cost rules fire). Days 0..6 are pure
silent (previous_window has no data); days 7..13 evaluate but only LOG —
no `alerts` row, no notification.

Sample-size guard (ADR-0021 §8): weekly rules require ≥ 30 evaluation
samples in `current_window`. Below that, the rule logs `not_enough_data`
and does not trigger.

Recovery (ADR-0021 §4): a rule must satisfy its `is_recovered_today`
predicate on **2 consecutive days** before the active alert flips to
`recovered`. The recovered transition writes one ALERT_RECOVERED
notification (severity=info), per ADR-0011 contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

import structlog

from packages.evaluation._internal.var_blend import MIN_SAMPLE_SIZE_FOR_ALERT
from packages.orchestration.cost import CostCheckResult
from packages.orchestration.eval_models import (
    AlertRule,
    AlertSeverity,
    EvalAlert,
    EvalSnapshot,
    Metric,
)

logger = structlog.get_logger(__name__)

# ADR-0021 §7
COLD_START_DAYS: int = 14
COLD_START_WEEKLY_RULE_SILENT_DAYS: int = 7

# ADR-0021 §1 thresholds
VAR_DROP_THRESHOLD_PP: float = -5.0
CITATION_F1_DROP_THRESHOLD_PP: float = -5.0
P95_RISE_FACTOR: float = 1.5  # 1 + 50%
DAILY_COST_WARN_PCT: float = 0.80
DAILY_COST_BLOCK_PCT: float = 1.00

# Recovery thresholds (ADR-0021 §4 table)
VAR_RECOVERY_TOLERANCE_PP: float = -2.0  # within 2pp of previous
CITATION_F1_RECOVERY_TOLERANCE_PP: float = -2.0
P95_RECOVERY_FACTOR: float = 1.2
DAILY_COST_WARN_RECOVERY_PCT: float = 0.70  # 5pp hysteresis
DAILY_COST_BLOCK_RECOVERY_PCT: float = 0.90


# ----------------------------------------------------------------------
# Outcome ADT
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TriggerOutcome:
    """Rule wants to trigger (or refresh) an alert with this payload."""

    rule: AlertRule
    severity: AlertSeverity
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class OkOutcome:
    """Metric is healthy this run."""

    rule: AlertRule


@dataclass(frozen=True, slots=True)
class SkipOutcome:
    """Cannot evaluate this run; no state change."""

    rule: AlertRule
    reason: str
    detail: dict[str, object]


type Outcome = TriggerOutcome | OkOutcome | SkipOutcome


# ----------------------------------------------------------------------
# Library context
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LibraryAlertContext:
    """Inputs needed by every rule for a single (library, day) evaluation."""

    library_id: str
    library_created_at: datetime
    today: Date
    snapshots: tuple[EvalSnapshot, ...]
    cost_today: CostCheckResult | None


# ----------------------------------------------------------------------
# Rule Protocol
# ----------------------------------------------------------------------


class RuleEngine(Protocol):
    """Single rule contract — pure function over context."""

    rule: AlertRule
    severity: AlertSeverity

    def evaluate(self, ctx: LibraryAlertContext) -> Outcome: ...

    def is_recovered_today(self, active: EvalAlert, ctx: LibraryAlertContext) -> bool: ...


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _slice(
    snapshots: Sequence[EvalSnapshot],
    metric: Metric,
    *,
    start: Date,
    end_exclusive: Date,
) -> tuple[EvalSnapshot, ...]:
    return tuple(s for s in snapshots if s.metric == metric and start <= s.date < end_exclusive)


def _weighted_mean(rows: Sequence[EvalSnapshot]) -> float | None:
    total_n = sum(s.sample_size for s in rows)
    if total_n == 0:
        return None
    return sum(s.value * s.sample_size for s in rows) / total_n


def _is_cold_start_silent(ctx: LibraryAlertContext) -> bool:
    """First 7 days — no weekly comparisons evaluated at all."""
    days_alive = (ctx.today - ctx.library_created_at.date()).days
    return days_alive < COLD_START_WEEKLY_RULE_SILENT_DAYS


# ----------------------------------------------------------------------
# Concrete rules
# ----------------------------------------------------------------------


class _MetricDropRule:
    """Shared logic for VAR / Citation F1 weekly drop rules."""

    rule: AlertRule
    severity: AlertSeverity
    _metric: Metric
    _threshold_pp: float
    _recovery_tolerance_pp: float

    def __init__(
        self,
        *,
        rule: AlertRule,
        metric: Metric,
        severity: AlertSeverity,
        threshold_pp: float,
        recovery_tolerance_pp: float,
    ) -> None:
        self.rule = rule
        self.severity = severity
        self._metric = metric
        self._threshold_pp = threshold_pp
        self._recovery_tolerance_pp = recovery_tolerance_pp

    def evaluate(self, ctx: LibraryAlertContext) -> Outcome:
        if _is_cold_start_silent(ctx):
            return SkipOutcome(
                rule=self.rule,
                reason="cold_start",
                detail={"days_alive": (ctx.today - ctx.library_created_at.date()).days},
            )

        current = _slice(
            ctx.snapshots,
            self._metric,
            start=ctx.today - timedelta(days=7),
            end_exclusive=ctx.today,
        )
        previous = _slice(
            ctx.snapshots,
            self._metric,
            start=ctx.today - timedelta(days=14),
            end_exclusive=ctx.today - timedelta(days=7),
        )
        sample_size = sum(s.sample_size for s in current)
        if sample_size < MIN_SAMPLE_SIZE_FOR_ALERT:
            return SkipOutcome(
                rule=self.rule,
                reason="not_enough_data",
                detail={
                    "sample_size": sample_size,
                    "min_required": MIN_SAMPLE_SIZE_FOR_ALERT,
                },
            )
        cur_value = _weighted_mean(current)
        prev_value = _weighted_mean(previous)
        if cur_value is None or prev_value is None:
            return SkipOutcome(rule=self.rule, reason="missing_window_data", detail={})
        delta_pp = (cur_value - prev_value) * 100.0
        if delta_pp <= self._threshold_pp:
            return TriggerOutcome(
                rule=self.rule,
                severity=self.severity,
                payload={
                    "metric": self._metric,
                    "current_value": cur_value,
                    "previous_value": prev_value,
                    "delta_pp": delta_pp,
                    "threshold_pp": self._threshold_pp,
                    "current_window_start": (ctx.today - timedelta(days=7)).isoformat(),
                    "current_window_end": ctx.today.isoformat(),
                    "sample_size": sample_size,
                    "min_sample_size_required": MIN_SAMPLE_SIZE_FOR_ALERT,
                },
            )
        return OkOutcome(rule=self.rule)

    def is_recovered_today(self, active: EvalAlert, ctx: LibraryAlertContext) -> bool:
        previous_value_obj = active.payload.get("previous_value")
        if not isinstance(previous_value_obj, (int, float)):
            return False
        baseline = float(previous_value_obj)
        current = _slice(
            ctx.snapshots,
            self._metric,
            start=ctx.today - timedelta(days=7),
            end_exclusive=ctx.today,
        )
        cur_value = _weighted_mean(current)
        if cur_value is None:
            return False
        return (cur_value - baseline) * 100.0 >= self._recovery_tolerance_pp


class _P95RiseRule:
    """ADR-0021 §1 — P95 latency rose ≥ 50% week-over-week."""

    rule: AlertRule = AlertRule.P95_RISE_50PCT
    severity: AlertSeverity = "warning"

    def evaluate(self, ctx: LibraryAlertContext) -> Outcome:
        if _is_cold_start_silent(ctx):
            return SkipOutcome(
                rule=self.rule,
                reason="cold_start",
                detail={"days_alive": (ctx.today - ctx.library_created_at.date()).days},
            )
        current = _slice(
            ctx.snapshots,
            "p95_latency_s",
            start=ctx.today - timedelta(days=7),
            end_exclusive=ctx.today,
        )
        previous = _slice(
            ctx.snapshots,
            "p95_latency_s",
            start=ctx.today - timedelta(days=14),
            end_exclusive=ctx.today - timedelta(days=7),
        )
        sample_size = sum(s.sample_size for s in current)
        if sample_size < MIN_SAMPLE_SIZE_FOR_ALERT:
            return SkipOutcome(
                rule=self.rule,
                reason="not_enough_data",
                detail={
                    "sample_size": sample_size,
                    "min_required": MIN_SAMPLE_SIZE_FOR_ALERT,
                },
            )
        cur_value = _weighted_mean(current)
        prev_value = _weighted_mean(previous)
        if cur_value is None or prev_value is None or prev_value <= 0:
            return SkipOutcome(rule=self.rule, reason="missing_window_data", detail={})
        ratio = cur_value / prev_value
        if ratio >= P95_RISE_FACTOR:
            return TriggerOutcome(
                rule=self.rule,
                severity=self.severity,
                payload={
                    "metric": "p95_latency_s",
                    "current_value": cur_value,
                    "previous_value": prev_value,
                    "ratio": ratio,
                    "threshold_factor": P95_RISE_FACTOR,
                    "sample_size": sample_size,
                },
            )
        return OkOutcome(rule=self.rule)

    def is_recovered_today(self, active: EvalAlert, ctx: LibraryAlertContext) -> bool:
        previous_value_obj = active.payload.get("previous_value")
        if not isinstance(previous_value_obj, (int, float)) or previous_value_obj <= 0:
            return False
        baseline = float(previous_value_obj)
        current = _slice(
            ctx.snapshots,
            "p95_latency_s",
            start=ctx.today - timedelta(days=7),
            end_exclusive=ctx.today,
        )
        cur_value = _weighted_mean(current)
        if cur_value is None:
            return False
        return cur_value / baseline <= P95_RECOVERY_FACTOR


class _DailyCostRule:
    """80% / 100% daily cost cap rules — share evaluate / recover logic."""

    rule: AlertRule
    severity: AlertSeverity
    _warn_pct: float
    _recovery_pct: float

    def __init__(
        self,
        *,
        rule: AlertRule,
        severity: AlertSeverity,
        warn_pct: float,
        recovery_pct: float,
    ) -> None:
        self.rule = rule
        self.severity = severity
        self._warn_pct = warn_pct
        self._recovery_pct = recovery_pct

    def evaluate(self, ctx: LibraryAlertContext) -> Outcome:
        if ctx.cost_today is None or ctx.cost_today.cap_usd is None:
            return SkipOutcome(rule=self.rule, reason="no_cost_cap_configured", detail={})
        cap = ctx.cost_today.cap_usd
        if cap <= 0:
            return SkipOutcome(rule=self.rule, reason="no_cost_cap_configured", detail={})
        spent = ctx.cost_today.spent_usd
        pct = float(spent) / float(cap)
        if pct >= self._warn_pct:
            return TriggerOutcome(
                rule=self.rule,
                severity=self.severity,
                payload={
                    "metric": "avg_cost_usd",
                    "spent_usd": str(spent),
                    "cap_usd": str(cap),
                    "pct_used": pct,
                    "warn_pct": self._warn_pct,
                },
            )
        return OkOutcome(rule=self.rule)

    def is_recovered_today(self, active: EvalAlert, ctx: LibraryAlertContext) -> bool:
        del active
        if ctx.cost_today is None or ctx.cost_today.cap_usd is None:
            return False
        cap = ctx.cost_today.cap_usd
        if cap <= 0:
            return False
        pct = float(ctx.cost_today.spent_usd) / float(cap)
        return pct < self._recovery_pct


# ----------------------------------------------------------------------
# Default rule set
# ----------------------------------------------------------------------


def default_rules() -> tuple[RuleEngine, ...]:
    """Five v1 rules, in evaluation order (ADR-0021 §1)."""
    rules: tuple[RuleEngine, ...] = (
        _MetricDropRule(
            rule=AlertRule.VAR_DROP_5PP,
            metric="var",
            severity="danger",
            threshold_pp=VAR_DROP_THRESHOLD_PP,
            recovery_tolerance_pp=VAR_RECOVERY_TOLERANCE_PP,
        ),
        _MetricDropRule(
            rule=AlertRule.CITATION_F1_DROP_5PP,
            metric="citation_f1",
            severity="warning",
            threshold_pp=CITATION_F1_DROP_THRESHOLD_PP,
            recovery_tolerance_pp=CITATION_F1_RECOVERY_TOLERANCE_PP,
        ),
        _P95RiseRule(),
        _DailyCostRule(
            rule=AlertRule.DAILY_COST_80PCT,
            severity="warning",
            warn_pct=DAILY_COST_WARN_PCT,
            recovery_pct=DAILY_COST_WARN_RECOVERY_PCT,
        ),
        _DailyCostRule(
            rule=AlertRule.DAILY_COST_100PCT,
            severity="danger",
            warn_pct=DAILY_COST_BLOCK_PCT,
            recovery_pct=DAILY_COST_BLOCK_RECOVERY_PCT,
        ),
    )
    return rules


# ----------------------------------------------------------------------
# Engine façade
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AlertEvaluationReport:
    """Per-library outcome of an alert evaluation pass."""

    library_id: str
    triggered: tuple[EvalAlert, ...]
    refreshed: tuple[EvalAlert, ...]
    recovered: tuple[EvalAlert, ...]
    skipped: tuple[SkipOutcome, ...]


def cap_decimal(cap: Decimal | None) -> Decimal | None:
    """Pass-through for `Decimal | None` to keep mypy happy in callers."""
    return cap


__all__ = [
    "CITATION_F1_DROP_THRESHOLD_PP",
    "COLD_START_DAYS",
    "COLD_START_WEEKLY_RULE_SILENT_DAYS",
    "DAILY_COST_BLOCK_PCT",
    "DAILY_COST_BLOCK_RECOVERY_PCT",
    "DAILY_COST_WARN_PCT",
    "DAILY_COST_WARN_RECOVERY_PCT",
    "P95_RECOVERY_FACTOR",
    "P95_RISE_FACTOR",
    "VAR_DROP_THRESHOLD_PP",
    "VAR_RECOVERY_TOLERANCE_PP",
    "AlertEvaluationReport",
    "LibraryAlertContext",
    "OkOutcome",
    "Outcome",
    "RuleEngine",
    "SkipOutcome",
    "TriggerOutcome",
    "default_rules",
]
