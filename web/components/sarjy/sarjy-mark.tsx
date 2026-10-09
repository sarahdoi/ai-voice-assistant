'use client';

import { useId } from 'react';
import { cn } from '@/lib/shadcn/utils';

/**
 * Sarjy's logo: a small version of the in-call orb (two rings around a glowing
 * core). With `animated`, the core breathes like the orb does while listening.
 * Keep in sync with app/icon.svg, the browser-tab icon.
 */
export function SarjyMark({
  className,
  animated = false,
}: {
  className?: string;
  animated?: boolean;
}) {
  const gradient = `sarjy-core-${useId().replaceAll(':', '')}`;
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className={cn('overflow-visible', className)}>
      <defs>
        <radialGradient id={gradient} cx="40%" cy="35%" r="70%">
          <stop offset="0%" stopColor="#7FE6FB" />
          <stop offset="45%" stopColor="#1FD5F9" />
          <stop offset="100%" stopColor="#0E5E70" />
        </radialGradient>
      </defs>
      <circle
        cx="32"
        cy="32"
        r="30"
        fill="none"
        stroke="#1FD5F9"
        strokeOpacity="0.3"
        strokeWidth="2"
      />
      <circle
        cx="32"
        cy="32"
        r="23"
        fill="none"
        stroke="#1FD5F9"
        strokeOpacity="0.55"
        strokeWidth="2"
      />
      <circle
        cx="32"
        cy="32"
        r="15"
        fill={`url(#${gradient})`}
        className={cn(
          'origin-center [transform-box:fill-box]',
          animated && 'motion-safe:animate-[sarjy-breathe_4s_ease-in-out_infinite]'
        )}
      />
    </svg>
  );
}
