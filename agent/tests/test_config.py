"""Timeout settings: connecting may wake a sleeping database; queries fail fast."""

from sarjy.config import Settings


def test_connect_timeout_allows_cold_start_but_queries_stay_fast(monkeypatch):
    monkeypatch.delenv("DB_CONNECT_TIMEOUT_S", raising=False)
    monkeypatch.delenv("DB_TIMEOUT_S", raising=False)
    settings = Settings(_env_file=None)
    assert settings.db_connect_timeout_s >= 10
    assert settings.db_timeout_s <= 3


def test_app_and_agent_names_come_from_env(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Nova")
    monkeypatch.setenv("AGENT_NAME", "nova")
    settings = Settings(_env_file=None)
    assert (settings.app_name, settings.agent_name) == ("Nova", "nova")
