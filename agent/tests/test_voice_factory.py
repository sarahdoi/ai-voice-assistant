"""Speech-to-speech providers skip the topic gate, so they must not start silently."""

import pytest

from sarjy.config import Settings, VoiceProvider
from sarjy.voice.factory import build_session


def settings(**overrides) -> Settings:
    return Settings(
        _env_file=None,
        voice_provider=VoiceProvider.GEMINI_LIVE,
        google_api_key="test-key",
        **overrides,
    )


def test_gemini_live_refuses_to_start_while_the_gate_is_on():
    with pytest.raises(ValueError, match="bypasses the topic gate"):
        build_session(settings(guard_mode="classifier"))
    with pytest.raises(ValueError, match="bypasses the topic gate"):
        build_session(settings(guard_mode="rules"))


async def test_gemini_live_needs_an_explicit_opt_in():
    try:
        build_session(settings(allow_ungated_realtime=True))
    except ValueError as error:  # past the gate check; plugin setup may still need more
        assert "topic gate" not in str(error)
