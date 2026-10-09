"""Weather service backed by Open-Meteo (geocoding + forecast).

Plain Python, no LiveKit imports. Implementation pending.
"""

from typing import Protocol

from sarjy.domain.results import ErrorCode, ToolResult


class WeatherService(Protocol):
    async def get_forecast(self, city: str) -> ToolResult: ...


class NotImplementedWeatherService:
    """Placeholder so the voice loop can run before weather is built."""

    async def get_forecast(self, city: str) -> ToolResult:
        return ToolResult.failure(ErrorCode.NOT_IMPLEMENTED, "Weather is not available yet.")
