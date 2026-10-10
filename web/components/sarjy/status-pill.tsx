'use client';

import { useEffect, useState } from 'react';
import type { useAgent } from '@livekit/components-react';
import { APP_NAME } from '@/lib/app-config';
import type { ToolName } from '@/lib/sarjy-events';
import { cn } from '@/lib/shadcn/utils';

type AgentState = ReturnType<typeof useAgent>['state'];

// Memory works silently: only the weather lookup gets its own label.
const TOOL_LABELS: Partial<Record<ToolName, string>> = {
  get_weather: 'Checking the weather…',
};

// After this long without the agent, it is probably waking from sleep.
const WAKING_AFTER_MS = 5_000;
const CONNECTING_STATES: readonly AgentState[] = [
  'connecting',
  'initializing',
  'pre-connect-buffering',
];

/** True once the agent has been connecting for a while. */
function useWaking(state: AgentState) {
  const connecting = CONNECTING_STATES.includes(state);
  const [waking, setWaking] = useState(false);
  useEffect(() => {
    if (!connecting) {
      setWaking(false);
      return;
    }
    const timer = setTimeout(() => setWaking(true), WAKING_AFTER_MS);
    return () => clearTimeout(timer);
  }, [connecting]);
  return connecting && waking;
}

function describe(state: AgentState, activeTool: ToolName | null, waking: boolean) {
  const toolLabel = activeTool ? TOOL_LABELS[activeTool] : undefined;
  if (toolLabel) return { label: toolLabel, tone: 'tool' as const };
  if (activeTool) return { label: 'Thinking…', tone: 'thinking' as const };
  switch (state) {
    case 'listening':
    case 'idle':
      return { label: 'Listening', tone: 'listening' as const };
    case 'thinking':
      return { label: 'Thinking…', tone: 'thinking' as const };
    case 'speaking':
      return { label: 'Speaking', tone: 'speaking' as const };
    case 'failed':
    case 'disconnected':
      return { label: 'Disconnected', tone: 'off' as const };
    default:
      return waking
        ? { label: `Waking ${APP_NAME} up…`, tone: 'thinking' as const }
        : { label: 'Connecting…', tone: 'off' as const };
  }
}

const DOT: Record<string, string> = {
  listening: 'bg-primary',
  thinking: 'bg-violet-400',
  speaking: 'bg-primary animate-pulse',
  tool: 'bg-amber-400 animate-pulse',
  off: 'border border-muted-foreground',
};

/** What Sarjy is doing right now, including which tool is running. */
export function StatusPill({
  state,
  activeTool,
  className,
}: {
  state: AgentState;
  activeTool: ToolName | null;
  className?: string;
}) {
  const waking = useWaking(state);
  const { label, tone } = describe(state, activeTool, waking);
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        'bg-card/80 border-border flex items-center gap-2.5 rounded-full border px-4 py-2 text-sm backdrop-blur',
        className
      )}
    >
      <span aria-hidden="true" className={cn('size-2 rounded-full', DOT[tone])} />
      <span>{label}</span>
    </div>
  );
}
