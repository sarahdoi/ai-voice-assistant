"""Postgres connection setup for memory. No voice SDK dependencies."""

from pathlib import Path

import asyncpg

from sarjy.config import Settings

# agent/db/migrations/001_memories.sql (the Dockerfile copies agent/db into the image).
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "migrations" / "001_memories.sql"


async def apply_schema(connection: asyncpg.Connection | asyncpg.Pool) -> None:
    """Create the memories table if it is missing. Idempotent, so safe on every start."""
    await connection.execute(SCHEMA_PATH.read_text())


async def connect_memory_pool(settings: Settings) -> asyncpg.Pool:
    """Open a small pool and make sure the schema exists.

    The connect timeout is long enough to wake a sleeping serverless database;
    each query keeps the short timeout so slow storage still fails fast.
    """
    if settings.database_url is None:
        raise ValueError("DATABASE_URL is not set")
    pool = await asyncpg.create_pool(
        settings.database_url.get_secret_value(),
        min_size=1,
        max_size=2,
        timeout=settings.db_connect_timeout_s,
        command_timeout=settings.db_timeout_s,
    )
    try:
        await apply_schema(pool)
    except BaseException:
        await pool.close()
        raise
    return pool
