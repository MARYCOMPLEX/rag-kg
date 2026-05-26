"""m7_001 — create libraries table with M7 status columns.

# Motivation
M7 introduces the Library status machine (ADR-0013) and requires every
queue / activity / notification row to carry a strict FK to a Library
known to Postgres. The pre-M7 system kept Library metadata on the
filesystem (`apps/_shared/persistence/library_fs.py`); from M7 the
relational store becomes the single source of truth.

# Rollback steps
``alembic downgrade -1`` drops the ``libraries`` table. Note this also
implicitly cascades any FK rows from later migrations — run a logical
backup before downgrading in production.

# Impact scope
Net-new table; no existing Postgres rows are modified. The filesystem
metadata directory is untouched and remains the authoritative copy
during the M7 cutover. A separate data-migration script (``scripts/
sync_libraries_fs_to_pg.py`` — out of scope here) replays filesystem
rows into the new table.

Revision ID: m7_001_libraries
Revises:
Create Date: 2026-05-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "m7_001_libraries"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "libraries",
        sa.Column("library_id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'healthy'"),
        ),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
        # Soft check on language enum per ADR_REVIEW R10.
        sa.CheckConstraint(
            "language IS NULL OR language IN ('en', 'zh', 'mixed')",
            name="libraries_language_enum",
        ),
        sa.CheckConstraint(
            "status IN ('healthy', 'indexing', 'stale_community', 'purging', 'partial_purged')",
            name="libraries_status_enum",
        ),
    )


def downgrade() -> None:
    op.drop_table("libraries")
