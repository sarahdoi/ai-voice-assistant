"""Postgres connection setup for memory. No voice SDK dependencies."""

from pathlib import Path

import asyncpg

from sarjy.config import Settings

# agent/db/migrations (the Dockerfile copies agent/db into the image).
MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations"


def migration_sql() -> list[str]:
    """Every migration, in file-name order."""
    return [path.read_text() for path in sorted(MIGRATIONS_DIR.glob("*.sql"))]


async def apply_schema(connection: asyncpg.Connection | asyncpg.Pool) -> None:
    """Bring the schema up to date. Every migration is idempotent, so safe on every start."""
    for sql in migration_sql():
        await connection.execute(sql)


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
