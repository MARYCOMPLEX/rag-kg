"""Library status state machine (ADR-0013).

Periodic worker job (`apps/worker/jobs/library_status_check.py`) calls
`LibraryStatusChecker.evaluate(...)` every 5 minutes. State transitions
emit `library_status_changed` notifications and activity events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from packages.core.models import LibraryStatus


class LibraryStatusEvaluation(BaseModel):
    """Output of one evaluation pass."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    library_id: str = Field(min_length=1)
    previous_status: LibraryStatus
    new_status: LibraryStatus
    reason: str  # human-readable trigger
    evaluated_at: datetime


@runtime_checkable
class LibraryStatusChecker(Protocol):
    """Idempotent status evaluator. Acquires Postgres advisory lock per library."""

    async def evaluate(self, library_id: str) -> LibraryStatusEvaluation: ...

    async def evaluate_all(self) -> tuple[LibraryStatusEvaluation, ...]:
        """Loop helper — calls `evaluate(library_id)` for every active Library.

        Cross-library iteration is L5-orchestration-only (ADR-0014 boundary).
        """
        ...
