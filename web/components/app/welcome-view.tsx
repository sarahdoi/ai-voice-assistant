import { WarningIcon } from '@phosphor-icons/react';
import { SarjyBackdrop } from '@/components/sarjy/sarjy-backdrop';
import { SarjyMark } from '@/components/sarjy/sarjy-mark';
import { Button } from '@/components/ui/button';
import { APP_NAME } from '@/lib/app-config';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
  /** Shown instead of starting the call, e.g. when the microphone is blocked. */
  problem?: { title: string; description: string } | null;
  starting?: boolean;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  problem,
  starting = false,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref} className="isolate">
      <SarjyBackdrop className="fixed" />
      <section className="flex flex-col items-center justify-center px-4 text-center">
        <SarjyMark animated className="mb-6 size-20" />

        <h1 className="text-foreground text-2xl font-semibold tracking-tight">
          Hi, I’m {APP_NAME}
        </h1>
        <p className="text-muted-foreground max-w-prose pt-2 leading-6">
          Your personal voice assistant
        </p>

        {problem && (
          <div
            role="alert"
            className="mt-6 flex max-w-sm items-start gap-3 rounded-2xl border border-amber-400/30 bg-amber-400/5 p-4 text-left"
          >
            <WarningIcon
              weight="bold"
              aria-hidden="true"
              className="mt-0.5 size-5 shrink-0 text-amber-400"
            />
            <div className="flex flex-col gap-1">
              <p className="font-medium">{problem.title}</p>
              <p className="text-muted-foreground text-sm">{problem.description}</p>
            </div>
          </div>
        )}

        <Button
          size="lg"
          onClick={onStartCall}
          disabled={starting}
          className="mt-6 w-64 rounded-full font-mono text-xs font-bold tracking-wider uppercase"
        >
          {starting ? 'Starting…' : problem ? 'Try again' : startButtonText}
        </Button>
      </section>

      <p className="text-muted-foreground fixed bottom-14 left-0 w-full px-4 text-center text-xs">
        No sign-up needed{' '}
        <span aria-hidden="true" className="whitespace-nowrap">
          ༼ つ ╹ ╹ ༽つ
        </span>
      </p>
    </div>
  );
};
