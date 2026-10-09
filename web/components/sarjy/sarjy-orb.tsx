'use client';

import { useEffect, useState } from 'react';
import { type TrackReference, type useAgent, useTrackVolume } from '@livekit/components-react';
import { cn } from '@/lib/shadcn/utils';

type AgentState = ReturnType<typeof useAgent>['state'];

/**
 * Sarjy's orb, as in the design: two quiet rings around a glowing core.
 * The core swells with Sarjy's voice while speaking and breathes while listening.
 * While the user waits (connecting, thinking, checking the weather), soft ripples
 * flow outward so the wait feels alive; if the wait runs long, Sarjy opens its
 * eyes (╹ ╹) and blinks at you; during a lookup the eyes glance side to side.
 * Motion is off for reduced-motion users.
 */

/** True once `active` has stayed true for `delayMs`, so quick replies don't flicker. */
function useLongWait(active: boolean, delayMs = 1_200) {
  const [long, setLong] = useState(false);
  useEffect(() => {
    if (!active) {
      setLong(false);
      return;
    }
    const timer = setTimeout(() => setLong(true), delayMs);
    return () => clearTimeout(timer);
  }, [active, delayMs]);
  return long;
}
export function SarjyOrb({
  state,
  audioTrack,
  searching = false,
  className,
}: {
  state: AgentState;
  audioTrack?: TrackReference;
  /** A lookup (e.g. weather) is running: the eyes glance around right away. */
  searching?: boolean;
  className?: string;
}) {
  const volume = useTrackVolume(audioTrack); // 0..1, Sarjy's voice
  const speaking = state === 'speaking';
  const scale = speaking ? 1 + Math.min(volume, 1) * 0.18 : 1;
  const waiting =
    state === 'thinking' ||
    state === 'connecting' ||
    state === 'initializing' ||
    state === 'pre-connect-buffering';
  const longWait = useLongWait(waiting);
  const showEyes = searching || longWait;

  return (
    <div
      role="img"
      aria-label={`Sarjy is ${speaking ? 'speaking' : waiting ? 'getting ready' : 'listening'}`}
      className={cn('relative aspect-square', className)}
    >
      <div className="border-primary/20 absolute inset-0 rounded-full border" />
      {waiting &&
        [0, 1, 2].map((i) => (
          <div
            key={i}
            aria-hidden="true"
            className="border-primary/50 absolute inset-[22%] rounded-full border motion-safe:animate-[sarjy-ripple_2.4s_ease-out_infinite]"
            style={{ animationDelay: `${i * 0.8}s` }}
          />
        ))}
      <div
        className={cn(
          'border-primary/35 absolute inset-[10%] rounded-full border',
          waiting && 'motion-safe:animate-pulse'
        )}
      />
      <div
        className={cn(
          'absolute inset-[22%] rounded-full transition-transform duration-100 ease-out',
          !speaking && 'motion-safe:animate-[sarjy-breathe_4s_ease-in-out_infinite]'
        )}
        style={{
          transform: `scale(${scale})`,
          background:
            'radial-gradient(circle at 40% 35%, #7FE6FB 0%, #1FD5F9 38%, #0E5E70 72%, transparent 100%)',
          boxShadow: `0 0 ${60 + volume * 80}px rgba(31, 213, 249, ${0.25 + volume * 0.35})`,
        }}
      >
        <div
          aria-hidden="true"
          className={cn(
            'absolute inset-0 flex items-center justify-center gap-[14%] transition-opacity duration-500',
            showEyes ? 'opacity-100' : 'opacity-0',
            searching && 'motion-safe:animate-[sarjy-glance_1.6s_ease-in-out_infinite]'
          )}
        >
          {[0, 1].map((eye) => (
            <span
              key={eye}
              className="aspect-[1/3] w-[6%] rounded-full bg-[#0B0B0C] motion-safe:animate-[sarjy-blink_3s_ease-in-out_infinite]"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
