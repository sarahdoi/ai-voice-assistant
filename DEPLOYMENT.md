# Deployment

Sarjy runs on three managed services: Vercel for the web app, LiveKit Cloud
for the voice agent, and Neon for persistent memory.

## Live configuration

| What | Value |
| --- | --- |
| Web URL | [Live demo](https://ai-voice-assistant-pi-one.vercel.app/) |
| Vercel project | [sarahdoi / ai-voice-assistant](https://vercel.com/sarahdoi/ai-voice-assistant) |
| LiveKit Cloud project | Sarjy (`sarjy-a0pso6kv`) |
| Agent ID / region | `CA_aMoDfRqNEG7a` / `us-east` |
| Neon region | AWS US East (Ohio), `us-east-2` |

## Deploy and update

- **Web:** Vercel builds `web/` with Node 24 and deploys changes from `main`.
- **Agent:** GitHub Actions checks the code and deploys agent changes from
  `main` to the existing LiveKit deployment. Manual updates use `lk agent deploy`.
- **Database:** migrations run when the agent starts. To apply them manually,
  run `uv run python db/migrate.py` from `agent/`.

For the first agent deployment, authenticate with `lk cloud auth`, then run
from `agent/`:

```sh
lk agent create --secrets-file .env --ignore-empty-secrets
```

Commit `agent/livekit.toml`; keep environment files and credentials private.

## Configuration

Vercel needs `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`,
`AGENT_NAME`, `NEXT_PUBLIC_APP_NAME` and `GUEST_ID_SECRET`.
The agent's runtime configuration and database credentials live in LiveKit Cloud.

GitHub Actions needs repository secrets `LIVEKIT_URL`, `LIVEKIT_API_KEY` and
`LIVEKIT_API_SECRET`. Require **Backend checks** and **Frontend checks** in
branch rules to block merges when checks fail.

## Monitoring and protection

From `agent/`, inspect cloud worker logs:

```sh
lk agent logs
```

Vercel Firewall limits `POST /api/token` to 10 requests per 60 seconds per IP,
returning 429 when exceeded. This limits new session requests, not active calls.
The rule is configured in Vercel and needs a live check.

After deployment, verify voice, memory across reconnects, weather with source
attribution, and a guardrail refusal from the public demo. Confirm session
recording is disabled in LiveKit.
