'use client';

import { MotionConfig } from 'motion/react';

/**
 * Honour the operating-system "reduce motion" setting for every motion/react animation (tab underline,
 * toasts, wizard steps, emergency fades). CSS animations already respect it through globals.css.
 */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
