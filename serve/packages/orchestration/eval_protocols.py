"""Eval computation Protocols (ADR-0016 VAR + ADR-0021 alerts).

Implementations live under `packages/evaluation/` (existing) — this file
just adds the Protocol contracts the M7 dashboard depends on.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from typing import Protocol, runtime_checkable

from packages.orchestration.eval_models import (
    AnswerFeedback,
    EvalAlert,
    EvalKPIs,
    EvalSet,
    EvalSnapshot,
    Metric,
)


@runtime_checkable
class FeedbackStore(Protocol):
    """Per-library AnswerFeedback persistence."""

    async def submit(self, feedback: AnswerFeedback) -> None: ...

    async def revoke(
        self,
        library_id: str,
        answer_id: str,
        user_id: str | None,
    ) -> None: ...

    async def list_for_library(
        self,
        library_id: str,
        *,
        since: datetime | None = None,
        limit: int = 200,
    ) -> tuple[AnswerFeedback, ...]: ...

    async def purge_library(self, library_id: str) -> None: ...


@runtime_checkable
class VARComputer(Protocol):
    """VAR (Valid Answer Rate) calculator (ADR-0016)."""

    async def compute(
        self,
        library_id: str,
        *,
        eval_set: EvalSet,
        days: int = 7,
    ) -> float: ...


@runtime_checkable
class EvalSnapshotter(Protocol):
    """Daily KPI snapshot writer + reader."""

    async def write_daily(
        self,
        library_id: str,
        *,
        as_of: Date,
    ) -> tuple[EvalSnapshot, ...]: ...

    async def get_kpis(
        self,
        library_id: str,
        *,
        eval_set: EvalSet,
    ) -> EvalKPIs | None: ...

    async def get_trend(
        self,
        library_id: str,
        *,
        metric: Metric,
        eval_set: EvalSet,
        days: int = 30,
    ) -> tuple[EvalSnapshot, ...]: ...

    async def purge_library(self, library_id: str) -> None: ...


@runtime_checkable
class AlertEngine(Protocol):
    """Eval alert evaluator (ADR-0021).

    Run once per day at 02:30 UTC, after `EvalSnapshotter.write_daily`.
    """

    async def evaluate(self, library_id: str) -> tuple[EvalAlert, ...]: ...

    async def list_active(self, library_id: str) -> tuple[EvalAlert, ...]: ...

    async def list_recent(
        self,
        library_id: str,
        *,
        days: int = 30,
        limit: int = 50,
    ) -> tuple[EvalAlert, ...]: ...

    async def purge_library(self, library_id: str) -> None: ...
