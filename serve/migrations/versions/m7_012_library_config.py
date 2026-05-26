"""m7_012 — create the ``library_config`` JSONB-overrides table.

# Motivation
ADR-0012 §1 specifies a single-row-per-library configuration table with a
JSONB ``overrides`` blob so override schema can evolve in Pydantic
without forcing alembic migrations every time a new field is added. A
GIN index on ``overrides`` supports occasional "find all libraries
running embedder X" admin queries.

# Rollback steps
``alembic downgrade -1`` drops the GIN index then the table. Effective
overrides revert to global defaults instantly — no data migration is
required, but anything that read overrides between upgrade and
downgrade will silently flip back to globals.

# Impact scope
Net-new table. ``library_id`` is both PK and FK to ``libraries`` with
``ON DELETE CASCADE`` per ADR_REVIEW R8 — purging a Library wipes its
config row automatically, matching ADR-0003's "drop everything" purge
semantics.

Revision ID: m7_012_library_config
Revises: m7_011_activity_log
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7_012_library_config"
down_revision: str | None = "m7_011_activity_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_config",
        sa.Column(
            "library_id",
            sa.Text(),
            sa.ForeignKey("libraries.library_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "overrides",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_by",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'system'"),
        ),
    )
    op.execute(
        """
        CREATE INDEX library_config_overrides_gin
            ON library_config
            USING GIN (overrides jsonb_path_ops);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS library_config_overrides_gin")
    op.drop_table("library_config")
