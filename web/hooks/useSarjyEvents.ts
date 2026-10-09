'use client';

import { useEffect, useReducer } from 'react';
import { type RemoteParticipant, RoomEvent } from 'livekit-client';
import { toast } from 'sonner';
import { useAgent, useSessionContext } from '@livekit/components-react';
import { APP_NAME } from '@/lib/app-config';
import { readCachedFacts, writeCachedFacts } from '@/lib/memory-cache';
import {
  EVENTS_TOPIC,
  type Fact,
  MEMORY_RPC_METHOD,
  type MemoryChangedEvent,
  type SarjyEvent,
  type ToolName,
  humanizeKey,
  parseMemorySnapshot,
  parseSarjyEvent,
} from '@/lib/sarjy-events';

export type FactRow = Fact & { previous?: string; updatedAt: number };

export type ActivityRow = {
  id: string;
  label: string;
  detail: string | null;
  /** null while the tool is still running */
  ok: boolean | null;
  errorCode: string | null;
  ms: number | null;
};

export type MemoryNotice = MemoryChangedEvent & { nonce: number; previous?: string };

export type SarjyState = {
  facts: FactRow[];
  /** Keys forgotten during this session, so an older snapshot can't bring them back. */
  forgotten: string[];
  activity: ActivityRow[];
  activeTool: { id: string; name: ToolName } | null;
  notice: MemoryNotice | null;
  memoryStatus: 'loading' | 'ready' | 'unavailable';
};

const INITIAL: SarjyState = {
  facts: [],
  forgotten: [],
  activity: [],
  activeTool: null,
  notice: null,
  memoryStatus: 'loading',
};
const MAX_ACTIVITY = 20;

type Action =
  | { kind: 'reset' }
  | { kind: 'cached'; facts: Fact[] }
  | { kind: 'snapshot'; facts: Fact[] }
  | { kind: 'snapshot_failed' }
  | { kind: 'event'; event: SarjyEvent; at: number };

function reducer(state: SarjyState, action: Action): SarjyState {
  switch (action.kind) {
    case 'reset':
      return INITIAL;
    case 'cached':
      // Show the last known facts right away; the agent's snapshot replaces them.
      return state.memoryStatus === 'loading'
        ? {
            ...state,
            memoryStatus: 'ready',
            facts: action.facts.map((f) => ({ ...f, updatedAt: 0 })),
          }
        : state;
    case 'snapshot': {
      // Changes that arrived live during the request are newer than the snapshot:
      // live saves win, and live deletions stay deleted.
      const live = state.facts.filter((f) => f.updatedAt > 0);
      const liveKeys = new Set([...live.map((f) => f.key), ...state.forgotten]);
      return {
        ...state,
        memoryStatus: 'ready',
        facts: [
          ...live,
          ...action.facts.filter((f) => !liveKeys.has(f.key)).map((f) => ({ ...f, updatedAt: 0 })),
        ],
      };
    }
    case 'snapshot_failed':
      return { ...state, memoryStatus: 'unavailable' };
    case 'event':
      return applyEvent(state, action.event, action.at);
  }
}

function applyEvent(state: SarjyState, event: SarjyEvent, at: number): SarjyState {
  switch (event.type) {
    case 'tool_started':
      return {
        ...state,
        activeTool: { id: event.id, name: event.name },
        activity: [
          { id: event.id, label: event.label, detail: null, ok: null, errorCode: null, ms: null },
          ...state.activity,
        ].slice(0, MAX_ACTIVITY),
      };
    case 'tool_finished':
      return {
        ...state,
        activeTool: state.activeTool?.id === event.id ? null : state.activeTool,
        activity: state.activity.map((row) =>
          row.id === event.id
            ? {
                ...row,
                ok: event.ok,
                errorCode: event.error_code,
                ms: event.ms,
                detail: event.detail,
              }
            : row
        ),
      };
    case 'memory_changed': {
      const existing = state.facts.find((f) => f.key === event.key);
      const notice: MemoryNotice = { ...event, nonce: at, previous: existing?.value };
      if (event.op === 'saved' || event.op === 'corrected') {
        const row: FactRow = {
          key: event.key,
          value: event.value,
          previous: existing && existing.value !== event.value ? existing.value : undefined,
          updatedAt: at,
        };
        return {
          ...state,
          notice,
          facts: [row, ...state.facts.filter((f) => f.key !== event.key)],
          forgotten: state.forgotten.filter((k) => k !== event.key),
        };
      }
      if (event.op === 'forgotten') {
        return {
          ...state,
          notice,
          facts: state.facts.filter((f) => f.key !== event.key),
          forgotten: [...state.forgotten.filter((k) => k !== event.key), event.key],
        };
      }
      return { ...state, notice };
    }
  }
}

/** Failures the user must hear about even if they missed what Sarjy said. */
function toastFor(event: SarjyEvent) {
  if (event.type === 'memory_changed' && event.op === 'uncertain') {
    toast.warning(`Couldn’t confirm the change to your ${humanizeKey(event.key)}`, {
      description: `Memory is slow right now. ${APP_NAME} is checking whether it went through.`,
    });
  }
  if (event.type === 'memory_changed' && event.op === 'failed') {
    const verb = { saved: 'save', corrected: 'update', forgotten: 'forget' }[event.action];
    toast.warning(`Couldn’t ${verb} your ${humanizeKey(event.key)}`, {
      description: event.message,
    });
  }
  if (
    event.type === 'tool_finished' &&
    event.name === 'get_weather' &&
    !event.ok &&
    (event.error_code === 'UPSTREAM_TIMEOUT' || event.error_code === 'UPSTREAM_ERROR')
  ) {
    toast.warning('Weather service didn’t respond', {
      description: `${APP_NAME} won’t guess the weather. Ask again in a moment.`,
    });
  }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Live view of what Sarjy did this session: saved facts, tool activity, and
 * the tool currently running. Data comes only from the agent.
 */
export function useSarjyEvents(): SarjyState {
  const { room, isConnected } = useSessionContext();
  const agent = useAgent();
  const agentParticipant: RemoteParticipant | null = agent.internal.agentParticipant;
  const agentIdentity = agentParticipant?.identity;
  const [state, dispatch] = useReducer(reducer, INITIAL);

  const identity = isConnected ? room?.localParticipant.identity : undefined;

  // New session or disconnect: start clean, then show this guest's last known facts.
  useEffect(() => {
    dispatch({ kind: 'reset' });
    const cached = identity ? readCachedFacts(identity) : null;
    if (cached) dispatch({ kind: 'cached', facts: cached });
  }, [room, identity]);

  // Keep the local copy in step with what the agent reports.
  useEffect(() => {
    if (identity && state.memoryStatus === 'ready') writeCachedFacts(identity, state.facts);
  }, [identity, state.memoryStatus, state.facts]);

  // Live events from the agent, accepted only from the agent participant.
  useEffect(() => {
    if (!room) return;
    const decoder = new TextDecoder();
    const onData = (
      payload: Uint8Array,
      participant?: RemoteParticipant,
      _kind?: unknown,
      topic?: string
    ) => {
      if (topic !== EVENTS_TOPIC || !participant?.isAgent) return;
      const event = parseSarjyEvent(decoder.decode(payload));
      if (!event) return;
      dispatch({ kind: 'event', event, at: Date.now() });
      toastFor(event);
    };
    room.on(RoomEvent.DataReceived, onData);
    return () => {
      room.off(RoomEvent.DataReceived, onData);
    };
  }, [room]);

  // Saved facts when the agent joins. Retries while the agent is still starting up.
  useEffect(() => {
    if (!room || !agentIdentity) return;
    let cancelled = false;
    (async () => {
      for (let attempt = 0; attempt < 6 && !cancelled; attempt++) {
        try {
          const reply = await room.localParticipant.performRpc({
            destinationIdentity: agentIdentity,
            method: MEMORY_RPC_METHOD,
            payload: '',
            responseTimeout: 15_000, // the database may be waking up
          });
          if (cancelled) return;
          const facts = parseMemorySnapshot(reply);
          dispatch(facts ? { kind: 'snapshot', facts } : { kind: 'snapshot_failed' });
          return;
        } catch {
          await sleep(1_000);
        }
      }
      if (!cancelled) dispatch({ kind: 'snapshot_failed' });
    })();
    return () => {
      cancelled = true;
    };
  }, [room, agentIdentity]);

  return state;
}
