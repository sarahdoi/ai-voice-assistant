'use client';

import type { useAgent } from '@livekit/components-react';
import type { ToolName } from '@/lib/sarjy-events';
import { cn } from '@/lib/shadcn/utils';

type AgentState = ReturnType<typeof useAgent>['state'];

// Memory works silently: only the weather lookup gets its own label.
const TOOL_LABELS: Partial<Record<ToolName, string>> = {
  get_weather: 'Checking the weather…',
};

function describe(state: AgentState, activeTool: ToolName | null) {
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
      return { label: 'Connecting…', tone: 'off' as const };
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
  const { label, tone } = describe(state, activeTool);
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
