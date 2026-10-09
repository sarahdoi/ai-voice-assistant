"""Scaffold checks: config loads, results are structured, and no tool
lets the model choose a user_id."""

import inspect

from sarjy.config import Settings, VoiceProvider
from sarjy.domain.results import ErrorCode, ToolResult
from sarjy.services.memory import NotImplementedMemoryService
from sarjy.services.weather import NotImplementedWeatherService
from sarjy.tools import SarjyAgent


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("VOICE_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.voice_provider is VoiceProvider.LIVEKIT_PIPELINE


def test_tool_result_helpers():
    ok = ToolResult.success({"key": "favorite_color"})
    assert ok.ok and ok.error_code is None
    bad = ToolResult.failure(ErrorCode.NOT_FOUND, "no such city")
    assert not bad.ok and bad.error_code is ErrorCode.NOT_FOUND


async def test_placeholders_fail_honestly():
    assert not (await NotImplementedMemoryService().remember("u1", "k", "v")).ok
    assert not (await NotImplementedWeatherService().get_forecast("Lisbon")).ok


def test_no_tool_accepts_user_id():
    tool_names = ["remember", "recall", "correct", "forget", "get_weather"]
    for name in tool_names:
        fn = getattr(SarjyAgent, name)
        fn = getattr(fn, "__wrapped__", fn)
        params = inspect.signature(fn).parameters
        assert "user_id" not in params, f"{name} must not expose user_id to the model"
