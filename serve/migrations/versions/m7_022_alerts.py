"""m7_022 — create the ``alerts`` table for the Eval Dashboard banner.

# Motivation
ADR-0021 §3 specifies a state-view table for the five v1 alert rules
(VAR / Citation F1 / P95 / cost-warn / cost-block). The partial unique
index ``UNIQUE (library_id, rule) WHERE status = 'active'`` is the
deduplication mechanism that keeps the Dashboard banner clean (§5).
Per ADR_REVIEW R3, ``notification_id`` is ``TEXT`` (ULID) — overriding
the UUID typo in ADR-0021.

# Rollback steps
``alembic downgrade -1`` drops the table and its indexes. Alerts are
re-derivable from snapshots, so rollback only loses recovery state.
Operators should clear any stale alert banners in the UI cache.

# Impact scope
Net-new table; the ``library_id`` FK CASCADEs (ADR_REVIEW R8) and the
``notification_id`` FK uses ``ON DELETE SET NULL`` so notification
expiry / purge does not blow up an ongoing alert state machine.

Revision ID: m7_022_alerts
Revises: m7_021_eval_snapshots
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7_022_alerts"
down_revision: str | None = "m7_021_eval_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "library_id",
            sa.Text(),
            sa.ForeignKey("libraries.library_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "recovery_consecutive_days",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "notification_id",
            sa.Text(),
            sa.ForeignKey("notifications.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "severity IN ('info','warning','danger')",
            name="alerts_severity_enum",
        ),
        sa.CheckConstraint(
            "status IN ('active','recovered','expired')",
            name="alerts_status_enum",
        ),
    )
    op.create_index(
        "alerts_library_status_idx",
        "alerts",
        ["library_id", "status"],
    )
    op.create_index(
        "alerts_rule_status_idx",
        "alerts",
        ["rule", "status"],
    )
    op.create_index(
        "alerts_library_triggered_at_idx",
        "alerts",
        ["library_id", "triggered_at"],
    )
    # ADR-0021 §3 — at most one ACTIVE row per (library_id, rule).
    op.create_index(
        "alerts_active_one_per_rule_idx",
        "alerts",
        ["library_id", "rule"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("alerts_active_one_per_rule_idx", table_name="alerts")
    op.drop_index("alerts_library_triggered_at_idx", table_name="alerts")
    op.drop_index("alerts_rule_status_idx", table_name="alerts")
    op.drop_index("alerts_library_status_idx", table_name="alerts")
    op.drop_table("alerts")
