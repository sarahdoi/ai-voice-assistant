"""Configuration failures must be explicit, never silently switch providers."""

import pytest

from sarjy.config import Settings, VoiceProvider
from sarjy.voice.factory import build_session


def test_gemini_without_key_fails_before_session_creation():
    settings = Settings(
        _env_file=None, voice_provider=VoiceProvider.GEMINI_LIVE, google_api_key=None
    )
    with pytest.raises(ValueError, match="GOOGLE_API_KEY is required"):
        build_session(settings)


def test_unimplemented_provider_does_not_fall_back():
    settings = Settings(_env_file=None, voice_provider=VoiceProvider.DEEPGRAM_CASCADE)
    with pytest.raises(NotImplementedError, match="stretch scope"):
        build_session(settings)
