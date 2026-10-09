# Sarjy

A voice assistant with persistent Postgres memory, built with Python and LiveKit Agents.

## Run locally

Requires Python 3.11+ and uv.

```sh
cd agent
cp .env.example .env
```

Set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and `DATABASE_URL` in `.env`.

```sh
uv sync
uv run python db/migrate.py
uv run python -m sarjy.agent dev
```

Test in LiveKit Agent Console with agent name `sarjy`.
The default voice pipeline uses LiveKit Inference. Weather uses Open-Meteo
for current conditions and today/tomorrow forecasts.

## Tests

```sh
cd agent
uv run pytest
```

Live weather endpoint checks (optional):

```sh
RUN_WEATHER_INTEGRATION=1 uv run pytest tests/test_weather_integration.py
```

Weather retries Open-Meteo once on timeout/5xx, then falls back to MET Norway.
Fallback forecasts contain UTC temperature/wind periods; city lookup still uses
Open-Meteo. MET Norway data is attributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
