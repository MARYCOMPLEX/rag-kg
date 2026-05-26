"""Daily eval snapshot writer (ADR-0016 §5 + BACKEND_ROADMAP §3.8 Gap 1).

Run by the worker cron at 02:00 UTC. For each Library + eval_set, writes one
row per metric into the `eval_snapshots` table:

  * `var_judge` — mean of dual-judge agreed `useful AND citations_correct`
    over the day's QA samples (ADR-0016 §4).
  * `citation_f1` — pulled from `EvalRunner.run_suite` aggregate.
  * `p95_latency_s` — 95th percentile of answer latencies.
  * `avg_cost_usd` — mean per-answer cost.

Refused tasks (cost-blocked, ADR-0015) counted as `useful=False,
citations_correct=False` (ADR-0016 §3).

The writer is **stateless** — pass it a small `DailyJudgeSamples` source
that yields (sample_id, question, answer, refused, latency_s, cost_usd)
tuples. In production this source comes from L5 orchestration's
`AnsweredQuery` log; in tests we substitute a fake.
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as Date
from typing import Protocol

import structlog

from packages.evaluation._internal.llm_judge import (
    JUDGE_PROMPT_VERSION,
    DualLLMJudge,
)
from packages.evaluation._internal.var_blend import (
    N_FEEDBACK_FULL_TRUST,
    blend,
)
from packages.observability import with_span
from packages.orchestration.eval_models import (
    EvalSet,
    EvalSnapshot,
    Metric,
)
from packages.orchestration.eval_protocols import EvalSnapshotter, FeedbackStore

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DailyJudgeSample:
    """A single QA sample to score for the day's snapshot.

    `refused=True` flags cost-blocked tasks (ADR-0015) — they enter the
    denominator with a forced `useful=False, citations_correct=False`
    verdict per ADR-0016 §3.
    """

    sample_id: str
    question: str
    answer: str
    refused: bool
    latency_s: float
    cost_usd: float
    citation_f1: float | None = None


class DailySampleSource(Protocol):
    """Yields QA samples to be judged for one (library_id, eval_set, day)."""

    def iter_samples(
        self,
        library_id: str,
        *,
        eval_set: EvalSet,
        day: Date,
    ) -> AsyncIterator[DailyJudgeSample]: ...


@dataclass(frozen=True, slots=True)
class DailyMetricBucket:
    """Accumulator for the four metrics on a single day."""

    judge_hits: int = 0
    judge_total: int = 0
    citation_f1_sum: float = 0.0
    citation_f1_count: int = 0
    latencies: tuple[float, ...] = ()
    cost_sum: float = 0.0
    cost_count: int = 0

    def with_sample(
        self,
        *,
        judged_hit: bool | None,
        citation_f1: float | None,
        latency_s: float,
        cost_usd: float,
    ) -> DailyMetricBucket:
        return DailyMetricBucket(
            judge_hits=self.judge_hits + (1 if judged_hit is True else 0),
            judge_total=self.judge_total + (1 if judged_hit is not None else 0),
            citation_f1_sum=self.citation_f1_sum + (citation_f1 or 0.0),
            citation_f1_count=self.citation_f1_count + (1 if citation_f1 is not None else 0),
            latencies=(*self.latencies, latency_s),
            cost_sum=self.cost_sum + cost_usd,
            cost_count=self.cost_count + 1,
        )


def _percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile; matches PRD §3.2 P95 reporting style."""
    if not values:
        return 0.0
    if not 0.0 <= p <= 100.0:
        msg = f"percentile p must be in [0, 100], got {p}"
        raise ValueError(msg)
    sorted_vals = sorted(values)
    rank = max(1, math.ceil(p / 100.0 * len(sorted_vals)))
    return sorted_vals[rank - 1]


class DailyEvalSnapshotter:
    """Computes 4 metrics + writes them to `eval_snapshots`.

    Single-library, single-eval-set, single-day call. The cron job loops
    over libraries and eval_sets. ADR-0016 §6 explicitly requires per-eval-set
    bucketing.
    """

    def __init__(
        self,
        *,
        snapshots: EvalSnapshotter,
        judge: DualLLMJudge,
        sample_source: DailySampleSource,
        feedback_store: FeedbackStore,
        feedback_window_days: int = 7,
    ) -> None:
        self._snapshots = snapshots
        self._judge = judge
        self._sample_source = sample_source
        self._feedback_store = feedback_store
        self._feedback_window_days = feedback_window_days

    async def write_for_day(
        self,
        library_id: str,
        *,
        eval_set: EvalSet,
        day: Date,
    ) -> tuple[EvalSnapshot, ...]:
        """Score the day's samples and write 4 snapshot rows."""
        async with with_span(
            "evaluation.snapshot.write_for_day",
            library_id=library_id,
        ):
            bucket = await self._score_day(library_id, eval_set=eval_set, day=day)
            now = datetime.now(UTC)
            blended_var = await self._blended_var(library_id=library_id, day=day, bucket=bucket)
            rows = _bucket_to_snapshots(
                bucket,
                library_id=library_id,
                day=day,
                eval_set=eval_set,
                computed_at=now,
                blended_var=blended_var,
            )
            for row in rows:
                # `EvalSnapshotter.write_daily` returns batches; here we
                # bypass that and use the row-level write to avoid recomputation.
                # The Protocol exposes only the batch entry point so the
                # adapter must accept individual writes via internal API.
                # See PostgresEvalSnapshotter.write_one.
                await self._write_row(row)
            await logger.ainfo(
                "eval_snapshot_written",
                library_id=library_id,
                eval_set=eval_set,
                day=day.isoformat(),
                judge_total=bucket.judge_total,
                judge_hits=bucket.judge_hits,
                latency_p95=_percentile(bucket.latencies, 95.0),
                avg_cost=bucket.cost_sum / bucket.cost_count if bucket.cost_count else 0.0,
                prompt_version=JUDGE_PROMPT_VERSION,
            )
            return rows

    async def _write_row(self, row: EvalSnapshot) -> None:
        """Adapter-level shim — concrete EvalSnapshotter implementations
        expose `write_one(row)`. We duck-type on it; tests can pass any object
        with that method.
        """
        write_one = getattr(self._snapshots, "write_one", None)
        if write_one is None:
            msg = (
                "EvalSnapshotter implementation must expose `write_one(row)` "
                "for granular daily inserts."
            )
            raise RuntimeError(msg)
        await write_one(row)

    async def _score_day(
        self,
        library_id: str,
        *,
        eval_set: EvalSet,
        day: Date,
    ) -> DailyMetricBucket:
        bucket = DailyMetricBucket()
        async for sample in self._sample_source.iter_samples(
            library_id, eval_set=eval_set, day=day
        ):
            judged_hit = await self._judge_sample(sample)
            bucket = bucket.with_sample(
                judged_hit=judged_hit,
                citation_f1=sample.citation_f1,
                latency_s=sample.latency_s,
                cost_usd=sample.cost_usd,
            )
        return bucket

    async def _blended_var(
        self,
        *,
        library_id: str,
        day: Date,
        bucket: DailyMetricBucket,
    ) -> tuple[float, int] | None:
        """Compute today's blended VAR using feedback over the same window.

        Returns (value, sample_size) or None when neither tier has data.
        Sample size = judge_total + n_feedback (rough denominator for
        downstream weight tracking).
        """
        if bucket.judge_total == 0:
            judge_value: float | None = None
        else:
            judge_value = bucket.judge_hits / bucket.judge_total
        end_dt = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)
        since_dt = end_dt - timedelta(days=self._feedback_window_days)
        feedback = await self._feedback_store.list_for_library(
            library_id, since=since_dt, limit=10_000
        )
        valid_fb = tuple(f for f in feedback if f.revoked_at is None)
        if valid_fb:
            hits = sum(1 for f in valid_fb if f.useful and f.citations_correct)
            fb_value: float | None = hits / len(valid_fb)
            n_fb = len(valid_fb)
        else:
            fb_value = None
            n_fb = 0
        if judge_value is None and fb_value is None:
            return None
        blended = blend(fb_value, judge_value, n_fb, n_full_trust=N_FEEDBACK_FULL_TRUST)
        return blended, bucket.judge_total + n_fb

    async def _judge_sample(self, sample: DailyJudgeSample) -> bool | None:
        """Return True/False if dual-judge agreed; None on disagreement."""
        if sample.refused:
            # ADR-0016 §3 — cost-blocked tasks count as failed VAR cases.
            return False
        verdict = await self._judge.judge(sample.question, sample.answer)
        if not verdict.agreed or verdict.useful is None:
            return None
        return bool(verdict.useful and verdict.citations_correct)


def _bucket_to_snapshots(
    bucket: DailyMetricBucket,
    *,
    library_id: str,
    day: Date,
    eval_set: EvalSet,
    computed_at: datetime,
    blended_var: tuple[float, int] | None,
) -> tuple[EvalSnapshot, ...]:
    """Convert a day's accumulator into snapshot rows.

    Writes (in order, when data is available):
      * `var_judge`     — judge-only ratio
      * `var`           — blended (feedback + judge); read by AlertEngine
      * `citation_f1`   — mean of per-sample F1
      * `p95_latency_s` — 95th-percentile latency
      * `avg_cost_usd`  — mean cost per sample
    """
    rows: list[EvalSnapshot] = []
    if bucket.judge_total > 0:
        rows.append(
            _row(
                library_id=library_id,
                day=day,
                eval_set=eval_set,
                metric="var_judge",
                value=bucket.judge_hits / bucket.judge_total,
                sample_size=bucket.judge_total,
                computed_at=computed_at,
            )
        )
    if blended_var is not None:
        value, sample_size = blended_var
        rows.append(
            _row(
                library_id=library_id,
                day=day,
                eval_set=eval_set,
                metric="var",
                value=value,
                sample_size=sample_size,
                computed_at=computed_at,
            )
        )
    if bucket.citation_f1_count > 0:
        rows.append(
            _row(
                library_id=library_id,
                day=day,
                eval_set=eval_set,
                metric="citation_f1",
                value=bucket.citation_f1_sum / bucket.citation_f1_count,
                sample_size=bucket.citation_f1_count,
                computed_at=computed_at,
            )
        )
    if bucket.latencies:
        rows.append(
            _row(
                library_id=library_id,
                day=day,
                eval_set=eval_set,
                metric="p95_latency_s",
                value=_percentile(bucket.latencies, 95.0),
                sample_size=len(bucket.latencies),
                computed_at=computed_at,
            )
        )
    if bucket.cost_count > 0:
        rows.append(
            _row(
                library_id=library_id,
                day=day,
                eval_set=eval_set,
                metric="avg_cost_usd",
                value=bucket.cost_sum / bucket.cost_count,
                sample_size=bucket.cost_count,
                computed_at=computed_at,
            )
        )
    return tuple(rows)


def _row(
    *,
    library_id: str,
    day: Date,
    eval_set: EvalSet,
    metric: Metric,
    value: float,
    sample_size: int,
    computed_at: datetime,
) -> EvalSnapshot:
    return EvalSnapshot(
        library_id=library_id,
        date=day,
        eval_set=eval_set,
        metric=metric,
        value=value,
        sample_size=sample_size,
        computed_at=computed_at,
    )


__all__ = [
    "DailyEvalSnapshotter",
    "DailyJudgeSample",
    "DailyMetricBucket",
    "DailySampleSource",
]
