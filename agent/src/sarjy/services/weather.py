"""Open-Meteo adapter. Returns source data, never generated weather claims."""

import asyncio
import random
from typing import Protocol

import httpx

from sarjy.domain.results import ErrorCode, ToolResult


class WeatherService(Protocol):
    async def get_forecast(
        self, city: str, country_code: str | None = None, region: str | None = None
    ) -> ToolResult: ...


class OpenMeteoWeatherService:
    def __init__(self, client: httpx.AsyncClient, *, fault: bool = False) -> None:
        self.client = client
        self.fault = fault

    async def _get(self, url: str, params: dict) -> dict:
        # Retry only timeouts and 5xx, once. Cancellation is allowed to propagate.
        for attempt in range(2):
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
                return data
            except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
                retryable = (
                    isinstance(error, httpx.TimeoutException) or error.response.status_code >= 500
                )
                if attempt or not retryable:
                    raise
                await asyncio.sleep(random.uniform(0.05, 0.15))
        raise RuntimeError("Unreachable")

    async def get_forecast(
        self, city: str, country_code: str | None = None, region: str | None = None
    ) -> ToolResult:
        city = city.strip()
        if not city or len(city) > 100:
            return ToolResult.failure(ErrorCode.INVALID_INPUT, "Which city?")
        if country_code and (len(country_code) != 2 or not country_code.isalpha()):
            return ToolResult.failure(ErrorCode.INVALID_INPUT, "Use a two-letter country code.")
        if self.fault:
            return ToolResult.failure(
                ErrorCode.UPSTREAM_ERROR, "Weather is temporarily unavailable."
            )
        try:
            params = {"name": city, "count": 10, "language": "en", "format": "json"}
            if country_code:
                params["countryCode"] = country_code.upper()
            geocoding = await self._get("https://geocoding-api.open-meteo.com/v1/search", params)
            places = geocoding.get("results", [])
            if not places:
                return ToolResult.failure(
                    ErrorCode.NOT_FOUND, "No matching city. Ask for another name."
                )
            # Prefer exact names, but never silently pick among equally named cities.
            exact = [p for p in places if p["name"].casefold() == city.casefold()]
            places = exact or places
            if region:
                places = [p for p in places if p.get("admin1", "").casefold() == region.casefold()]
                if not places:
                    return ToolResult.failure(
                        ErrorCode.NOT_FOUND, "No matching city in that region."
                    )
            if len(places) > 1:
                candidates = [
                    {k: p.get(k) for k in ("name", "admin1", "country", "country_code")}
                    for p in places[:5]
                ]
                return ToolResult(
                    ok=False,
                    error_code=ErrorCode.AMBIGUOUS,
                    data={"candidates": candidates},
                    message="Ask for city, country or state/region. Do not report weather yet.",
                )
            place = places[0]
            forecast = await self._get(
                "https://api.open-meteo.com/v1/forecast",
                {
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,precipitation,wind_speed_10m",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 2,
                },
            )
            current, daily = forecast["current"], forecast["daily"]
            if not isinstance(current["temperature_2m"], (int, float)):
                raise ValueError("Missing current temperature")
            days = daily["time"]
            fields = ("temperature_2m_max", "temperature_2m_min", "precipitation_probability_max")
            if len(days) != 2 or any(len(daily[field]) != len(days) for field in fields):
                raise ValueError("Incomplete daily forecast")
            return ToolResult.success(
                {
                    "source": "Open-Meteo",
                    "source_url": "https://open-meteo.com/",
                    "location": {k: place.get(k) for k in ("name", "admin1", "country")},
                    "timezone": forecast["timezone"],
                    "current": current,
                    "current_units": forecast["current_units"],
                    "daily": daily,
                    "daily_units": forecast["daily_units"],
                }
            )
        except httpx.TimeoutException:
            return ToolResult.failure(ErrorCode.UPSTREAM_TIMEOUT, "Weather lookup timed out.")
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
            return ToolResult.failure(
                ErrorCode.UPSTREAM_ERROR, "Weather data is unavailable or invalid."
            )


class NotImplementedWeatherService:
    async def get_forecast(
        self, city: str, country_code: str | None = None, region: str | None = None
    ) -> ToolResult:
        return ToolResult.failure(ErrorCode.NOT_IMPLEMENTED, "Weather is not available yet.")
