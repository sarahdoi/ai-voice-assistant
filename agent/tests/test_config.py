"""Timeout settings: connecting may wake a sleeping database; queries fail fast."""

from sarjy.config import Settings


def test_connect_timeout_allows_cold_start_but_queries_stay_fast(monkeypatch):
    monkeypatch.delenv("DB_CONNECT_TIMEOUT_S", raising=False)
    monkeypatch.delenv("DB_TIMEOUT_S", raising=False)
    settings = Settings(_env_file=None)
    assert settings.db_connect_timeout_s >= 10
    assert settings.db_timeout_s <= 3
