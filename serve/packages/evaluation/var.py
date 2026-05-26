"""VAR (Valid Answer Rate) computer (ADR-0016).

Public surface is intentionally tiny — `VARComputer` Protocol shipped from
`packages.orchestration.eval_protocols` requires only `compute(...)`. The
DefaultVARComputer below also exposes the three-tier breakdown
(`var_feedback`, `var_judge`, `var_blended`) so the dashboard endpoint can
render the side-by-side numbers required by ADR-0016 §1.

The computer is purely a query layer; it never *generates* judge data —
that's `DailyEvalSnapshotter.write_daily` (see `packages/evaluation/snapshot.py`).
This separation keeps reads cheap and writes scheduled.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog

from packages.evaluation._internal.var_blend import (
    DEFAULT_WINDOW_DAYS,
    N_FEEDBACK_FULL_TRUST,
    blend,
)
from packages.observability import with_span
from packages.orchestration.eval_models import AnswerFeedback, EvalSet, EvalSnapshot
from packages.orchestration.eval_protocols import EvalSnapshotter, FeedbackStore

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class VARBreakdown:
    """Three-tier VAR view for the Eval Dashboard.

    All three numbers are always present (None means "no data") so the UI
    can render `feedback / judge / blended` columns uniformly.
    """

    blended: float
    feedback: float | None
    judge: float | None
    n_feedback: int
    n_judge: int
    weight_feedback: float


class DefaultVARComputer:
    """Computes VAR over a sliding window from feedback + snapshots.

    `compute(library_id, ...)` — Protocol method — returns the blended scalar.
    `compute_breakdown(...)` returns the full structured view for the
    Dashboard endpoint.
    """

    def __init__(
        self,
        *,
        feedback_store: FeedbackStore,
        snapshots: EvalSnapshotter,
        n_full_trust: int = N_FEEDBACK_FULL_TRUST,
    ) -> None:
        self._feedback = feedback_store
        self._snapshots = snapshots
        self._n_full_trust = n_full_trust

    async def compute(
        self,
        library_id: str,
        *,
        eval_set: EvalSet = "smoke",
        days: int = DEFAULT_WINDOW_DAYS,
    ) -> float:
        """VAR Protocol entry — returns the blended scalar."""
        breakdown = await self.compute_breakdown(library_id, eval_set=eval_set, days=days)
        return breakdown.blended

    async def compute_breakdown(
        self,
        library_id: str,
        *,
        eval_set: EvalSet = "smoke",
        days: int = DEFAULT_WINDOW_DAYS,
        now: datetime | None = None,
    ) -> VARBreakdown:
        """Three-tier VAR view (feedback / judge / blended)."""
        async with with_span("evaluation.compute_var", library_id=library_id):
            current_now = now or datetime.now().astimezone()
            since = current_now - timedelta(days=days)

            feedback = await self._feedback.list_for_library(library_id, since=since, limit=10_000)
            var_fb, n_fb = _compute_feedback_var(feedback)

            judge_snapshots = await self._snapshots.get_trend(
                library_id, metric="var_judge", eval_set=eval_set, days=days
            )
            var_judge, n_judge = _compute_judge_var(judge_snapshots)

            blended = blend(var_fb, var_judge, n_fb, n_full_trust=self._n_full_trust)
            weight_fb = min(1.0, n_fb / self._n_full_trust) if n_fb > 0 else 0.0
            return VARBreakdown(
                blended=blended,
                feedback=var_fb,
                judge=var_judge,
                n_feedback=n_fb,
                n_judge=n_judge,
                weight_feedback=weight_fb,
            )


def _compute_feedback_var(
    feedback: Sequence[AnswerFeedback],
) -> tuple[float | None, int]:
    """ADR-0016 §3 var_feedback formula.

    Denominator excludes revoked rows (already handled by `list_for_library`
    if the adapter filters; we re-filter here for safety).
    """
    valid = tuple(f for f in feedback if f.revoked_at is None)
    if not valid:
        return None, 0
    hits = sum(1 for f in valid if f.useful and f.citations_correct)
    return hits / len(valid), len(valid)


def _compute_judge_var(
    snapshots: Sequence[EvalSnapshot],
) -> tuple[float | None, int]:
    """Compute judge VAR from daily snapshots (metric='var_judge').

    Each snapshot.value is the day's mean (already averaged at write time);
    we take the sample-size-weighted mean to honour days with more samples.
    Refused tasks counted in denominator — the snapshot writer is
    responsible for that, ADR-0016 §3 §"Refused tasks count".
    """
    if not snapshots:
        return None, 0
    total_n = sum(s.sample_size for s in snapshots)
    if total_n == 0:
        return None, 0
    weighted = sum(s.value * s.sample_size for s in snapshots)
    return weighted / total_n, total_n


__all__ = [
    "DEFAULT_WINDOW_DAYS",
    "N_FEEDBACK_FULL_TRUST",
    "DefaultVARComputer",
    "VARBreakdown",
]
