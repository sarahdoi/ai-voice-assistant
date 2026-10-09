# Sarjy

Voice assistant take-home. Deep dive: guardrails and reliability.

## Scaffold architecture

Browser (Next.js) ↔ WebRTC ↔ LiveKit Cloud ↔ Python agent
→ hosted LiveKit Inference STT / LLM / TTS.
Application services stay independent of LiveKit. Gemini Live is an optional
configuration; switching providers requires behavior tests, not just an env change.

## Agent setup

Install Python 3.11+ and uv, then:

```sh
cd agent
cp .env.example .env
# Set LIVEKIT_URL, LIVEKIT_API_KEY and LIVEKIT_API_SECRET locally.
uv sync
uv run pytest
uv run python -m sarjy.agent dev
```

In the LiveKit Agent Console, dispatch agent name `sarjy`.
The pipeline uses LiveKit credentials and inference credits; no separate model
keys are required. Model availability and actual voice behavior still need a live test.
For Gemini, set VOICE_PROVIDER=gemini_live and GOOGLE_API_KEY.

## Frontend setup

```sh
cd web
cp .env.example .env.local
# Set the same LiveKit credentials and AGENT_NAME=sarjy.
pnpm install
pnpm dev
```

The frontend is the upstream LiveKit starter, including its development-only
token endpoint. It deliberately blocks normal production use. Before deploying,
implement signed anonymous identity, server-owned room/dispatch configuration,
origin checks and abuse limits. Never enable a preview bypass for production.

## Scaffold status

Implemented: package structure, provider factory, typed config, structured tool
results, tool adapters, starter frontend, fresh database schema, Dockerfile.
Memory and weather return NOT_IMPLEMENTED honestly. No persistent memory,
weather integration, production identity or deployed demo is claimed yet.
The initial SQL schema uses hard deletion; it is intended for a fresh database.

## Next commits

1. Verify live voice and dummy tool through LiveKit Console.
2. Signed browser identity and secure token endpoint.
3. Postgres memory service, validation, correction/deletion and isolation tests.
4. Open-Meteo weather with clarification, timeouts and grounded responses.
5. Reliability evaluation, memory panel and deployment.

Frontend source: https://github.com/livekit-examples/agent-starter-react
LiveKit setup: https://docs.livekit.io/agents/start/voice-ai/

## Voice setup validation

On 9 October 2026, the local `sarjy` worker registered with LiveKit Cloud and
Sarah confirmed a working spoken conversation through Agent Console. This
validates the default hosted pipeline voice loop, not persistence or deployment.
Gemini Live remains unverified. Configuration tests ensure a missing Gemini key
and the unimplemented stretch provider fail explicitly rather than falling back.
Keep application services provider-independent; add adapters only where a tested
provider requires them. A configuration switch alone does not prove portability.
