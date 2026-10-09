/**
 * The UI event contract shared with the agent (agent/src/sarjy/events.py).
 *
 * The agent reports what really happened; the browser only renders it and never
 * writes memory itself. Anything that does not match this contract is ignored.
 */

export const EVENTS_TOPIC = 'sarjy.events';
export const MEMORY_RPC_METHOD = 'sarjy.memory_snapshot';
const EVENTS_VERSION = 1;

export type ToolName = 'remember' | 'recall' | 'correct' | 'forget' | 'get_weather';

export type ToolStartedEvent = { type: 'tool_started'; id: string; name: ToolName; label: string };

export type ToolFinishedEvent = {
  type: 'tool_finished';
  id: string;
  name: ToolName;
  label: string;
  ok: boolean;
  error_code: string | null;
  ms: number;
  detail: string | null;
};

/** What the user asked for: save, change or forget a fact. */
export type MemoryAction = 'saved' | 'corrected' | 'forgotten';

export type MemoryChangedEvent =
  | { type: 'memory_changed'; op: 'saved' | 'corrected'; key: string; value: string }
  | { type: 'memory_changed'; op: 'forgotten' | 'refused'; key: string }
  // The write timed out and may or may not have gone through; the agent checks
  // storage and follows up with the real outcome.
  | { type: 'memory_changed'; op: 'uncertain'; key: string; action: MemoryAction }
  | { type: 'memory_changed'; op: 'failed'; key: string; action: MemoryAction; message: string };

const MEMORY_ACTIONS: readonly string[] = ['saved', 'corrected', 'forgotten'];
const asAction = (v: unknown): MemoryAction =>
  MEMORY_ACTIONS.includes(v as string) ? (v as MemoryAction) : 'saved';

export type SarjyEvent = ToolStartedEvent | ToolFinishedEvent | MemoryChangedEvent;

export type Fact = { key: string; value: string };

const TOOL_NAMES: readonly string[] = ['remember', 'recall', 'correct', 'forget', 'get_weather'];

const isString = (v: unknown): v is string => typeof v === 'string';
const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/** Parse one data message from the agent. Returns null for anything unexpected. */
export function parseSarjyEvent(raw: string): SarjyEvent | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(data) || data.v !== EVENTS_VERSION) return null;

  switch (data.type) {
    case 'tool_started':
      return isString(data.id) && isString(data.label) && TOOL_NAMES.includes(data.name as string)
        ? { type: 'tool_started', id: data.id, name: data.name as ToolName, label: data.label }
        : null;
    case 'tool_finished':
      return isString(data.id) &&
        isString(data.label) &&
        TOOL_NAMES.includes(data.name as string) &&
        typeof data.ok === 'boolean' &&
        typeof data.ms === 'number'
        ? {
            type: 'tool_finished',
            id: data.id,
            name: data.name as ToolName,
            label: data.label,
            ok: data.ok,
            error_code: isString(data.error_code) ? data.error_code : null,
            ms: data.ms,
            detail: isString(data.detail) ? data.detail : null,
          }
        : null;
    case 'memory_changed': {
      if (!isString(data.key)) return null;
      if ((data.op === 'saved' || data.op === 'corrected') && isString(data.value)) {
        return { type: 'memory_changed', op: data.op, key: data.key, value: data.value };
      }
      if (data.op === 'forgotten' || data.op === 'refused') {
        return { type: 'memory_changed', op: data.op, key: data.key };
      }
      if (data.op === 'uncertain') {
        return {
          type: 'memory_changed',
          op: 'uncertain',
          key: data.key,
          action: asAction(data.action),
        };
      }
      if (data.op === 'failed') {
        const message = isString(data.message) ? data.message : 'Memory is unavailable.';
        return {
          type: 'memory_changed',
          op: 'failed',
          key: data.key,
          action: asAction(data.action),
          message,
        };
      }
      return null;
    }
    default:
      return null;
  }
}

/** Parse the agent's reply to the memory snapshot RPC (a ToolResult). */
export function parseMemorySnapshot(raw: string): Fact[] | null {
  try {
    const result: unknown = JSON.parse(raw);
    if (!isRecord(result) || result.ok !== true || !isRecord(result.data)) return null;
    const memories = result.data.memories;
    if (!Array.isArray(memories)) return null;
    return memories.filter((m): m is Fact => isRecord(m) && isString(m.key) && isString(m.value));
  } catch {
    return null;
  }
}

/** "favorite_color" → "favorite color" for display. */
export const humanizeKey = (key: string) => key.replaceAll('_', ' ');
