"""m7_030 — create the immutable `library_purge_audit` table.

# Motivation
ADR-0022 §5 requires a tamper-evident permanent record of every library
purge — even after the library row itself is gone. ADR_REVIEW R1 fixes
the table name (`library_purge_audit`, not `archived_activity_log`), and
ADR_REVIEW §7 R8 requires the table to NOT be FK-cascaded so it survives
the parent library deletion.

# Rollback steps
``alembic downgrade -1`` drops the audit table. Operators must
acknowledge that any historical purge events written here are
unrecoverable; production downgrades should always logical-backup the
table first.

# Impact scope
Net-new table. Not FK-linked to `libraries.library_id` (deliberate per
§7 R8 — the audit row outlives the library). Indexed by `library_id`
for the operator dashboard and by `purged_at` for time-window queries.

Revision ID: m7_030_library_purge_audit
Revises: m7_002_task_queue
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7_030_library_purge_audit"
down_revision: str | None = "m7_022_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_purge_audit",
        sa.Column("audit_id", sa.Text(), primary_key=True),
        # Intentionally NOT a FK — the parent library row goes away as
        # part of the purge saga (ADR-0022 §3 step 5). The audit row is
        # the surviving evidence and must persist beyond CASCADE.
        sa.Column("library_id", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purged_by", sa.Text(), nullable=True),
        sa.Column("partial_resume_state", sa.Text(), nullable=True),
        sa.Column(
            "receipts_payload",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "library_purge_audit_library_idx",
        "library_purge_audit",
        ["library_id", "purged_at"],
    )
    op.create_index(
        "library_purge_audit_purged_at_idx",
        "library_purge_audit",
        ["purged_at"],
    )


def downgrade() -> None:
    op.drop_index("library_purge_audit_purged_at_idx", table_name="library_purge_audit")
    op.drop_index("library_purge_audit_library_idx", table_name="library_purge_audit")
    op.drop_table("library_purge_audit")
