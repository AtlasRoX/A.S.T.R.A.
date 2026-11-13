'use client';

import { useSyncExternalStore } from 'react';

export type Theme = 'dark' | 'light';
const EVENT = 'astra-theme';

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  return () => window.removeEventListener(EVENT, cb);
}
const getSnapshot = (): Theme => (document.documentElement.dataset.theme === 'light' ? 'light' : 'dark');
const getServerSnapshot = (): Theme => 'dark';

/** Current theme, kept in sync across every toggle on the page (SSR-safe). */
export function useTheme(): [Theme, (t: Theme) => void] {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const set = (t: Theme) => {
    document.documentElement.dataset.theme = t;
    try {
      localStorage.setItem('astra-theme', t);
    } catch {
      /* storage unavailable */
    }
    window.dispatchEvent(new Event(EVENT));
  };
  return [theme, set];
}
