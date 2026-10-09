"""The UI is told what really happened, never what the model claims."""

from unittest.mock import AsyncMock

from sarjy.domain.results import ErrorCode, ToolResult
from sarjy.tools import SarjyAgent


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def emit(self, event: dict) -> None:
        self.events.append(event)

    def of(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["type"] == kind]


def make_agent(memory=None, weather=None) -> tuple[SarjyAgent, RecordingSink]:
    sink = RecordingSink()
    agent = SarjyAgent("user-a", memory or AsyncMock(), weather or AsyncMock(), events=sink)
    return agent, sink


def call(tool):
    """Call the undecorated tool body."""
    return getattr(tool, "__wrapped__", tool)


async def test_successful_save_reports_the_stored_value():
    memory = AsyncMock()
    memory.remember.return_value = ToolResult.success(
        {"memories": [{"key": "favorite_color", "value": "teal"}]}
    )
    agent, sink = make_agent(memory)
    await call(SarjyAgent.remember)(agent, "favorite_color", "teal")
    assert sink.of("memory_changed") == [
        {"type": "memory_changed", "op": "saved", "key": "favorite_color", "value": "teal"}
    ]
    started, finished = sink.of("tool_started")[0], sink.of("tool_finished")[0]
    assert started["id"] == finished["id"] and finished["ok"] is True
    assert isinstance(finished["ms"], int)


async def test_refused_fact_never_sends_its_value():
    memory = AsyncMock()
    memory.remember.return_value = ToolResult.failure(ErrorCode.REFUSED_SENSITIVE, "No.")
    agent, sink = make_agent(memory)
    await call(SarjyAgent.remember)(agent, "card_number", "4111 1111 1111 1111")
    (event,) = sink.of("memory_changed")
    assert event == {"type": "memory_changed", "op": "refused", "key": "card_number"}
    assert "4111" not in str(sink.events)


async def test_failed_write_is_reported_as_failed_not_saved():
    memory = AsyncMock()
    memory.correct.return_value = ToolResult.failure(
        ErrorCode.STORAGE_ERROR, "Memory is unavailable."
    )
    agent, sink = make_agent(memory)
    await call(SarjyAgent.correct)(agent, "favorite_color", "green")
    (event,) = sink.of("memory_changed")
    assert event["op"] == "failed" and "value" not in event
    assert sink.of("tool_finished")[0]["ok"] is False


async def test_forgetting_a_missing_fact_changes_nothing_on_screen():
    memory = AsyncMock()
    memory.forget.return_value = ToolResult.success({"deleted": False, "key": "coffee"})
    agent, sink = make_agent(memory)
    await call(SarjyAgent.forget)(agent, "coffee")
    assert sink.of("memory_changed") == []


async def test_weather_reports_place_and_source():
    weather = AsyncMock()
    weather.get_forecast.return_value = ToolResult.success(
        {"source": "Open-Meteo", "location": {"name": "Lisbon"}}
    )
    agent, sink = make_agent(weather=weather)
    await call(SarjyAgent.get_weather)(agent, "Lisbon")
    assert sink.of("tool_finished")[0]["detail"] == "Lisbon · Open-Meteo"
