"""Apply the fresh schema: cd agent && uv run python db/migrate.py."""

import asyncio
from pathlib import Path

import asyncpg

from sarjy.config import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("Set DATABASE_URL in .env first.")
    connection = await asyncpg.connect(
        settings.database_url.get_secret_value(), timeout=settings.db_connect_timeout_s
    )
    try:
        await connection.execute(
            (Path(__file__).parent / "migrations/001_memories.sql").read_text()
        )
    finally:
        await connection.close()
    print("Memory schema ready.")


if __name__ == "__main__":
    asyncio.run(main())
