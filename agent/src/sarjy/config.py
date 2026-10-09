"""Typed settings, loaded once from environment variables (or .env)."""

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceProvider(StrEnum):
    LIVEKIT_PIPELINE = "livekit_pipeline"
    GEMINI_LIVE = "gemini_live"
    DEEPGRAM_CASCADE = "deepgram_cascade"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The name the assistant introduces itself with, and the LiveKit agent name
    # the web app dispatches (must match AGENT_NAME there).
    app_name: str = "Sarjy"
    agent_name: str = "sarjy"

    voice_provider: VoiceProvider = VoiceProvider.LIVEKIT_PIPELINE
    stt_model: str = "assemblyai/universal-3-6-pro"
    llm_model: str = "google/gemma-4-31b-it"
    tts_model: str = "fishaudio/s2.1-pro"
    tts_voice: str = "fa4c9eb3dccc4806b382b40d61c6b10a"
    language: str = "en"

    google_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-live"
    gemini_voice: str = "Puck"

    database_url: SecretStr | None = None

    weather_geocoding_url: HttpUrl = HttpUrl("https://geocoding-api.open-meteo.com/v1/search")
    weather_forecast_url: HttpUrl = HttpUrl("https://api.open-meteo.com/v1/forecast")

    weather_fallback_url: HttpUrl = HttpUrl(
        "https://api.met.no/weatherapi/locationforecast/2.0/compact"
    )
    weather_user_agent: str = "Sarjy/0.1 github.com/sarahdoi/ai-voice-assistant"

    weather_timeout_s: float = 3.0
    # Connecting may need to wake a sleeping serverless database (Neon), so it gets
    # longer than individual queries, which should still fail fast and honestly.
    db_connect_timeout_s: float = 10.0
    db_timeout_s: float = 2.0
    # Delete a guest's facts after this many days without a call (0 keeps them forever).
    # Matches the one-year guest cookie: after that, the browser is a new guest anyway.
    memory_retention_days: int = 365

    # Topic gate before the main LLM: "classifier" (rules + LLM label), "rules"
    # (patterns only, no added latency) or "off". The classifier fails open after
    # guard_timeout_s. guard_model defaults to llm_model.
    guard_mode: Literal["classifier", "rules", "off"] = "classifier"
    guard_model: str = ""
    guard_timeout_s: float = 1.5
    # Speech-to-speech providers skip the topic gate (see voice/factory.py); they
    # only start when this is set, accepting prompt-only topic guardrails.
    allow_ungated_realtime: bool = False

    fault_weather: bool = False
    fault_db_write: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
