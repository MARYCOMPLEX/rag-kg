"""m7_010 — create the durable ``notifications`` table + LISTEN/NOTIFY trigger.

# Motivation
ADR-0011 §1 specifies a Postgres ``notifications`` table as the single
source of truth for the top-bar Notify center: durable read/unread state,
TTL-based retention, and ``LISTEN/NOTIFY`` realtime push. This migration
materialises the table, the supporting partial indexes, and the after-
insert trigger that fires ``pg_notify('notifications_channel', ...)``
with the row id so SSE handlers can fan out the row.

# Rollback steps
``alembic downgrade -1`` drops the trigger, function, indexes, and table
in dependency order. Operators should drain SSE consumers first
(``GET /v1/notifications/stream`` connections) — a bare downgrade leaves
the API returning 500s from the notification routes until the table is
recreated by a re-upgrade.

# Impact scope
Net-new table. ``library_id`` is a nullable FK to ``libraries`` with
``ON DELETE CASCADE`` per ADR_REVIEW R8 — purging a Library cleans up
its notifications automatically. Globals (``library_id IS NULL``) are
unaffected by cascades.

Revision ID: m7_010_notifications
Revises: m7_002_task_queue
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7_010_notifications"
down_revision: str | None = "m7_002_task_queue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TRIGGER_FN_SQL = """
CREATE OR REPLACE FUNCTION notifications_notify()
RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify(
        'notifications_channel',
        json_build_object(
            'id', NEW.id,
            'library_id', NEW.library_id,
            'type', NEW.type
        )::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


_TRIGGER_DDL = """
CREATE TRIGGER notifications_after_insert
AFTER INSERT ON notifications
FOR EACH ROW EXECUTE FUNCTION notifications_notify();
"""


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "library_id",
            sa.Text(),
            sa.ForeignKey("libraries.library_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now() + interval '90 days'"),
        ),
        sa.Column("dedup_key", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'danger')",
            name="notifications_severity_enum",
        ),
        sa.UniqueConstraint("dedup_key", name="notifications_dedup_uq"),
    )
    op.create_index(
        "notifications_unread_idx",
        "notifications",
        ["created_at"],
        postgresql_where=sa.text("read = FALSE"),
        postgresql_using="btree",
    )
    op.create_index(
        "notifications_library_unread_idx",
        "notifications",
        ["library_id", "created_at"],
        postgresql_where=sa.text("read = FALSE"),
    )
    op.create_index(
        "notifications_expires_idx",
        "notifications",
        ["expires_at"],
    )
    op.execute(_TRIGGER_FN_SQL)
    op.execute(_TRIGGER_DDL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS notifications_after_insert ON notifications")
    op.execute("DROP FUNCTION IF EXISTS notifications_notify()")
    op.drop_index("notifications_expires_idx", table_name="notifications")
    op.drop_index("notifications_library_unread_idx", table_name="notifications")
    op.drop_index("notifications_unread_idx", table_name="notifications")
    op.drop_table("notifications")
