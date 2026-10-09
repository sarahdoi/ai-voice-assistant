'use client';

import { useCallback, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useSessionContext } from '@livekit/components-react';
import { WelcomeView } from '@/components/app/welcome-view';
import { SarjySessionView } from '@/components/sarjy/sarjy-session-view';
import { APP_NAME } from '@/lib/app-config';
import { MICROPHONE_MESSAGES, checkMicrophone, microphoneErrorStatus } from '@/lib/microphone';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(SarjySessionView);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.5,
    ease: 'linear',
  },
};

type Problem = { title: string; description: string };

const START_FAILED: Problem = {
  title: 'Couldn’t start the call',
  description: `${APP_NAME} may be busy or offline. Please try again in a moment.`,
};

export function ViewController() {
  const { isConnected, start } = useSessionContext();
  const [problem, setProblem] = useState<Problem | null>(null);
  const [starting, setStarting] = useState(false);

  // Check the microphone first so a blocked mic gets a clear message, not a crash.
  const startCall = useCallback(async () => {
    setStarting(true);
    setProblem(null);
    try {
      const mic = await checkMicrophone();
      if (mic !== 'ok') {
        setProblem(MICROPHONE_MESSAGES[mic]);
        return;
      }
      await start();
    } catch (error) {
      const mic = microphoneErrorStatus(error);
      setProblem(mic === 'unavailable' ? START_FAILED : MICROPHONE_MESSAGES[mic]);
    } finally {
      setStarting(false);
    }
  }, [start]);

  return (
    <AnimatePresence mode="wait">
      {!isConnected && (
        <MotionWelcomeView
          key="welcome"
          {...VIEW_MOTION_PROPS}
          startButtonText={`Talk to ${APP_NAME}`}
          onStartCall={startCall}
          problem={problem}
          starting={starting}
        />
      )}
      {isConnected && <MotionSessionView key="session-view" {...VIEW_MOTION_PROPS} />}
    </AnimatePresence>
  );
}
