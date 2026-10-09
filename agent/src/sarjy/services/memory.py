"""Persistent facts. No voice SDK dependencies; every query is user-scoped."""

import re
from typing import Protocol

import asyncpg

from sarjy.domain.results import ErrorCode, ToolResult


class MemoryService(Protocol):
    async def remember(self, user_id: str, key: str, value: str) -> ToolResult: ...
    async def recall(self, user_id: str, key: str | None = None) -> ToolResult: ...
    async def correct(self, user_id: str, key: str, new_value: str) -> ToolResult: ...
    async def forget(self, user_id: str, key: str) -> ToolResult: ...


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
        return None

    async def remember(self, user_id: str, key: str, value: str) -> ToolResult:
        invalid = self._validate(key, value)
        if invalid:
            return invalid
        return await self._query(
            "INSERT INTO memories (user_id, key, value) VALUES ($1, $2, $3) "
            "ON CONFLICT (user_id, key) DO UPDATE SET value=EXCLUDED.value, updated_at=now() "
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
            "UPDATE memories SET value=$3, updated_at=now() WHERE user_id=$1 AND key=$2 "
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
