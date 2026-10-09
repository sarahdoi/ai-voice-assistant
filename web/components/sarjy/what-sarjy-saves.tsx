import { cn } from '@/lib/shadcn/utils';

/**
 * Plain-language answer to "what does Sarjy keep about me?".
 * Each line matches what the code actually does, so keep them in sync:
 * memory rules live in agent/src/sarjy/services/memory.py.
 */
export function WhatSarjySaves({ className }: { className?: string }) {
  return (
    <details className={cn('group text-sm', className)}>
      <summary className="text-muted-foreground hover:text-foreground cursor-pointer list-none underline-offset-4 hover:underline">
        What does Sarjy save?
      </summary>
      <ul className="text-muted-foreground mt-3 flex flex-col gap-2 text-left leading-5">
        <li>
          <span className="text-foreground font-medium">Saved:</span> only facts you ask it to
          remember, like your favorite color or home city. Ask Sarjy to forget any of them.
        </li>
        <li>
          <span className="text-foreground font-medium">Never saved:</span> passwords, card or bank
          numbers, and ID numbers. Sarjy refuses them.
        </li>
        <li>
          <span className="text-foreground font-medium">Not kept by Sarjy:</span> your voice or the
          full conversation.
        </li>
        <li>
          <span className="text-foreground font-medium">Where:</span> on Sarjy’s server, linked to
          this browser by an anonymous ID. No account. A different browser, a private window or
          clearing cookies starts fresh.
        </li>
      </ul>
    </details>
  );
}
