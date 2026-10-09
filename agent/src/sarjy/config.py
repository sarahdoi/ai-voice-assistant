"""Typed settings, loaded once from environment variables (or .env)."""

from enum import StrEnum
from functools import lru_cache

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceProvider(StrEnum):
    LIVEKIT_PIPELINE = "livekit_pipeline"
    GEMINI_LIVE = "gemini_live"
    DEEPGRAM_CASCADE = "deepgram_cascade"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    weather_timeout_s: float = 3.0
    db_timeout_s: float = 2.0

    fault_weather: bool = False
    fault_db_write: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
