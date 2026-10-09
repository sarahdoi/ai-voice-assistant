import type { Fact } from '@/lib/sarjy-events';

/**
 * A copy of the user's last known facts, so the memory panel opens instantly
 * instead of showing "Loading…". The server stays the source of truth: the
 * copy is replaced as soon as the agent sends the real list.
 *
 * The copy is tied to the guest identity it belongs to. If cookies are cleared
 * (a new guest), the old copy is never shown. Storage can be unavailable
 * (private windows, blocked site data), so every access is guarded.
 */
const KEY = 'sarjy.memory.v1';

type CachedMemory = { identity: string; facts: Fact[] };

export function readCachedFacts(identity: string): Fact[] | null {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const cached = JSON.parse(raw) as CachedMemory;
    if (cached.identity !== identity || !Array.isArray(cached.facts)) return null;
    return cached.facts.filter(
      (f): f is Fact => typeof f?.key === 'string' && typeof f?.value === 'string'
    );
  } catch {
    return null;
  }
}

export function writeCachedFacts(identity: string, facts: Fact[]) {
  try {
    const value: CachedMemory = {
      identity,
      facts: facts.map(({ key, value }) => ({ key, value })),
    };
    window.localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    // Storage unavailable: the panel just loads from the server as before.
  }
}
