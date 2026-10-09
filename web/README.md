# Web app

Next.js front end for the voice assistant. See the [root README](../README.md)
for the architecture and the agent.

```sh
cp .env.example .env.local   # LiveKit keys, AGENT_NAME, NEXT_PUBLIC_APP_NAME
pnpm install
pnpm dev                     # http://localhost:3000
```

- `app/api/token/route.ts` issues LiveKit tokens for the browser's guest identity
  and dispatches the agent. The identity is decided here, never by the client.
- `lib/app-config.ts` holds the display name (`NEXT_PUBLIC_APP_NAME`).

Before pushing, run `pnpm lint` and `pnpm build`.
