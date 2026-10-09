"""Retention: inactive guests are deleted, at most once a day, never in the call's way."""

from unittest.mock import AsyncMock

from sarjy.domain.results import ErrorCode, ToolResult
from sarjy.retention import RetentionSweeper
from sarjy.services.memory import PostgresMemoryService


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def memory_deleting(rows: int) -> AsyncMock:
    memory = AsyncMock()
    memory.delete_inactive.return_value = ToolResult.success({"rows": rows})
    return memory


async def test_sweep_runs_at_most_once_per_interval():
    clock, memory = Clock(), memory_deleting(3)
    sweeper = RetentionSweeper(interval_s=100, clock=clock)
    assert await sweeper.maybe_sweep(memory, 365) == 3
    clock.now = 50
    assert await sweeper.maybe_sweep(memory, 365) is None
    clock.now = 150
    assert await sweeper.maybe_sweep(memory, 365) == 3
    assert memory.delete_inactive.await_count == 2
    memory.delete_inactive.assert_awaited_with(365)


async def test_failed_sweep_is_retried_on_the_next_call():
    memory = AsyncMock()
    memory.delete_inactive.side_effect = [
        ToolResult.failure(ErrorCode.STORAGE_ERROR, "down"),
        ToolResult.success({"rows": 0}),
    ]
    sweeper = RetentionSweeper(interval_s=100, clock=Clock())
    assert await sweeper.maybe_sweep(memory, 365) is None
    assert await sweeper.maybe_sweep(memory, 365) == 0


async def test_zero_days_disables_retention():
    memory = memory_deleting(3)
    assert await RetentionSweeper(clock=Clock()).maybe_sweep(memory, 0) is None
    memory.delete_inactive.assert_not_called()


async def test_mark_seen_is_scoped_to_the_user():
    pool = AsyncMock()
    pool.execute.return_value = "UPDATE 2"
    result = await PostgresMemoryService(pool).mark_seen("user-a")
    sql, uid = pool.execute.call_args.args
    assert result.data == {"rows": 2}
    assert "WHERE user_id=$1" in sql and uid == "user-a"


async def test_delete_inactive_reports_rows_and_never_raises():
    pool = AsyncMock()
    pool.execute.return_value = "DELETE 4"
    assert (await PostgresMemoryService(pool).delete_inactive(365)).data == {"rows": 4}
    pool.execute.side_effect = OSError("down")
    result = await PostgresMemoryService(pool).delete_inactive(365)
    assert result.error_code is ErrorCode.STORAGE_ERROR
