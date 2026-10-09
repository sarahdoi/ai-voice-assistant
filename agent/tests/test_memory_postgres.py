"""Optional real-Postgres check; uses a session-local temporary table only."""

import os
from pathlib import Path

import asyncpg
import pytest

from sarjy.services.memory import PostgresMemoryService


async def test_persistence_and_user_isolation():
    url = os.getenv("MEMORY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set MEMORY_TEST_DATABASE_URL to run the real Postgres check")
    connection = await asyncpg.connect(url, timeout=5)
    try:
        schema = (Path(__file__).parents[1] / "db/migrations/001_memories.sql").read_text()
        await connection.execute(schema.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE"))
        memory = PostgresMemoryService(connection)
        assert (await memory.remember("a", "favorite_color", "teal")).ok
        assert (await memory.remember("b", "favorite_color", "blue")).ok
        assert (await memory.correct("a", "favorite_color", "green")).ok
        # Recreate service to prove state belongs to storage, not the service instance.
        memory = PostgresMemoryService(connection)
        assert (await memory.recall("a")).data["memories"] == [
            {"key": "favorite_color", "value": "green"}
        ]
        assert (await memory.forget("a", "favorite_color")).ok
        assert (await memory.recall("a")).data["memories"] == []
        assert (await memory.recall("b")).data["memories"] == [
            {"key": "favorite_color", "value": "blue"}
        ]
    finally:
        await connection.close()
