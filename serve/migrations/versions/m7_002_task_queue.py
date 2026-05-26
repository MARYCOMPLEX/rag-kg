"""m7_002 — create the durable ``tasks`` table for the async queue.

# Motivation
ADR-0009 §4 specifies that the Postgres ``tasks`` table is the single
source of truth for task lifecycle; Arq's Redis state is treated as
ephemeral cache. This migration materialises that schema.

# Rollback steps
``alembic downgrade -1`` drops the ``tasks`` table along with the two
indexes. Operators should drain in-flight Arq jobs first
(``redis-cli -- XLEN arq:queue``) — a bare downgrade orphans queue
metadata still in Redis but does not corrupt other tables.

# Impact scope
Net-new table; no existing rows are touched. The FK on
``library_id → libraries(library_id) ON DELETE CASCADE`` means Library
purge (ADR-0022) will automatically clean up task rows as part of the
Postgres saga.

Revision ID: m7_002_task_queue
Revises: m7_001_libraries
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7_002_task_queue"
down_revision: str | None = "m7_001_libraries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.Text(), primary_key=True),
        sa.Column(
            "library_id",
            sa.Text(),
            sa.ForeignKey("libraries.library_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "progress",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("current_stage", sa.Text(), nullable=True),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("budget", sa.JSON(), nullable=True),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("dedup_key", sa.Text(), nullable=True),
        sa.Column("result_pointer", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column(
            "cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="tasks_status_enum",
        ),
        sa.UniqueConstraint("library_id", "dedup_key", name="tasks_dedup_uq"),
    )
    op.create_index(
        "tasks_library_status_idx",
        "tasks",
        ["library_id", "status", "enqueued_at"],
    )
    op.create_index(
        "tasks_active_idx",
        "tasks",
        ["library_id"],
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("tasks_active_idx", table_name="tasks")
    op.drop_index("tasks_library_status_idx", table_name="tasks")
    op.drop_table("tasks")
