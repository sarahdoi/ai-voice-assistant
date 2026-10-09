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
The default voice pipeline uses LiveKit Inference. Weather is not implemented yet.

## Tests

```sh
cd agent
uv run pytest
```
