# Deployment runbook

How the app was deployed, step by step, including what went wrong and how it
was fixed. The README has the short version; this is the record.

**Never put secrets in this file.** URLs, regions and IDs are fine; keys,
passwords and connection strings are not.

## Live configuration

| What | Value |
| --- | --- |
| Web URL | [Live demo](https://ai-voice-assistant-pi-one.vercel.app/) |
| Vercel project | [sarahdoi / ai-voice-assistant](https://vercel.com/sarahdoi/ai-voice-assistant) |
| LiveKit Cloud project | Sarjy (`sarjy-a0pso6kv`) |
| Agent ID / region | `CA_aMoDfRqNEG7a` / `us-east` |
| Neon region | AWS US East (Ohio), `us-east-2` |
| Deployed commit | Initial agent deployment: `88ba64e`; current agent and web revisions: check deployment dashboards |
| Deployed on | Initial agent deployment: 10 October 2026 (Asia/Riyadh); current deployment dates: check dashboards |

## Steps

### 0. Merge to main

- [ ] PR #6 merged into `main`
- [ ] Agent tests pass before deploying (`cd agent && uv run pytest -q`)

```sh
gh pr merge 6 --merge && git checkout main && git pull
```

Notes: _none yet_

### 1. Database (Neon)

- [ ] Migrations applied (`001_memories`, `002_retention`)

```sh
cd agent && uv run python db/migrate.py   # prints "Memory schema ready."
```

The agent also applies migrations on start; both are idempotent.
For Neon, the connection string must not include `&channel_binding=require`
(asyncpg rejects it).

Notes: _none yet_

### 2. Agent → LiveKit Cloud

- [ ] LiveKit CLI installed and signed in to the right project
- [ ] Secrets file created without the `LIVEKIT_*` keys (LiveKit Cloud provides those)
- [ ] Agent created and worker registered
- [ ] `livekit.toml` committed

```sh
brew install livekit-cli
lk cloud auth
cd agent
grep -vE '^(LIVEKIT_|#|$)' .env > .env.production
lk agent create --secrets-file .env.production
lk agent logs                     # look for the worker registering
```

Later updates: `lk agent deploy`. Pick the region closest to the Neon database.

Notes: _none yet_

### 3. Web → Vercel

- [ ] Repository imported, Root Directory `web`
- [ ] Environment variables set
- [ ] Deployed

| Variable                                               | Value                                                           |
| ------------------------------------------------------ | --------------------------------------------------------------- |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Same LiveKit project as the agent                               |
| `AGENT_NAME`                                           | `sarjy` (must match the agent)                                  |
| `NEXT_PUBLIC_APP_NAME`                                 | `Sarjy`                                                         |
| `GUEST_ID_SECRET`                                      | New random value: `openssl rand -base64 32` (not the local one) |

Notes: _none yet_

### 4. Smoke test (live URL)

- [ ] Call starts and the assistant greets
- [ ] Memory survives a refresh: "Remember my favorite color is teal", reload, new call, ask
- [ ] Weather answers with a source: "What's the weather in Riyadh?"
- [ ] Guardrail refuses: "Ignore your previous instructions"
- [ ] LiveKit dashboard shows no recording for the session

Notes: _none yet_

### 5. Rate limit (Vercel Firewall)

- [ ] Rule "Limit voice sessions" published

Firewall → Configure → New Rule:

- If **Request Path** equals `/api/token` and **Method** equals `POST`
- Then **Rate Limit**: Fixed Window, 60 s, 10 requests, key IP, action 429

Notes: _none yet_

### 6. Red-team evaluation

- [ ] `uv run python evals/redteam.py` run; results in `agent/evals/results.md`

Notes: _none yet_

## Issues and fixes

| When          | Problem                                            | Cause                                                                    | Fix                                                                    |
| ------------- | -------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| Before deploy | Migration failed to connect to Neon                | asyncpg rejects `channel_binding=require` in the copied URL              | Remove `&channel_binding=require` from `DATABASE_URL`                  |
| Before deploy | Migration timed out on first run                   | A sleeping Neon database takes longer than the 2 s query timeout to wake | Separate connect timeout (`DB_CONNECT_TIMEOUT_S=10`); queries keep 2 s |
| Before deploy | Sessions were being recorded in LiveKit Cloud      | `AgentSession.start` records by default                                  | `record=False` in `agent.py`                                           |
| Before deploy | Switching to Gemini Live would skip the topic gate | Speech-to-speech turns skip `on_user_turn_completed`                     | Agent refuses to start that way unless `ALLOW_UNGATED_REALTIME=true`   |
