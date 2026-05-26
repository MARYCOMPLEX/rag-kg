"""Pure-function evaluator for the Library status state machine (ADR-0013).

Decoupled from any I/O: the caller fetches the inputs (active task count,
last community rebuild ts, new doc count) and passes them in. This keeps
the rule trivially unit-testable and lets the postgres adapter use the
same logic as a future in-memory adapter.

Status decision tree (ADR-0013 §3):

```
active_index_tasks > 0     → INDEXING
last_rebuild is None       → HEALTHY
age(last_rebuild) < 7d     → HEALTHY
new_docs_since_rebuild ≥ 50 → STALE_COMMUNITY
otherwise                  → HEALTHY
```

The "stuck-in-Indexing > 24h" warning (ADR-0013 §7) is signaled via a
separate flag returned alongside the status, since it does not change the
state itself but should trigger an alert notification.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from packages.core.models import LibraryStatus

# ADR-0013 §3 — hardcoded in v1, per-Library override deferred to v1.1.
STALE_AGE_THRESHOLD: timedelta = timedelta(days=7)
STALE_DOC_COUNT_THRESHOLD: int = 50
STUCK_INDEXING_THRESHOLD: timedelta = timedelta(hours=24)
STATUS_CHECK_INTERVAL_SECONDS: int = 300


@dataclass(frozen=True, slots=True)
class StatusInputs:
    """Snapshot of facts used to derive the next library status.

    All fields are explicit inputs so the evaluator stays pure.
    """

    library_id: str
    current_status: LibraryStatus
    status_updated_at: datetime | None
    active_index_tasks: int
    last_community_rebuild: datetime | None
    new_docs_since_rebuild: int
    now: datetime


@dataclass(frozen=True, slots=True)
class StatusDecision:
    """Result of a single evaluator pass."""

    new_status: LibraryStatus
    reason: str
    stuck_in_indexing: bool


def evaluate(inputs: StatusInputs) -> StatusDecision:
    """Compute the next status from a snapshot of facts.

    Args:
        inputs: Frozen snapshot of all values needed to make a decision.

    Returns:
        A `StatusDecision` carrying the new status, a human-readable
        reason, and a flag indicating the library has been Indexing for
        longer than the safety threshold (ops should investigate).
    """
    stuck = _is_stuck_in_indexing(inputs)

    if inputs.active_index_tasks > 0:
        return StatusDecision(
            new_status=LibraryStatus.INDEXING,
            reason=f"{inputs.active_index_tasks} active index task(s)",
            stuck_in_indexing=stuck,
        )

    if inputs.last_community_rebuild is None:
        return StatusDecision(
            new_status=LibraryStatus.HEALTHY,
            reason="never built community summaries — empty corpus is healthy",
            stuck_in_indexing=False,
        )

    age = inputs.now - inputs.last_community_rebuild
    if age < STALE_AGE_THRESHOLD:
        return StatusDecision(
            new_status=LibraryStatus.HEALTHY,
            reason=f"community rebuilt {_humanize_age(age)} ago",
            stuck_in_indexing=False,
        )

    if inputs.new_docs_since_rebuild >= STALE_DOC_COUNT_THRESHOLD:
        return StatusDecision(
            new_status=LibraryStatus.STALE_COMMUNITY,
            reason=(
                f"{inputs.new_docs_since_rebuild} new docs since last rebuild "
                f"({_humanize_age(age)} ago)"
            ),
            stuck_in_indexing=False,
        )

    return StatusDecision(
        new_status=LibraryStatus.HEALTHY,
        reason=(
            f"{inputs.new_docs_since_rebuild} new docs since last rebuild "
            f"(threshold {STALE_DOC_COUNT_THRESHOLD})"
        ),
        stuck_in_indexing=False,
    )


def _is_stuck_in_indexing(inputs: StatusInputs) -> bool:
    if inputs.current_status is not LibraryStatus.INDEXING:
        return False
    if inputs.status_updated_at is None:
        return False
    return (inputs.now - inputs.status_updated_at) >= STUCK_INDEXING_THRESHOLD


def _humanize_age(delta: timedelta) -> str:
    """Render a timedelta as `Nd Hh` for log lines."""
    total_seconds = int(delta.total_seconds())
    total_seconds = max(total_seconds, 0)
    days, remainder = divmod(total_seconds, 86_400)
    hours = remainder // 3_600
    if days:
        return f"{days}d{hours}h"
    minutes = (total_seconds % 3_600) // 60
    return f"{hours}h{minutes}m"
