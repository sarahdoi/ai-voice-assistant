"""Structured tool results.

Every tool returns a ToolResult so the model can only confirm what actually
succeeded, and never has to guess about failures.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class ErrorCode(StrEnum):
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID_INPUT = "INVALID_INPUT"
    REFUSED_SENSITIVE = "REFUSED_SENSITIVE"
    REFUSED_UNSAFE = "REFUSED_UNSAFE"
    UPSTREAM_TIMEOUT = "UPSTREAM_TIMEOUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class ToolResult(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    error_code: ErrorCode | None = None
    message: str = ""

    @classmethod
    def success(cls, data: dict[str, Any] | None = None, message: str = "") -> "ToolResult":
        return cls(ok=True, data=data or {}, message=message)

    @classmethod
    def failure(cls, code: ErrorCode, message: str) -> "ToolResult":
        return cls(ok=False, error_code=code, message=message)
