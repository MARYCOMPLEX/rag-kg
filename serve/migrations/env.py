"""Alembic env file.

Loads the sqlalchemy URL from the project Settings so a single source of
truth (`packages/core/config.py`) controls every connection. Supports
async drivers (`postgresql+asyncpg://`) by running migrations inside an
asyncio event loop.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from packages.core.config import Settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_url() -> str:
    override = os.environ.get("RKB_ALEMBIC_URL")
    if override:
        return override
    return Settings().postgres_url


target_metadata = None  # We use raw `op.*` ops; no autogenerate metadata.


def run_migrations_offline() -> None:
    """Render SQL without a live connection."""
    context.configure(
        url=_resolve_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    engine: AsyncEngine = create_async_engine(_resolve_url(), future=True)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    """Run migrations against a live (async) engine."""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
