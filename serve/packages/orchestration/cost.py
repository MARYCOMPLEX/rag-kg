"""Per-library daily cost cap (ADR-0015).

Tracks LLM token cost per (library_id, date) in Postgres. Gateway reads
before each call and blocks when cap reached. Soft warn at 80%, hard block
at 100% (configurable per-Library via `LibraryConfig.cost_cap_warn_pct`).
"""

from __future__ import annotations

from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class LibraryDailyCost(BaseModel):
    """One day's accumulated cost for one Library.

    Atomically updated via `INSERT ... ON CONFLICT DO UPDATE` — ADR-0015.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    date: Date  # in Library's configured timezone
    cost_usd: Decimal = Field(default=Decimal("0"))
    llm_calls: int = Field(default=0, ge=0)
    last_updated_at: datetime


class CostCheckResult(BaseModel):
    """Outcome of a cost-cap pre-check.

    `decision == "blocked"` causes the LLM Gateway / TaskRunner to refuse
    the call with HTTP 402 / Arq abort.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    decision: str  # "allow" | "warn" | "blocked"
    spent_usd: Decimal
    cap_usd: Decimal | None = None
    pct_used: float = Field(ge=0.0)
    next_reset_at: datetime


@runtime_checkable
class CostCapEnforcer(Protocol):
    """Cost cap reads + writes (ADR-0015)."""

    async def check(self, library_id: str) -> CostCheckResult: ...

    async def record(
        self,
        library_id: str,
        cost_usd: Decimal,
        llm_calls: int = 1,
    ) -> CostCheckResult: ...

    async def history(
        self,
        library_id: str,
        *,
        days: int = 30,
    ) -> tuple[LibraryDailyCost, ...]: ...

    async def purge_library(self, library_id: str) -> None: ...
