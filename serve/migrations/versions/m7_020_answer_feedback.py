"""m7_020 — create the ``answer_feedback`` table for VAR computation.

# Motivation
ADR-0016 §2 specifies a per-user feedback signal that feeds the
``var_feedback`` term of the blended VAR. Submission idempotency is
enforced by the composite ``UNIQUE (answer_id, user_id)`` constraint,
serving as the spam guard required by ADR-0016 §R-VAR-2.

# Rollback steps
``alembic downgrade -1`` drops the table and its indexes. Operators
should verify no analytics jobs (Grafana / Eval Dashboard) are scraping
the table before downgrading; rollback drops accumulated user feedback.

# Impact scope
Net-new table; no existing rows are touched. Per ADR_REVIEW R8 the
``library_id`` FK CASCADEs on Library purge — feedback rows belong to
their Library and are dropped when the Library is deleted.

Revision ID: m7_020_answer_feedback
Revises: m7_013
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7_020_answer_feedback"
down_revision: str | None = "m7_013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "answer_feedback",
        sa.Column(
            "library_id",
            sa.Text(),
            sa.ForeignKey("libraries.library_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("answer_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("useful", sa.Boolean(), nullable=False),
        sa.Column("citations_correct", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        # ADR-0016 §2 — one verdict per (answer, user) pair. NULL user_id
        # is treated as a single anonymous bucket per Postgres NULL semantics,
        # which is exactly the spam-guard intent.
        sa.UniqueConstraint("answer_id", "user_id", name="answer_feedback_answer_user_uq"),
    )
    op.create_index(
        "answer_feedback_lib_date_idx",
        "answer_feedback",
        ["library_id", "created_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "answer_feedback_lib_answer_idx",
        "answer_feedback",
        ["library_id", "answer_id"],
    )


def downgrade() -> None:
    op.drop_index("answer_feedback_lib_answer_idx", table_name="answer_feedback")
    op.drop_index("answer_feedback_lib_date_idx", table_name="answer_feedback")
    op.drop_table("answer_feedback")
