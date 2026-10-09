import { cn } from '@/lib/shadcn/utils';

const CALM =
  'radial-gradient(40% 45% at 22% 18%, rgba(31,213,249,0.14), transparent 70%),' +
  'radial-gradient(35% 40% at 80% 85%, rgba(127,230,251,0.10), transparent 70%)';
const BUSY =
  'radial-gradient(45% 50% at 22% 18%, rgba(31,213,249,0.18), transparent 70%),' +
  'radial-gradient(40% 45% at 80% 85%, rgba(127,230,251,0.13), transparent 70%)';

/**
 * Ambient background: two soft cyan glows drifting slowly behind the page.
 * While Sarjy is busy (`active`), a brighter version fades in, so a wait feels
 * alive rather than stuck. Pure CSS; the drift stops for reduced-motion users.
 */
export function SarjyBackdrop({
  active = false,
  className,
}: {
  active?: boolean;
  className?: string;
}) {
  const layer =
    'absolute inset-0 bg-size-[200%_200%] motion-safe:animate-[sarjy-drift_24s_ease-in-out_infinite_alternate]';
  return (
    <div
      aria-hidden="true"
      className={cn('pointer-events-none absolute inset-0 -z-10 overflow-hidden', className)}
    >
      <div className={layer} style={{ backgroundImage: CALM }} />
      <div
        className={cn(
          layer,
          'transition-opacity duration-1000',
          active ? 'opacity-100' : 'opacity-0'
        )}
        style={{ backgroundImage: BUSY }}
      />
    </div>
  );
}
