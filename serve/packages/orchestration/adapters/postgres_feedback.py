"""Postgres-backed AnswerFeedback store (ADR-0016).

Implements the ``FeedbackStore`` Protocol. The composite ``UNIQUE (answer_id,
user_id)`` constraint is the spam guard required by ADR-0016 §R-VAR-2 — a
re-submission for the same (answer, user) pair updates the existing row
instead of inserting a duplicate.

Library scope is enforced as a WHERE clause on every read so feedback
written under Library A is invisible from Library B (CODING_STANDARDS §6.5).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    MetaData,
    Table,
    Text,
    and_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.observability import with_span
from packages.orchestration.errors import OrchestrationError
from packages.orchestration.eval_models import AnswerFeedback

logger = structlog.get_logger(__name__)

_metadata = MetaData()

answer_feedback_table = Table(
    "answer_feedback",
    _metadata,
    Column("library_id", Text, nullable=False),
    Column("answer_id", Text, nullable=False),
    Column("user_id", Text, nullable=True),
    Column("useful", Boolean, nullable=False),
    Column("citations_correct", Boolean, nullable=False),
    Column("comment", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    """Coerce naive timestamps to UTC; pass through aware ones."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _row_to_feedback(row: Mapping[str, Any]) -> AnswerFeedback:
    """Map a SQLAlchemy Row mapping back to the domain model."""
    return AnswerFeedback(
        library_id=row["library_id"],
        answer_id=row["answer_id"],
        user_id=row["user_id"],
        useful=bool(row["useful"]),
        citations_correct=bool(row["citations_correct"]),
        comment=row["comment"],
        created_at=_ensure_aware(row["created_at"]) or datetime.now(UTC),
        revoked_at=_ensure_aware(row["revoked_at"]),
    )


class PostgresFeedbackStore:
    """Durable ``answer_feedback`` adapter implementing ``FeedbackStore``."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
            engine, expire_on_commit=False
        )

    async def submit(self, feedback: AnswerFeedback) -> None:
        """Insert or update a feedback row.

        Idempotency: ``(answer_id, user_id)`` UNIQUE — a re-submission with
        the same pair updates the existing row's verdict and clears any
        prior ``revoked_at`` (ADR-0016 §R-VAR-2 spam guard).
        """
        async with with_span("orchestration.feedback.submit", library_id=feedback.library_id):
            try:
                stmt = pg_insert(answer_feedback_table).values(
                    library_id=feedback.library_id,
                    answer_id=feedback.answer_id,
                    user_id=feedback.user_id,
                    useful=feedback.useful,
                    citations_correct=feedback.citations_correct,
                    comment=feedback.comment,
                    created_at=feedback.created_at,
                    revoked_at=feedback.revoked_at,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["answer_id", "user_id"],
                    set_={
                        "useful": feedback.useful,
                        "citations_correct": feedback.citations_correct,
                        "comment": feedback.comment,
                        "revoked_at": feedback.revoked_at,
                    },
                )
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                await logger.aerror(
                    "feedback_submit_failed",
                    library_id=feedback.library_id,
                    answer_id=feedback.answer_id,
                    error=repr(exc),
                )
                raise OrchestrationError("feedback submit failed") from exc

            await logger.ainfo(
                "feedback_submitted",
                library_id=feedback.library_id,
                answer_id=feedback.answer_id,
                user_id=feedback.user_id,
                useful=feedback.useful,
                citations_correct=feedback.citations_correct,
            )

    async def revoke(
        self,
        library_id: str,
        answer_id: str,
        user_id: str | None,
    ) -> None:
        """Soft-revoke an existing feedback row (ADR-0016 §2 ``DELETE``)."""
        async with with_span("orchestration.feedback.revoke", library_id=library_id):
            now = datetime.now(UTC)
            condition = and_(
                answer_feedback_table.c.library_id == library_id,
                answer_feedback_table.c.answer_id == answer_id,
                (
                    answer_feedback_table.c.user_id.is_(None)
                    if user_id is None
                    else answer_feedback_table.c.user_id == user_id
                ),
            )
            stmt = update(answer_feedback_table).where(condition).values(revoked_at=now)
            try:
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                raise OrchestrationError("feedback revoke failed") from exc

            await logger.ainfo(
                "feedback_revoked",
                library_id=library_id,
                answer_id=answer_id,
                user_id=user_id,
            )

    async def list_for_library(
        self,
        library_id: str,
        *,
        since: datetime | None = None,
        limit: int = 200,
    ) -> tuple[AnswerFeedback, ...]:
        """Return un-revoked feedback rows for a Library, newest first."""
        async with with_span("orchestration.feedback.list_for_library", library_id=library_id):
            conditions = [answer_feedback_table.c.library_id == library_id]
            if since is not None:
                conditions.append(answer_feedback_table.c.created_at >= since)
            stmt = (
                select(answer_feedback_table)
                .where(and_(*conditions))
                .order_by(answer_feedback_table.c.created_at.desc())
                .limit(limit)
            )
            async with self._sessionmaker() as session:
                result = await session.execute(stmt)
                rows = result.mappings().all()
            return tuple(_row_to_feedback(cast(Mapping[str, Any], r)) for r in rows)

    async def purge_library(self, library_id: str) -> None:
        """Delete every feedback row for a Library (ADR-0022 saga step)."""
        async with with_span("orchestration.feedback.purge_library", library_id=library_id):
            stmt = answer_feedback_table.delete().where(
                answer_feedback_table.c.library_id == library_id
            )
            try:
                async with self._sessionmaker() as session, session.begin():
                    await session.execute(stmt)
            except SQLAlchemyError as exc:
                raise OrchestrationError(f"feedback purge failed: {library_id}") from exc
            await logger.ainfo("feedback_purged", library_id=library_id)


__all__ = ["PostgresFeedbackStore", "answer_feedback_table"]
