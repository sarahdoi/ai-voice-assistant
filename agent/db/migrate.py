"""Apply all migrations: cd agent && uv run python db/migrate.py."""

import asyncio

import asyncpg

from sarjy.config import get_settings
from sarjy.storage import apply_schema


async def main() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("Set DATABASE_URL in .env first.")
    connection = await asyncpg.connect(
        settings.database_url.get_secret_value(), timeout=settings.db_connect_timeout_s
    )
    try:
        await apply_schema(connection)
    finally:
        await connection.close()
    print("Memory schema ready.")


if __name__ == "__main__":
    asyncio.run(main())
