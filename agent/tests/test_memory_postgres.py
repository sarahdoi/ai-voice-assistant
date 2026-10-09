"""Optional real-Postgres check; uses a session-local temporary table only."""

import os

import asyncpg
import pytest

from sarjy.services.memory import PostgresMemoryService
from sarjy.storage import migration_sql


async def test_persistence_and_user_isolation():
    url = os.getenv("MEMORY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set MEMORY_TEST_DATABASE_URL to run the real Postgres check")
    connection = await asyncpg.connect(url, timeout=5)
    try:
        for sql in migration_sql():  # temp table shadows any real one for this session
            await connection.execute(sql.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE"))
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

        # Retention: only users inactive for longer than the limit are deleted.
        await connection.execute(
            "UPDATE pg_temp.memories SET last_seen_at = now() - interval '400 days' "
            "WHERE user_id = 'b'"
        )
        assert (await memory.remember("c", "name", "Sam")).ok
        assert (await memory.delete_inactive(365)).data == {"rows": 1}
        assert (await memory.recall("b")).data["memories"] == []
        assert (await memory.recall("c")).data["memories"] == [{"key": "name", "value": "Sam"}]
    finally:
        await connection.close()
