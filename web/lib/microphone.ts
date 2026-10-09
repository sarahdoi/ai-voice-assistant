/**
 * Ask for the microphone before a call starts, so a blocked or missing mic gets
 * a clear message instead of a crash. The test stream is closed immediately.
 */
export type MicrophoneStatus = 'ok' | 'blocked' | 'missing' | 'unavailable';

export async function checkMicrophone(): Promise<MicrophoneStatus> {
  if (!navigator.mediaDevices?.getUserMedia) return 'unavailable';
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return 'ok';
  } catch (error) {
    return microphoneErrorStatus(error);
  }
}

export function microphoneErrorStatus(error: unknown): Exclude<MicrophoneStatus, 'ok'> {
  const name = error instanceof Error ? error.name : '';
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'blocked';
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'missing';
  return 'unavailable';
}

export const MICROPHONE_MESSAGES: Record<
  Exclude<MicrophoneStatus, 'ok'>,
  { title: string; description: string }
> = {
  blocked: {
    title: 'Microphone is blocked',
    description:
      'Allow Sarjy to use your microphone so it can hear you. Click the lock icon in the address bar, then try again.',
  },
  missing: {
    title: 'No microphone found',
    description: 'Connect a microphone or headset, then try again.',
  },
  unavailable: {
    title: 'Microphone isn’t available',
    description: 'Another app may be using it. Close it, then try again.',
  },
};
