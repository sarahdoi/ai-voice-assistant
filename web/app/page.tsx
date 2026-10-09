import { App } from '@/components/app/app';

// Sessions always go through our own /api/token route, which assigns the guest
// identity. There is deliberately no fallback to another token server: a missing
// configuration should fail loudly, not connect visitors to someone else's agent.
export default function Page() {
  return (
    <App
      tokenEndpoint="/api/token"
      agentName={process.env.AGENT_NAME ?? 'sarjy'}
      isVideoInputSupported={false}
    />
  );
}
