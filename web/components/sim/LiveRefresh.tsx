'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { getLiveSimulationStatus } from '@/app/actions';

/** Screens whose data must not change under the user's hands: a reading being entered, an emergency. */
const PAUSED = [/^\/measure\/[^/]+/, /^\/emergency/];

/**
 * Keeps every screen current while ASTRA Core's background telemetry runs: just after each new simulated
 * reading, the page's server data is refreshed in place (open panels, typed text and scroll stay as they are).
 * Renders nothing. Stops in hidden tabs and on screens where someone is entering data.
 */
export function LiveRefresh() {
  const router = useRouter();
  const path = usePathname();

  useEffect(() => {
    if (PAUSED.some((re) => re.test(path))) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const poll = async () => {
      if (stopped || document.visibilityState !== 'visible') return;
      const res = await getLiveSimulationStatus();
      if (stopped) return;
      // Running: refresh right after the next reading lands. Not running: look again in a minute.
      const running = res.ok && res.data.active;
      const wait = running ? (Math.max(0, res.data.countdown_s) + 1.5) * 1000 : 60_000;
      timer = setTimeout(() => {
        if (stopped) return;
        if (running && document.visibilityState === 'visible') {
          router.refresh();
          window.dispatchEvent(new Event('astra:data'));
        }
        void poll();
      }, wait);
    };
    // Back in a hidden tab: catch up once, then follow the readings again.
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      clearTimeout(timer);
      router.refresh();
      void poll();
    };

    void poll();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      stopped = true;
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [path, router]);

  return null;
}
