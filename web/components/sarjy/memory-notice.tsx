'use client';

import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { CheckCircleIcon, ProhibitIcon, TrashIcon, WarningIcon } from '@phosphor-icons/react';
import type { MemoryNotice as Notice } from '@/hooks/useSarjyEvents';

// Successes fade quickly; problems stay a little longer so they are not missed.
const VISIBLE_MS = { ok: 2_500, problem: 6_000 };

/** Deliberately quiet: confirms that memory changed, never shows what was stored. */
function content(notice: Notice) {
  switch (notice.op) {
    case 'saved':
      return {
        icon: <CheckCircleIcon weight="fill" className="text-emerald-400" />,
        text: notice.previous && notice.previous !== notice.value ? 'Updated' : 'Remembered',
      };
    case 'corrected':
      return {
        icon: <CheckCircleIcon weight="fill" className="text-emerald-400" />,
        text: 'Updated',
      };
    case 'forgotten':
      return {
        icon: <TrashIcon weight="bold" className="text-muted-foreground" />,
        text: 'Forgotten',
      };
    case 'refused':
      return {
        icon: <ProhibitIcon weight="bold" className="text-amber-400" />,
        text: 'Not saved',
      };
    case 'uncertain':
      return {
        icon: <WarningIcon weight="bold" className="text-amber-400" />,
        text: 'Couldn’t confirm the change',
      };
    case 'failed':
      return {
        icon: <WarningIcon weight="bold" className="text-amber-400" />,
        text: {
          saved: 'Couldn’t save',
          corrected: 'Couldn’t update',
          forgotten: 'Couldn’t forget',
        }[notice.action],
      };
  }
}

/**
 * A quiet hint the moment memory changes. It reflects the agent's reported
 * outcome, not what the model said aloud, and never shows the stored value.
 */
export function MemoryNotice({ notice }: { notice: Notice | null }) {
  const [visible, setVisible] = useState<Notice | null>(null);

  useEffect(() => {
    if (!notice) return;
    setVisible(notice);
    const problem = notice.op === 'refused' || notice.op === 'failed' || notice.op === 'uncertain';
    const timer = setTimeout(() => setVisible(null), problem ? VISIBLE_MS.problem : VISIBLE_MS.ok);
    return () => clearTimeout(timer);
  }, [notice]);

  const shown = visible ? content(visible) : null;

  return (
    <div aria-live="polite" className="pointer-events-none flex min-h-6 justify-center">
      <AnimatePresence>
        {visible && shown && (
          <motion.div
            key={visible.nonce}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="text-muted-foreground flex items-center gap-1.5 text-sm [&_svg]:size-4 [&_svg]:shrink-0"
          >
            {shown.icon}
            <span>{shown.text}</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
