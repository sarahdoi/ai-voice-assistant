"""Open-Meteo adapter. Returns source data, never generated weather claims."""

import asyncio
import logging
import math
import re
from datetime import date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx

from sarjy.domain.results import ErrorCode, ToolResult

logger = logging.getLogger(__name__)


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_forecast(data):
    current, daily = data["current"], data["daily"]
    datetime.fromisoformat(current["time"])
    ZoneInfo(data["timezone"])
    for field in ("temperature_2m", "precipitation", "wind_speed_10m"):
        if not number(current[field]) or not isinstance(data["current_units"][field], str):
            raise ValueError("Invalid current field")
    days = daily["time"]
    if not isinstance(days, list) or len(days) != 2:
        raise ValueError("Invalid daily dates")
    dates = [date.fromisoformat(day) for day in days]
    if (dates[1] - dates[0]).days != 1:
        raise ValueError("Nonconsecutive dates")
    for field in ("temperature_2m_max", "temperature_2m_min", "precipitation_probability_max"):
        values = daily[field]
        if not isinstance(values, list) or len(values) != 2:
            raise ValueError("Invalid daily array")
        if not isinstance(data["daily_units"][field], str) or not data["daily_units"][field]:
            raise ValueError("Missing units")
        for value in values:
            if value is not None and (
                not number(value)
                or (field == "precipitation_probability_max" and not 0 <= value <= 100)
            ):
                raise ValueError("Invalid daily value")
    return current, daily


class WeatherService(Protocol):
    async def get_forecast(
        self, city: str, country_code: str | None = None, region: str | None = None
    ) -> ToolResult: ...


class OpenMeteoWeatherService:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        geocoding_url: str,
        forecast_url: str,
        fault: bool = False,
        sleep=asyncio.sleep,
    ) -> None:
        self.client = client
        self.geocoding_url = geocoding_url
        self.forecast_url = forecast_url
        self.fault = fault
        self.sleep = sleep

    async def _get(self, url: str, params: dict) -> dict:
        # Retry only timeouts and 5xx, once. Cancellation is allowed to propagate.
        for attempt in range(2):
            try:
                async with self.client.stream("GET", url, params=params) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > 262144:
                            raise ValueError("Weather response too large")
                        body.extend(chunk)
                    import json

                    data = json.loads(body)
                    if not isinstance(data, dict):
                        raise ValueError("Expected an object")
                return data
            except (httpx.TimeoutException, httpx.HTTPStatusError) as error:
                retryable = (
                    isinstance(error, httpx.TimeoutException) or error.response.status_code >= 500
                )
                if attempt or not retryable:
                    raise
                await self.sleep(0.1)

    async def get_forecast(
        self, city: str, country_code: str | None = None, region: str | None = None
    ) -> ToolResult:
        city = city.strip()
        country_code = country_code.strip().upper() or None if country_code else None
        region = region.strip() or None if region else None
        if not city or len(city) > 100:
            return ToolResult.failure(ErrorCode.INVALID_INPUT, "Which city?")
        if country_code and not re.fullmatch(r"[A-Z]{2}", country_code):
            return ToolResult.failure(ErrorCode.INVALID_INPUT, "Use a two-letter country code.")
        if self.fault:
            return ToolResult.failure(
                ErrorCode.UPSTREAM_ERROR, "Weather is temporarily unavailable."
            )
        try:
            params = {"name": city, "count": 10, "language": "en", "format": "json"}
            if country_code:
                params["countryCode"] = country_code.upper()
            geocoding = await self._get(self.geocoding_url, params)
            places = geocoding.get("results", [])
            if not isinstance(places, list):
                raise ValueError("Invalid places")
            for place in places:
                if not isinstance(place, dict) or not isinstance(place.get("name"), str):
                    raise ValueError("Invalid place")
                if not number(place.get("latitude")) or not -90 <= place["latitude"] <= 90:
                    raise ValueError("Invalid latitude")
                if not number(place.get("longitude")) or not -180 <= place["longitude"] <= 180:
                    raise ValueError("Invalid longitude")
            if country_code:
                places = [p for p in places if p.get("country_code") == country_code]
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
                self.forecast_url,
                {
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,precipitation,wind_speed_10m",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 2,
                },
            )
            current, daily = validate_forecast(forecast)
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
            logger.warning("Weather lookup timed out after retry")
            return ToolResult.failure(ErrorCode.UPSTREAM_TIMEOUT, "Weather lookup timed out.")
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as error:
            logger.warning("Weather lookup rejected", extra={"error_type": type(error).__name__})
            return ToolResult.failure(
                ErrorCode.UPSTREAM_ERROR, "Weather data is unavailable or invalid."
            )


class NotImplementedWeatherService:
    async def get_forecast(
        self, city: str, country_code: str | None = None, region: str | None = None
    ) -> ToolResult:
        return ToolResult.failure(ErrorCode.NOT_IMPLEMENTED, "Weather is not available yet.")


class FallbackWeatherService:
    """Only fail over on upstream failures; never bypass ambiguity or invalid input."""

    def __init__(self, primary: WeatherService, secondary: WeatherService) -> None:
        self.primary, self.secondary = primary, secondary

    async def get_forecast(self, city, country_code=None, region=None) -> ToolResult:
        result = await self.primary.get_forecast(city, country_code, region)
        if result.error_code in (ErrorCode.UPSTREAM_TIMEOUT, ErrorCode.UPSTREAM_ERROR):
            return await self.secondary.get_forecast(city, country_code, region)
        return result
