"""m7_013 — create the ``library_daily_cost`` aggregation table.

# Motivation
ADR-0015 §1 specifies a per-(library_id, date) accumulator for LLM cost
that the gateway upserts atomically via ``INSERT ... ON CONFLICT DO
UPDATE``. The table feeds the cost-cap admission check (Gate 1) and the
S2/S8 cost trend chart (``GET /v1/libraries/{lib}/cost``).

# Rollback steps
``alembic downgrade -1`` drops the date index then the table. Operators
should snapshot the current rows first if they need historical cost
attribution — the data is reconstructable from Langfuse traces but the
backfill is non-trivial.

# Impact scope
Net-new table. ``library_id`` is FK to ``libraries`` with ``ON DELETE
CASCADE`` per ADR_REVIEW R8. Composite PK ``(library_id, date)`` is the
upsert conflict target the LLM gateway relies on.

Revision ID: m7_013
Revises: m7_012_library_config
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Short revision id (`m7_013`) keeps it stable for downstream chains
# (e.g. m7_020) that pre-reference us by the milestone marker only.
revision: str = "m7_013"
down_revision: str | None = "m7_012_library_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_daily_cost",
        sa.Column(
            "library_id",
            sa.Text(),
            sa.ForeignKey("libraries.library_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "cost_usd",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "llm_calls",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("library_id", "date", name="library_daily_cost_pk"),
    )
    op.create_index(
        "library_daily_cost_date_idx",
        "library_daily_cost",
        ["date"],
    )


def downgrade() -> None:
    op.drop_index("library_daily_cost_date_idx", table_name="library_daily_cost")
    op.drop_table("library_daily_cost")
