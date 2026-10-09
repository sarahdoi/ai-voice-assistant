from unittest.mock import AsyncMock

import httpx
import pytest

from sarjy.domain.results import ErrorCode, ToolResult
from sarjy.services.weather import OpenMeteoWeatherService
from sarjy.tools import SarjyAgent


def make_service(client, **kwargs):
    return OpenMeteoWeatherService(
        client,
        geocoding_url="https://geocoding.example/search",
        forecast_url="https://forecast.example/forecast",
        **kwargs,
    )


PLACE = {
    "name": "Lisbon",
    "latitude": 38.7,
    "longitude": -9.1,
    "country": "Portugal",
    "country_code": "PT",
    "admin1": "Lisbon",
}
FORECAST = {
    "timezone": "Europe/Lisbon",
    "current": {"time": "2026-10-09T12:00", "temperature_2m": 21},
    "current_units": {"temperature_2m": "°C"},
    "daily": {
        "time": ["2026-10-09", "2026-10-10"],
        "temperature_2m_max": [23, 24],
        "temperature_2m_min": [15, 16],
        "precipitation_probability_max": [10, 20],
    },
    "daily_units": {"temperature_2m_max": "°C", "precipitation_probability_max": "%"},
}


async def test_forecast_preserves_source_numbers_units_and_dates():
    def handler(request):
        if "geocoding" in request.url.host:
            assert request.url.host == "geocoding.example"
            assert request.url.params["countryCode"] == "PT"
            return httpx.Response(200, json={"results": [PLACE]})
        assert request.url.host == "forecast.example"
        assert request.url.params["forecast_days"] == "2"
        assert request.url.params["latitude"] == "38.7"
        return httpx.Response(200, json=FORECAST)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await make_service(client).get_forecast("Lisbon", "pt")
    assert result.ok
    assert result.data["current"] == FORECAST["current"]
    assert result.data["daily"] == FORECAST["daily"]
    assert result.data["daily_units"] == FORECAST["daily_units"]


async def test_ambiguity_stops_forecast_and_region_resolves_it():
    places = [dict(PLACE, name="Springfield", admin1=region) for region in ["Illinois", "Oregon"]]
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(
            200, json={"results": places} if "geocoding" in request.url.host else FORECAST
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = make_service(client)
        result = await service.get_forecast("Springfield")
        assert result.error_code == ErrorCode.AMBIGUOUS
        assert len(result.data["candidates"]) == 2
        assert len(calls) == 1
        result = await service.get_forecast("Springfield", "US", "Illinois")
        assert result.ok and result.data["location"]["admin1"] == "Illinois"


@pytest.mark.parametrize("status,expected_calls", [(503, 2), (400, 1), (429, 1)])
async def test_retries_only_server_errors(status, expected_calls):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await make_service(client).get_forecast("Lisbon")
    assert result.error_code == ErrorCode.UPSTREAM_ERROR
    assert len(calls) == expected_calls


async def test_timeout_retries_once_then_returns_error():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await make_service(client).get_forecast("Lisbon")
    assert result.error_code == ErrorCode.UPSTREAM_TIMEOUT
    assert len(calls) == 2


@pytest.mark.parametrize(
    "payload,code",
    [
        ({}, ErrorCode.NOT_FOUND),
        ([], ErrorCode.UPSTREAM_ERROR),
        ({"results": [None]}, ErrorCode.UPSTREAM_ERROR),
    ],
)
async def test_missing_or_malformed_geocoding_is_honest(payload, code):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    ) as client:
        result = await make_service(client).get_forecast("Lisbon")
    assert not result.ok and result.error_code == code


async def test_missing_forecast_never_returns_success():
    def handler(request):
        return httpx.Response(
            200,
            json={"results": [PLACE]}
            if "geocoding" in request.url.host
            else {"current": {"temperature_2m": None}, "daily": {}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert not (await make_service(client).get_forecast("Lisbon")).ok


async def test_fault_flag_and_empty_city_make_no_requests():
    client = AsyncMock()
    assert not (await make_service(client, fault=True).get_forecast("Lisbon")).ok
    assert not (await make_service(client).get_forecast(" ")).ok
    client.get.assert_not_called()


async def test_tool_uses_saved_city_and_clarifies_when_missing():
    memory, weather = AsyncMock(), AsyncMock()
    memory.recall.return_value = ToolResult.success({"memories": [{"value": "Lisbon"}]})
    weather.get_forecast.return_value = ToolResult.success({"source": "Open-Meteo"})
    agent = SarjyAgent("u", memory, weather)
    await agent.get_weather()
    memory.recall.assert_awaited_once_with("u", "city")
    weather.get_forecast.assert_awaited_once_with("Lisbon", None, None)
    memory.recall.return_value = ToolResult.success({"memories": []})
    weather.reset_mock()
    assert "INVALID_INPUT" in await agent.get_weather()
    weather.get_forecast.assert_not_called()
