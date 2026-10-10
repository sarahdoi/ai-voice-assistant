# Deployment overview

[Open Sarjy](https://ai-voice-assistant-pi-one.vercel.app/)

## Hosting

| Component | Platform | Role |
| --- | --- | --- |
| Web app | Vercel | Interface and session tokens |
| Voice agent | LiveKit Cloud | Audio sessions, reasoning and tools |
| Memory | Neon Postgres | Saved facts across visits |

## Updates

Vercel deploys the web app from `main`. GitHub Actions runs backend tests and
frontend checks, then deploys agent changes to LiveKit Cloud. Database
migrations run when the agent starts.

## Operations

Agent logs are available through LiveKit Cloud and `lk agent logs`.
Vercel Firewall limits new session requests to 10 per minute per IP;
excess requests receive HTTP 429. This does not limit active call duration.
