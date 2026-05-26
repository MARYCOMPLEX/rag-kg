"""m7_011 — create the partitioned ``activity_log`` table + 12 monthly partitions.

# Motivation
ADR-0014 §2 specifies a per-month range-partitioned ``activity_log`` table
to drive the S2 Library Dashboard "Recent activity" feed and the L5
cross-library aggregation reader. ``pg_partman`` is not assumed to be
installed, so partitions are created manually for the next 12 months
starting from the migration date.

# Rollback steps
``alembic downgrade -1`` drops every child partition first (in reverse
order to satisfy CHECK constraints) and then the parent table. Existing
activity rows are lost — operators should ``COPY`` them out to a CSV
before downgrading.

# Impact scope
Net-new table family. No FK to ``libraries`` per ADR-0014 §6 Open
Question 6 (``library_purged`` events must outlive the Library row for
audit purposes). Default 90-day retention is enforced by a separate
manual ``DETACH + DROP`` runbook step (or future pg_partman config).

Revision ID: m7_011_activity_log
Revises: m7_010_notifications
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from alembic import op

revision: str = "m7_011_activity_log"
down_revision: str | None = "m7_010_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Anchor month — keeps `alembic upgrade head` deterministic across reruns.
# 12 monthly partitions starting at this anchor cover one full year ahead
# of the M7 launch. Operators can extend the chain via runbook SQL or by
# wiring pg_partman in later.
_ANCHOR_YEAR = 2026
_ANCHOR_MONTH = 1
_MONTHS_PER_YEAR = 12
_PARTITION_COUNT = _MONTHS_PER_YEAR


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == _MONTHS_PER_YEAR:
        return year + 1, 1
    return year, month + 1


def _partition_name(year: int, month: int) -> str:
    return f"activity_log_y{year}m{month:02d}"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE activity_log (
            id BIGSERIAL,
            library_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            actor TEXT NOT NULL DEFAULT 'system',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);
        """
    )
    op.create_index(
        "activity_log_lib_created_idx",
        "activity_log",
        ["library_id", "created_at"],
        postgresql_using="btree",
    )
    op.create_index(
        "activity_log_lib_type_created_idx",
        "activity_log",
        ["library_id", "type", "created_at"],
    )

    year, month = _ANCHOR_YEAR, _ANCHOR_MONTH
    for _ in range(_PARTITION_COUNT):
        next_year, next_month = _next_month(year, month)
        partition = _partition_name(year, month)
        start = date(year, month, 1).isoformat()
        end = date(next_year, next_month, 1).isoformat()
        op.execute(
            f"""
            CREATE TABLE {partition}
            PARTITION OF activity_log
            FOR VALUES FROM ('{start}') TO ('{end}');
            """
        )
        year, month = next_year, next_month


def downgrade() -> None:
    year, month = _ANCHOR_YEAR, _ANCHOR_MONTH
    partitions: list[str] = []
    for _ in range(_PARTITION_COUNT):
        partitions.append(_partition_name(year, month))
        year, month = _next_month(year, month)
    for partition in reversed(partitions):
        op.execute(f"DROP TABLE IF EXISTS {partition}")
    op.drop_index("activity_log_lib_type_created_idx", table_name="activity_log")
    op.drop_index("activity_log_lib_created_idx", table_name="activity_log")
    op.execute("DROP TABLE IF EXISTS activity_log")
