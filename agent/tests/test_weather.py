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
        sleep=AsyncMock(),
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
    "current": {
        "time": "2026-10-09T12:00",
        "temperature_2m": 21,
        "precipitation": 0,
        "wind_speed_10m": 5,
    },
    "current_units": {"temperature_2m": "°C", "precipitation": "mm", "wind_speed_10m": "km/h"},
    "daily": {
        "time": ["2026-10-09", "2026-10-10"],
        "temperature_2m_max": [23, 24],
        "temperature_2m_min": [15, 16],
        "precipitation_probability_max": [10, 20],
    },
    "daily_units": {
        "temperature_2m_max": "°C",
        "temperature_2m_min": "°C",
        "precipitation_probability_max": "%",
    },
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
    places = [
        dict(PLACE, name="Springfield", admin1=region, country_code="US")
        for region in ["Illinois", "Oregon"]
    ]
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


@pytest.mark.parametrize(
    "field,value", [("temperature_2m", True), ("temperature_2m", float("inf"))]
)
def test_boolean_and_nonfinite_numbers_rejected(field, value):
    from copy import deepcopy

    from sarjy.services.weather import validate_forecast

    payload = deepcopy(FORECAST)
    payload["current"][field] = value
    with pytest.raises(ValueError):
        validate_forecast(payload)


def test_invalid_dates_probabilities_and_units_rejected():
    from copy import deepcopy

    from sarjy.services.weather import validate_forecast

    for part, key, value in [
        ("daily", "time", ["bad", "bad"]),
        ("daily", "precipitation_probability_max", [101, 20]),
        ("daily_units", "temperature_2m_min", None),
    ]:
        payload = deepcopy(FORECAST)
        payload[part][key] = value
        with pytest.raises((ValueError, TypeError)):
            validate_forecast(payload)


async def test_response_size_limit():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 262145))
    ) as client:
        result = await make_service(client).get_forecast("Lisbon")
    assert result.error_code == ErrorCode.UPSTREAM_ERROR


async def test_normalized_country_is_enforced_locally():
    def handler(request):
        assert request.url.params["countryCode"] == "US"
        return httpx.Response(200, json={"results": [PLACE]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await make_service(client).get_forecast(" Lisbon ", " us ", "  ")
    assert result.error_code == ErrorCode.NOT_FOUND


@pytest.mark.parametrize("failure", [503, "timeout"])
async def test_retry_recovers(failure):
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("timeout", request=request)
            return httpx.Response(failure)
        return httpx.Response(
            200, json={"results": [PLACE]} if "geocoding" in request.url.host else FORECAST
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (await make_service(client).get_forecast("Lisbon")).ok
    assert len(calls) == 3


async def test_cancellation_propagates_during_backoff():
    import asyncio

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as client:
        service = make_service(client)
        service.sleep = AsyncMock(side_effect=asyncio.CancelledError)
        with pytest.raises(asyncio.CancelledError):
            await service.get_forecast("Lisbon")


@pytest.mark.parametrize(
    "code,uses_fallback",
    [
        (ErrorCode.UPSTREAM_TIMEOUT, True),
        (ErrorCode.UPSTREAM_ERROR, True),
        (ErrorCode.AMBIGUOUS, False),
        (ErrorCode.NOT_FOUND, False),
        (ErrorCode.INVALID_INPUT, False),
    ],
)
async def test_simulated_provider_fallback(code, uses_fallback):
    from sarjy.services.weather import FallbackWeatherService

    primary, secondary = AsyncMock(), AsyncMock()
    primary.get_forecast.return_value = ToolResult.failure(code, "primary error")
    secondary.get_forecast.return_value = ToolResult.success({"source": "mock provider"})
    result = await FallbackWeatherService(primary, secondary).get_forecast("Lisbon", "PT")
    assert result.ok == uses_fallback
    if uses_fallback:
        secondary.get_forecast.assert_awaited_once_with("Lisbon", "PT", None)
        assert result.data["source"] == "mock provider"
    else:
        secondary.get_forecast.assert_not_called()


async def test_both_providers_fail_honestly():
    from sarjy.services.weather import FallbackWeatherService

    primary, secondary = AsyncMock(), AsyncMock()
    primary.get_forecast.return_value = ToolResult.failure(ErrorCode.UPSTREAM_TIMEOUT, "timeout")
    secondary.get_forecast.return_value = ToolResult.failure(
        ErrorCode.UPSTREAM_ERROR, "unavailable"
    )
    result = await FallbackWeatherService(primary, secondary).get_forecast("Lisbon")
    assert not result.ok and result.data is None


async def test_successful_primary_does_not_call_fallback():
    from sarjy.services.weather import FallbackWeatherService

    primary, secondary = AsyncMock(), AsyncMock()
    primary.get_forecast.return_value = ToolResult.success({"source": "primary"})
    assert (await FallbackWeatherService(primary, secondary).get_forecast("Lisbon")).ok
    secondary.get_forecast.assert_not_called()


async def test_http_cancellation_propagates():
    import asyncio

    def handler(request):
        raise asyncio.CancelledError

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(asyncio.CancelledError):
            await make_service(client).get_forecast("Lisbon")
