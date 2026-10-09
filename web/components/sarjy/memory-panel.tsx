'use client';

import type { SarjyState } from '@/hooks/useSarjyEvents';
import { APP_NAME } from '@/lib/app-config';
import { humanizeKey } from '@/lib/sarjy-events';

/**
 * Turns a saved fact into a sentence about the user:
 *   name → "Your name is Sarah", city → "You live in Riyadh",
 *   favorite_food → "Your favorite food is burger", anything else → "Your <key> is <value>".
 */
function FactSentence({ factKey, value }: { factKey: string; value: string }) {
  const key = factKey.replace(/^(user|my)_/, '');
  const v = <strong className="text-foreground font-medium">{value}</strong>;
  if (key === 'name') return <>Your name is {v}</>;
  if (key === 'city' || key === 'home_city' || key === 'location') return <>You live in {v}</>;
  return (
    <>
      Your {humanizeKey(key)} is {v}
    </>
  );
}

const isName = (key: string) => /^(user_|my_)?name$/.test(key);

/** What the assistant knows about this user, straight from the agent's memory service. */
export function MemoryList({ state }: { state: SarjyState }) {
  return (
    <div className="flex flex-col gap-4">
      {state.memoryStatus === 'loading' && (
        <p className="text-muted-foreground text-sm">Loading…</p>
      )}
      {state.memoryStatus === 'unavailable' && state.facts.length === 0 && (
        <p className="text-sm">Memory is unavailable right now.</p>
      )}
      {state.memoryStatus === 'ready' && state.facts.length === 0 && (
        <p className="text-muted-foreground text-sm">
          Nothing yet. Tell {APP_NAME} something to remember.
        </p>
      )}
      {state.facts.length > 0 && (
        <ul className="flex flex-col gap-2.5">
          {[...state.facts]
            .sort((a, b) => Number(isName(b.key)) - Number(isName(a.key)))
            .map((fact) => (
              <li key={fact.key} className="text-muted-foreground leading-relaxed">
                <FactSentence factKey={fact.key} value={fact.value} />.
              </li>
            ))}
        </ul>
      )}
      <p className="text-muted-foreground text-xs">Ask {APP_NAME} to forget anything.</p>
    </div>
  );
}

/** A titled card, as in the desktop side panel. */
export function PanelCard({ title, children }: { title: string; children: React.ReactNode }) {
  const id = `panel-${title.toLowerCase().replaceAll(' ', '-')}`;
  return (
    <section
      aria-labelledby={id}
      className="bg-card border-border flex flex-col gap-3 rounded-2xl border p-5"
    >
      <h2 id={id} className="text-base font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}
