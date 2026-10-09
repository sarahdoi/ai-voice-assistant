'use client';

import { useEffect, useState } from 'react';
import { Track } from 'livekit-client';
import { toast } from 'sonner';
import {
  useSessionContext,
  useSessionMessages,
  useTrackToggle,
  useVoiceAssistant,
} from '@livekit/components-react';
import {
  BrainIcon,
  ClosedCaptioningIcon,
  MicrophoneIcon,
  MicrophoneSlashIcon,
} from '@phosphor-icons/react';
import { MemoryNotice } from '@/components/sarjy/memory-notice';
import { MemoryList, PanelCard } from '@/components/sarjy/memory-panel';
import { SarjyBackdrop } from '@/components/sarjy/sarjy-backdrop';
import { SarjyMark } from '@/components/sarjy/sarjy-mark';
import { SarjyOrb } from '@/components/sarjy/sarjy-orb';
import { StatusPill } from '@/components/sarjy/status-pill';
import { useSarjyEvents } from '@/hooks/useSarjyEvents';
import { APP_NAME } from '@/lib/app-config';
import { MICROPHONE_MESSAGES, microphoneErrorStatus } from '@/lib/microphone';
import { cn } from '@/lib/shadcn/utils';

function useElapsed() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}

/** The last exchange, labelled with who spoke, with the assistant's line larger. */
function Captions() {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const lastUser = messages.findLast((m) => m.from?.isLocal);
  const lastSarjy = messages.findLast((m) => !m.from?.isLocal);

  return (
    <section
      aria-label="Live captions"
      aria-live="polite"
      className="flex min-h-28 w-full max-w-2xl flex-col items-center gap-3 text-center"
    >
      {!lastUser && !lastSarjy ? (
        <p className="text-muted-foreground">
          Try “My favorite color is teal” or “Do I need an umbrella tomorrow?”
        </p>
      ) : (
        <>
          {lastUser && (
            <div className="flex flex-col gap-1">
              <span className="text-muted-foreground font-mono text-xs tracking-wider">YOU</span>
              <p className="text-foreground/80 text-base">{lastUser.message}</p>
            </div>
          )}
          {lastSarjy && (
            <div className="flex flex-col gap-1">
              <span className="text-primary font-mono text-xs tracking-wider uppercase">
                {APP_NAME}
              </span>
              <p className="text-xl leading-relaxed text-balance md:text-2xl">
                {lastSarjy.message}
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}

/**
 * The in-call screen: orb, status, captions and three controls. Memory works in
 * the background: a quiet hint confirms changes, and the Memory button shows
 * what Sarjy knows.
 */
export function SarjySessionView({ ref, className, ...props }: React.ComponentProps<'div'>) {
  const session = useSessionContext();
  const { state: agentState, audioTrack } = useVoiceAssistant();
  const sarjy = useSarjyEvents();
  const mic = useTrackToggle({
    source: Track.Source.Microphone,
    // e.g. permission revoked mid-call: explain instead of failing silently.
    onDeviceError: (error) => {
      const message = MICROPHONE_MESSAGES[microphoneErrorStatus(error)];
      toast.warning(message.title, { description: message.description });
    },
  });
  const elapsed = useElapsed();
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [captionsOn, setCaptionsOn] = useState(true);
  // Sarjy is working on something: the backdrop brightens so the wait feels alive.
  const busy =
    sarjy.activeTool !== null ||
    ['thinking', 'connecting', 'initializing', 'pre-connect-buffering'].includes(agentState);

  return (
    <div
      ref={ref}
      className={cn('bg-background fixed inset-0 z-10 flex flex-col overflow-y-auto', className)}
      {...props}
    >
      <SarjyBackdrop active={busy} />
      <header className="flex items-center justify-between px-5 py-5 md:px-8">
        <div className="flex items-center gap-2.5">
          <SarjyMark className="size-6" />
          <span className="font-semibold tracking-tight">{APP_NAME}</span>
          <span className="border-border text-muted-foreground rounded-full border px-2.5 py-0.5 font-mono text-xs">
            voice assistant
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-muted-foreground font-mono text-xs tabular-nums">{elapsed}</span>
          <button
            type="button"
            onClick={() => setMemoryOpen((open) => !open)}
            aria-expanded={memoryOpen}
            aria-controls="sarjy-memory"
            className={cn(
              'border-border flex min-h-9 items-center gap-2 rounded-full border px-3.5 text-sm transition-colors [&_svg]:size-4',
              memoryOpen ? 'bg-muted' : 'hover:bg-muted'
            )}
          >
            <BrainIcon weight="bold" aria-hidden="true" />
            Memory
          </button>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-[1440px] flex-1 flex-wrap justify-center gap-8 px-5 pb-8 md:px-8">
        <main className="flex min-w-0 flex-[999_1_560px] flex-col items-center justify-center gap-8">
          <SarjyOrb
            state={agentState}
            audioTrack={audioTrack}
            searching={sarjy.activeTool?.name === 'get_weather'}
            className="size-[200px] md:size-[300px]"
          />
          <StatusPill state={agentState} activeTool={sarjy.activeTool?.name ?? null} />
          {captionsOn ? <Captions /> : <div className="min-h-28" aria-hidden="true" />}

          <div className="flex flex-col items-center gap-3">
            <MemoryNotice notice={sarjy.notice} />
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => mic.toggle()}
                aria-pressed={!mic.enabled}
                aria-label={mic.enabled ? 'Mute microphone' : 'Unmute microphone'}
                className={cn(
                  'border-border flex size-14 items-center justify-center rounded-full border transition-colors [&_svg]:size-5',
                  mic.enabled ? 'bg-card hover:bg-muted' : 'bg-amber-400/15 text-amber-300'
                )}
              >
                {mic.enabled ? (
                  <MicrophoneIcon weight="bold" />
                ) : (
                  <MicrophoneSlashIcon weight="bold" />
                )}
              </button>
              <button
                type="button"
                onClick={() => setCaptionsOn((on) => !on)}
                aria-pressed={captionsOn}
                aria-label={captionsOn ? 'Hide captions' : 'Show captions'}
                className={cn(
                  'border-border flex size-14 items-center justify-center rounded-full border transition-colors [&_svg]:size-5',
                  captionsOn ? 'bg-muted' : 'bg-card hover:bg-muted'
                )}
              >
                <ClosedCaptioningIcon weight={captionsOn ? 'fill' : 'bold'} />
              </button>
              <button
                type="button"
                onClick={session.end}
                className="h-14 rounded-full bg-red-600 px-7 font-semibold text-white transition-colors hover:bg-red-700"
              >
                End call
              </button>
            </div>
          </div>
        </main>

        {memoryOpen && (
          <aside
            id="sarjy-memory"
            aria-label="Memory"
            className="flex max-w-[420px] min-w-0 flex-[1_1_340px] flex-col gap-5"
          >
            <PanelCard title={`What ${APP_NAME} knows about you`}>
              <MemoryList state={sarjy} />
            </PanelCard>
          </aside>
        )}
      </div>
    </div>
  );
}
