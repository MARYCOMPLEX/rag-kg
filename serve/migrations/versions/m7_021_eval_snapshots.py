"""m7_021 — create the ``eval_snapshots`` table for daily KPI pins.

# Motivation
ADR-0016 §5 mandates a daily snapshot of VAR / Citation F1 / P95 latency /
avg cost per (Library, eval_set), composing the source-of-truth window for
the alert engine (ADR-0021) and the Eval Dashboard trend charts. The
composite primary key ``(library_id, date, eval_set, metric)`` matches
ADR-0016 §5 exactly.

# Rollback steps
``alembic downgrade -1`` drops the table. Snapshots are recomputable from
the underlying QA logs but the recomputation is expensive (one LLM-judge
pass per day); export the table before downgrade if the trend history
matters.

# Impact scope
Net-new table; the ``library_id`` FK CASCADEs per ADR_REVIEW R8 so
purging a Library cleans its snapshots too. Read paths in
``apps/api/routes/eval.py`` query this table directly.

Revision ID: m7_021_eval_snapshots
Revises: m7_020_answer_feedback
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7_021_eval_snapshots"
down_revision: str | None = "m7_020_answer_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_snapshots",
        sa.Column(
            "library_id",
            sa.Text(),
            sa.ForeignKey("libraries.library_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("eval_set", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "sample_size",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint(
            "library_id",
            "date",
            "eval_set",
            "metric",
            name="eval_snapshots_pk",
        ),
        sa.CheckConstraint(
            "eval_set IN ('smoke','multihop','review')",
            name="eval_snapshots_eval_set_enum",
        ),
        sa.CheckConstraint(
            "metric IN ('var','var_feedback','var_judge','citation_f1',"
            "'p95_latency_s','avg_cost_usd')",
            name="eval_snapshots_metric_enum",
        ),
    )
    op.create_index(
        "eval_snapshots_lib_metric_date_idx",
        "eval_snapshots",
        ["library_id", "metric", "date"],
    )
    op.create_index(
        "eval_snapshots_lib_evalset_date_idx",
        "eval_snapshots",
        ["library_id", "eval_set", "date"],
    )


def downgrade() -> None:
    op.drop_index("eval_snapshots_lib_evalset_date_idx", table_name="eval_snapshots")
    op.drop_index("eval_snapshots_lib_metric_date_idx", table_name="eval_snapshots")
    op.drop_table("eval_snapshots")
