"""Live endpoint contracts. Opt in with RUN_WEATHER_INTEGRATION=1."""

import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from sarjy.config import Settings
from sarjy.services.weather import (
    CURRENT_FIELDS,
    DAILY_FIELDS,
    OpenMeteoWeatherService,
    validate_forecast,
)

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WEATHER_INTEGRATION") != "1", reason="Live weather tests are opt-in"
)


@pytest.fixture
async def weather():
    settings = Settings()
    async with httpx.AsyncClient(timeout=settings.weather_timeout_s) as client:
        yield OpenMeteoWeatherService(
            client,
            geocoding_url=str(settings.weather_geocoding_url),
            forecast_url=str(settings.weather_forecast_url),
        )


async def test_geocoding_endpoint_contract(weather):
    data = await weather._get(
        weather.geocoding_url, {"name": "Riyadh", "countryCode": "SA", "count": 5}
    )
    matches = [p for p in data["results"] if p["name"] == "Riyadh" and p["country_code"] == "SA"]
    assert matches
    assert all(24 < p["latitude"] < 25 and 46 < p["longitude"] < 47 for p in matches)


async def test_forecast_endpoint_contract(weather):
    data = await weather._get(
        weather.forecast_url,
        {
            "latitude": 24.7136,
            "longitude": 46.6753,
            "current": ",".join(CURRENT_FIELDS),
            "daily": ",".join(DAILY_FIELDS),
            "timezone": "auto",
            "forecast_days": 2,
        },
    )
    current, daily = validate_forecast(data)
    assert data["current_units"]["temperature_2m"] == "°C"
    assert data["daily_units"]["precipitation_probability_max"] == "%"
    assert date.fromisoformat(daily["time"][0]) == datetime.now(ZoneInfo(data["timezone"])).date()
    assert datetime.fromisoformat(current["time"]).date() == date.fromisoformat(daily["time"][0])


async def test_real_adapter_end_to_end(weather):
    result = await weather.get_forecast("Riyadh", "SA")
    assert result.ok, result.error_code
    assert result.data["source"] == "Open-Meteo"
    assert result.data["location"]["name"] == "Riyadh"
    assert result.data["location"]["country"] == "Saudi Arabia"
    validate_forecast(result.data)


async def test_secondary_endpoint_after_primary_failure(weather):
    from unittest.mock import AsyncMock

    from sarjy.domain.results import ErrorCode, ToolResult
    from sarjy.services.weather import FallbackWeatherService, MetNorwayWeatherService

    settings = Settings()
    primary = AsyncMock()
    primary.get_forecast.return_value = ToolResult.failure(
        ErrorCode.UPSTREAM_ERROR, "Simulated primary outage"
    )
    secondary = MetNorwayWeatherService(
        weather, url=str(settings.weather_fallback_url), user_agent=settings.weather_user_agent
    )
    result = await FallbackWeatherService(primary, secondary).get_forecast("Riyadh", "SA")
    assert result.ok, result.error_code
    assert result.data["source"] == "MET Norway"
    assert result.data["forecast_periods"]
