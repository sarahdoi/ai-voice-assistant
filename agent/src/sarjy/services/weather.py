"""Open-Meteo adapter. Returns source data, never generated weather claims."""

import asyncio
import json
import logging
import math
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx

from sarjy.domain.results import ErrorCode, ToolResult

logger = logging.getLogger(__name__)
CURRENT_FIELDS = ("temperature_2m", "precipitation", "wind_speed_10m")
DAILY_FIELDS = ("temperature_2m_max", "temperature_2m_min", "precipitation_probability_max")
MAX_RESPONSE_BYTES = 256 * 1024


def number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def validate_forecast(data: dict[str, Any]) -> tuple[dict, dict]:
    current, daily = data["current"], data["daily"]
    datetime.fromisoformat(current["time"])
    ZoneInfo(data["timezone"])
    for field in CURRENT_FIELDS:
        if not number(current[field]) or not isinstance(data["current_units"][field], str):
            raise ValueError("Invalid current field")
    days = daily["time"]
    if not isinstance(days, list) or len(days) != 2:
        raise ValueError("Invalid daily dates")
    dates = [date.fromisoformat(day) for day in days]
    if (dates[1] - dates[0]).days != 1:
        raise ValueError("Nonconsecutive dates")
    for field in DAILY_FIELDS:
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
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
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
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise ValueError("Weather response too large")
                        body.extend(chunk)
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

    async def _resolve_place(
        self, city: str, country_code: str | None, region: str | None
    ) -> dict | ToolResult:
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
                return ToolResult.failure(ErrorCode.NOT_FOUND, "No matching city in that region.")
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
        return places[0]

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
            place = await self._resolve_place(city, country_code, region)
            if isinstance(place, ToolResult):
                return place
            forecast = await self._get(
                self.forecast_url,
                {
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": ",".join(CURRENT_FIELDS),
                    "daily": ",".join(DAILY_FIELDS),
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

    async def get_forecast(
        self, city: str, country_code: str | None = None, region: str | None = None
    ) -> ToolResult:
        result = await self.primary.get_forecast(city, country_code, region)
        if result.error_code in (ErrorCode.UPSTREAM_TIMEOUT, ErrorCode.UPSTREAM_ERROR):
            return await self.secondary.get_forecast(city, country_code, region)
        return result


class MetNorwayWeatherService:
    """Coordinate forecast fallback; city resolution still uses the primary geocoder."""

    def __init__(self, resolver: OpenMeteoWeatherService, *, url: str, user_agent: str):
        self.resolver, self.url, self.user_agent = resolver, url, user_agent
        self._cache: dict[tuple, tuple[dict, datetime, str | None]] = {}

    async def _forecast(self, place: dict) -> dict:
        coordinates = tuple(math.trunc(place[k] * 10000) / 10000 for k in ("latitude", "longitude"))
        cached = self._cache.get(coordinates)
        if cached and cached[1] > datetime.now(UTC):
            return cached[0]
        headers = {"User-Agent": self.user_agent}
        if cached and cached[2]:
            headers["If-Modified-Since"] = cached[2]
        async with self.resolver.client.stream(
            "GET",
            self.url,
            params=dict(zip(("lat", "lon"), coordinates, strict=True)),
            headers=headers,
        ) as response:
            if response.status_code != 304:
                response.raise_for_status()
            expires = parsedate_to_datetime(response.headers["Expires"])
            if expires.tzinfo is None:
                raise ValueError("Missing expiry timezone")
            if response.status_code == 304 and cached:
                data = cached[0]
            else:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ValueError("Weather response too large")
                    body.extend(chunk)
                data = json.loads(body)
                if not isinstance(data, dict):
                    raise ValueError("Invalid forecast")
            if len(self._cache) >= 64 and coordinates not in self._cache:
                self._cache.pop(next(iter(self._cache)))
            self._cache[coordinates] = (data, expires, response.headers.get("Last-Modified"))
            return data

    async def get_forecast(
        self, city: str, country_code: str | None = None, region: str | None = None
    ) -> ToolResult:
        try:
            place = await self.resolver._resolve_place(
                city.strip(),
                country_code.strip().upper() if country_code else None,
                region.strip() if region else None,
            )
            if isinstance(place, ToolResult):
                return place
            data = await self._forecast(place)
            properties = data["properties"]
            units = properties["meta"]["units"]
            periods = []
            for entry in properties["timeseries"][:48]:
                timestamp = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    raise ValueError("Missing forecast timezone")
                details = entry["data"]["instant"]["details"]
                values = {k: details[k] for k in ("air_temperature", "wind_speed")}
                if not all(number(v) for v in values.values()):
                    raise ValueError("Invalid forecast values")
                periods.append({"time": entry["time"], **values})
            if not periods or not all(
                isinstance(units[k], str) and units[k] for k in ("air_temperature", "wind_speed")
            ):
                raise ValueError("Missing forecast data")
            return ToolResult.success(
                {
                    "source": "MET Norway",
                    "source_url": "https://www.met.no/",
                    "license_url": "https://creativecommons.org/licenses/by/4.0/",
                    "location": {k: place.get(k) for k in ("name", "admin1", "country")},
                    "timezone": "UTC",
                    "forecast_periods": periods,
                    "units": {k: units[k] for k in ("air_temperature", "wind_speed")},
                }
            )
        except httpx.TimeoutException:
            return ToolResult.failure(
                ErrorCode.UPSTREAM_TIMEOUT, "Secondary weather lookup timed out."
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as error:
            logger.warning(
                "Secondary weather lookup rejected", extra={"error_type": type(error).__name__}
            )
            return ToolResult.failure(
                ErrorCode.UPSTREAM_ERROR, "Both weather providers are unavailable."
            )
