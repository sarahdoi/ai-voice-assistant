"""Persistent facts. No voice SDK dependencies; every query is user-scoped."""

import asyncio
import re
from collections.abc import Awaitable
from typing import Protocol

import asyncpg

from sarjy.domain.results import ErrorCode, ToolResult
from sarjy.policy import rule_category


class MemoryService(Protocol):
    async def remember(self, user_id: str, key: str, value: str) -> ToolResult: ...
    async def recall(self, user_id: str, key: str | None = None) -> ToolResult: ...
    async def correct(self, user_id: str, key: str, new_value: str) -> ToolResult: ...
    async def forget(self, user_id: str, key: str) -> ToolResult: ...
    async def mark_seen(self, user_id: str) -> ToolResult: ...
    async def delete_inactive(self, days: int) -> ToolResult: ...


class PostgresMemoryService:
    def __init__(self, pool: asyncpg.Pool, *, fault_write: bool = False) -> None:
        self.pool = pool
        self.fault_write = fault_write

    async def _query(self, sql: str, *args: str, write: bool = False) -> ToolResult:
        if write and self.fault_write:
            return ToolResult.failure(ErrorCode.STORAGE_ERROR, "Memory write failed.")
        try:
            rows = await self.pool.fetch(sql, *args)
            return ToolResult.success({"memories": [dict(row) for row in rows]})
        except TimeoutError:
            # A timed-out write may have committed. Never claim it failed definitively.
            return ToolResult.failure(
                ErrorCode.UPSTREAM_TIMEOUT,
                "Memory timed out; the outcome is uncertain. Recall before confirming a write.",
            )
        except (asyncpg.PostgresError, OSError):
            return ToolResult.failure(ErrorCode.STORAGE_ERROR, "Memory is unavailable.")

    def _validate(self, key: str, value: str) -> ToolResult | None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key) or not value.strip() or len(value) > 500:
            return ToolResult.failure(
                ErrorCode.INVALID_INPUT, "Use a short key and a nonempty fact."
            )
        # Deliberately conservative, incomplete pattern screening; not a security guarantee.
        sensitive = r"password|passwd|secret|api.?key|token|\bpin\b|card|bank|passport|ssn"
        if re.search(sensitive, key.replace("_", " ") + " " + value, re.I):
            return ToolResult.failure(
                ErrorCode.REFUSED_SENSITIVE, "Do not save credentials or IDs."
            )
        # A "fact" that is really an instruction would be read back into the prompt later.
        if rule_category(value) is not None:
            return ToolResult.failure(
                ErrorCode.REFUSED_UNSAFE, "Not saved: that is an instruction, not a fact."
            )
        return None

    async def remember(self, user_id: str, key: str, value: str) -> ToolResult:
        invalid = self._validate(key, value)
        if invalid:
            return invalid
        return await self._query(
            "INSERT INTO memories (user_id, key, value) VALUES ($1, $2, $3) "
            "ON CONFLICT (user_id, key) DO UPDATE "
            "SET value=EXCLUDED.value, updated_at=now(), last_seen_at=now() "
            "RETURNING key, value",
            user_id,
            key,
            value.strip(),
            write=True,
        )

    async def recall(self, user_id: str, key: str | None = None) -> ToolResult:
        if key is not None:
            return await self._query(
                "SELECT key, value FROM memories WHERE user_id=$1 AND key=$2",
                user_id,
                key,
            )
        return await self._query(
            "SELECT key, value FROM memories WHERE user_id=$1 ORDER BY key LIMIT 100",
            user_id,
        )

    async def correct(self, user_id: str, key: str, new_value: str) -> ToolResult:
        invalid = self._validate(key, new_value)
        if invalid:
            return invalid
        result = await self._query(
            "UPDATE memories SET value=$3, updated_at=now(), last_seen_at=now() "
            "WHERE user_id=$1 AND key=$2 "
            "RETURNING key, value",
            user_id,
            key,
            new_value.strip(),
            write=True,
        )
        if result.ok and not result.data["memories"]:
            return ToolResult.failure(ErrorCode.NOT_FOUND, "No saved fact to correct.")
        return result

    async def forget(self, user_id: str, key: str) -> ToolResult:
        result = await self._query(
            "DELETE FROM memories WHERE user_id=$1 AND key=$2 RETURNING key",
            user_id,
            key,
            write=True,
        )
        if result.ok:
            return ToolResult.success({"deleted": bool(result.data["memories"]), "key": key})
        return result

    async def mark_seen(self, user_id: str) -> ToolResult:
        """Record that this user started a call, so retention keeps their facts."""
        return await self._execute(
            "UPDATE memories SET last_seen_at=now() WHERE user_id=$1", user_id
        )

    async def delete_inactive(self, days: int) -> ToolResult:
        """Delete every fact of users who have not started a call for `days` days."""
        return await self._execute(
            "DELETE FROM memories WHERE last_seen_at < now() - make_interval(days => $1)", days
        )

    async def _execute(self, sql: str, *args: str | int) -> ToolResult:
        """Run a housekeeping write and report how many rows it touched."""
        if self.fault_write:
            return ToolResult.failure(ErrorCode.STORAGE_ERROR, "Memory write failed.")
        try:
            status = await self.pool.execute(sql, *args)  # e.g. "DELETE 3"
        except (asyncpg.PostgresError, OSError, TimeoutError):
            return ToolResult.failure(ErrorCode.STORAGE_ERROR, "Memory is unavailable.")
        return ToolResult.success({"rows": int(status.rsplit(" ", 1)[-1])})


class DeferredMemoryService:
    """Starts connecting at once, so a sleeping database wakes during the greeting.

    Tool calls wait for the connection only if it is not ready yet. A failed
    connection is reported honestly as unavailable storage, never as success.
    """

    def __init__(self, connect: Awaitable[asyncpg.Pool], *, fault_write: bool = False) -> None:
        self._task: asyncio.Future[asyncpg.Pool] = asyncio.ensure_future(connect)
        self._fault_write = fault_write
        self._service: PostgresMemoryService | None = None

    async def _ready(self) -> PostgresMemoryService | ToolResult:
        if self._service is None:
            try:
                # shield: an interrupted tool call must not cancel the shared connection.
                pool = await asyncio.shield(self._task)
            except (asyncpg.PostgresError, OSError, TimeoutError, ValueError):
                return ToolResult.failure(ErrorCode.STORAGE_ERROR, "Memory is unavailable.")
            self._service = PostgresMemoryService(pool, fault_write=self._fault_write)
        return self._service

    async def remember(self, user_id: str, key: str, value: str) -> ToolResult:
        service = await self._ready()
        return (
            service
            if isinstance(service, ToolResult)
            else await service.remember(user_id, key, value)
        )

    async def recall(self, user_id: str, key: str | None = None) -> ToolResult:
        service = await self._ready()
        return service if isinstance(service, ToolResult) else await service.recall(user_id, key)

    async def correct(self, user_id: str, key: str, new_value: str) -> ToolResult:
        service = await self._ready()
        return (
            service
            if isinstance(service, ToolResult)
            else await service.correct(user_id, key, new_value)
        )

    async def forget(self, user_id: str, key: str) -> ToolResult:
        service = await self._ready()
        return service if isinstance(service, ToolResult) else await service.forget(user_id, key)

    async def mark_seen(self, user_id: str) -> ToolResult:
        service = await self._ready()
        return service if isinstance(service, ToolResult) else await service.mark_seen(user_id)

    async def delete_inactive(self, days: int) -> ToolResult:
        service = await self._ready()
        return service if isinstance(service, ToolResult) else await service.delete_inactive(days)

    async def aclose(self) -> None:
        """Close the pool, or stop a connection still in progress."""
        if not self._task.done():
            self._task.cancel()
            return
        if not self._task.cancelled() and self._task.exception() is None:
            await self._task.result().close()


class NotImplementedMemoryService:
    """Honest fallback when no database is configured."""

    async def remember(self, user_id: str, key: str, value: str) -> ToolResult:
        return ToolResult.failure(ErrorCode.NOT_IMPLEMENTED, "Memory is not configured.")

    async def recall(self, user_id: str, key: str | None = None) -> ToolResult:
        return await self.remember(user_id, "", "")

    async def correct(self, user_id: str, key: str, new_value: str) -> ToolResult:
        return await self.remember(user_id, key, new_value)

    async def forget(self, user_id: str, key: str) -> ToolResult:
        return await self.remember(user_id, key, "")

    async def mark_seen(self, user_id: str) -> ToolResult:
        return await self.remember(user_id, "", "")

    async def delete_inactive(self, days: int) -> ToolResult:
        return await self.remember("", "", "")
