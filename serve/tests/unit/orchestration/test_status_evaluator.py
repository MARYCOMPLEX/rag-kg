"""Pure-function tests for the library status evaluator (ADR-0013 §3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.core.models import LibraryStatus
from packages.orchestration._internal.status_evaluator import (
    STALE_AGE_THRESHOLD,
    STALE_DOC_COUNT_THRESHOLD,
    STUCK_INDEXING_THRESHOLD,
    StatusInputs,
    evaluate,
)

_NOW = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)


def _inputs(
    *,
    current: LibraryStatus = LibraryStatus.HEALTHY,
    status_updated_at: datetime | None = None,
    active_index_tasks: int = 0,
    last_community_rebuild: datetime | None = None,
    new_docs_since_rebuild: int = 0,
    now: datetime = _NOW,
) -> StatusInputs:
    return StatusInputs(
        library_id="lib-test",
        current_status=current,
        status_updated_at=status_updated_at,
        active_index_tasks=active_index_tasks,
        last_community_rebuild=last_community_rebuild,
        new_docs_since_rebuild=new_docs_since_rebuild,
        now=now,
    )


def test_active_index_tasks_force_indexing() -> None:
    """Any in-flight ingest/KG/community task wins regardless of staleness."""
    # Arrange
    facts = _inputs(
        active_index_tasks=2,
        last_community_rebuild=_NOW - timedelta(days=10),
        new_docs_since_rebuild=STALE_DOC_COUNT_THRESHOLD + 1,
    )

    # Act
    decision = evaluate(facts)

    # Assert
    assert decision.new_status is LibraryStatus.INDEXING
    assert "active index task" in decision.reason


def test_no_rebuild_yet_is_healthy() -> None:
    """An empty library that has never built communities is Healthy, not Stale."""
    # Arrange
    facts = _inputs(last_community_rebuild=None)

    # Act
    decision = evaluate(facts)

    # Assert
    assert decision.new_status is LibraryStatus.HEALTHY
    assert "never built" in decision.reason


def test_stale_when_age_and_doc_threshold_breached() -> None:
    """7+ days since last rebuild AND ≥ 50 new docs → STALE_COMMUNITY."""
    # Arrange
    facts = _inputs(
        last_community_rebuild=_NOW - STALE_AGE_THRESHOLD - timedelta(days=1),
        new_docs_since_rebuild=STALE_DOC_COUNT_THRESHOLD,
    )

    # Act
    decision = evaluate(facts)

    # Assert
    assert decision.new_status is LibraryStatus.STALE_COMMUNITY
    assert str(STALE_DOC_COUNT_THRESHOLD) in decision.reason


def test_recent_rebuild_keeps_healthy_even_with_many_new_docs() -> None:
    """Within the 7-day window we stay Healthy regardless of doc count."""
    # Arrange
    facts = _inputs(
        last_community_rebuild=_NOW - timedelta(days=2),
        new_docs_since_rebuild=STALE_DOC_COUNT_THRESHOLD * 4,
    )

    # Act
    decision = evaluate(facts)

    # Assert
    assert decision.new_status is LibraryStatus.HEALTHY
    assert decision.stuck_in_indexing is False


def test_stuck_in_indexing_flag_set_after_24h() -> None:
    """Indexing > 24h sets stuck flag without changing the status itself."""
    # Arrange
    facts = _inputs(
        current=LibraryStatus.INDEXING,
        status_updated_at=_NOW - STUCK_INDEXING_THRESHOLD - timedelta(hours=1),
        active_index_tasks=1,
    )

    # Act
    decision = evaluate(facts)

    # Assert — still INDEXING but stuck signal is on for the alert path.
    assert decision.new_status is LibraryStatus.INDEXING
    assert decision.stuck_in_indexing is True
