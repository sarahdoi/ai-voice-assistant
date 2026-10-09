"""Memory service: remember, recall, correct, forget.

Plain Python, no LiveKit imports. Every method takes an explicit user_id,
which comes from the verified participant identity and never from the model.
Implementation pending.
"""

from typing import Protocol

from sarjy.domain.results import ErrorCode, ToolResult


class MemoryService(Protocol):
    async def remember(self, user_id: str, key: str, value: str) -> ToolResult: ...
    async def recall(self, user_id: str, key: str | None = None) -> ToolResult: ...
    async def correct(self, user_id: str, key: str, new_value: str) -> ToolResult: ...
    async def forget(self, user_id: str, key: str) -> ToolResult: ...


class NotImplementedMemoryService:
    """Placeholder so the voice loop can run before memory is built."""

    async def _todo(self) -> ToolResult:
        return ToolResult.failure(ErrorCode.NOT_IMPLEMENTED, "Memory is not available yet.")

    async def remember(self, user_id: str, key: str, value: str) -> ToolResult:
        return await self._todo()

    async def recall(self, user_id: str, key: str | None = None) -> ToolResult:
        return await self._todo()

    async def correct(self, user_id: str, key: str, new_value: str) -> ToolResult:
        return await self._todo()

    async def forget(self, user_id: str, key: str) -> ToolResult:
        return await self._todo()
