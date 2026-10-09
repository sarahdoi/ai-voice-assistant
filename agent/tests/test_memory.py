from unittest.mock import AsyncMock

import asyncpg
import pytest

from sarjy.domain.results import ErrorCode
from sarjy.services.memory import PostgresMemoryService


@pytest.mark.parametrize(
    "method,args",
    [
        ("remember", ("favorite_color", "teal")),
        ("recall", ("favorite_color",)),
        ("recall", ()),
        ("correct", ("favorite_color", "green")),
        ("forget", ("favorite_color",)),
    ],
)
async def test_identity_is_bound_to_every_query(method, args):
    pool = AsyncMock()
    pool.fetch.return_value = [{"key": "favorite_color", "value": "teal"}]
    await getattr(PostgresMemoryService(pool), method)("user-a", *args)
    sql, uid, *values = pool.fetch.call_args.args
    assert uid == "user-a"
    assert "user_id" in sql and "$1" in sql
    assert "user-a" not in sql  # identity is parameterized, never interpolated


@pytest.mark.parametrize(
    "key,value",
    [
        ("favorite_color", ""),
        ("bad key", "teal"),
        ("password", "example"),
        ("api_key", "example"),
    ],
)
async def test_invalid_or_sensitive_input_never_writes(key, value):
    pool = AsyncMock()
    assert not (await PostgresMemoryService(pool).remember("u", key, value)).ok
    pool.fetch.assert_not_called()


async def test_correction_requires_existing_fact():
    pool = AsyncMock()
    pool.fetch.return_value = []
    result = await PostgresMemoryService(pool).correct("u", "favorite_color", "green")
    assert result.error_code == ErrorCode.NOT_FOUND


async def test_forget_does_not_return_deleted_value():
    pool = AsyncMock()
    pool.fetch.return_value = [{"key": "favorite_color"}]
    result = await PostgresMemoryService(pool).forget("u", "favorite_color")
    assert result.data == {"deleted": True, "key": "favorite_color"}
    assert pool.fetch.call_args.args[0].startswith("DELETE")


@pytest.mark.parametrize(
    "error,code",
    [
        (asyncpg.PostgresError(), ErrorCode.STORAGE_ERROR),
        (TimeoutError(), ErrorCode.UPSTREAM_TIMEOUT),
    ],
)
async def test_storage_errors_return_honest_results(error, code):
    pool = AsyncMock()
    pool.fetch.side_effect = error
    result = await PostgresMemoryService(pool).remember("u", "favorite_color", "teal")
    assert not result.ok and result.error_code == code


async def test_fault_injection_does_not_write():
    pool = AsyncMock()
    result = await PostgresMemoryService(pool, fault_write=True).remember("u", "color", "teal")
    assert result.error_code == ErrorCode.STORAGE_ERROR
    pool.fetch.assert_not_called()
