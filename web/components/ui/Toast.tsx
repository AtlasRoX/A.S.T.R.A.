'use client';

import { AnimatePresence, motion } from 'motion/react';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { installSound, play, type SoundName } from '@/lib/sound';
import { Award, CircleCheck, Info, Sparkles, TriangleAlert, X } from './icons';

type Tone = 'success' | 'info' | 'warning' | 'reward';
interface ToastItem {
  id: number;
  title: string;
  body?: string;
  tone: Tone;
  /** Stay until the user dismisses it. Warnings are persistent by default; confirmations are not. */
  persistent?: boolean;
  /** The sound for this toast; by default from its tone (info is silent). false: none. */
  sound?: SoundName | false;
}

const TONE_SOUND: Record<Tone, SoundName | null> = { success: 'success', warning: 'warning', reward: 'reward', info: null };

/** Warnings carry something the crew must know (an alert sent, a failure), so they do not time out. */
const isPersistent = (t: Omit<ToastItem, 'id'>) => t.persistent ?? t.tone === 'warning';
const VISIBLE = 4;

const ToastCtx = createContext<(t: Omit<ToastItem, 'id'>) => void>(() => {});

export const useToast = () => useContext(ToastCtx);

const ICON = { success: CircleCheck, info: Info, warning: TriangleAlert, reward: Award } as const;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);
  // Sound starts here: the provider wraps every page.
  useEffect(installSound, []);
  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const push = useCallback(
    (t: Omit<ToastItem, 'id'>) => {
      seq.current += 1;
      const id = seq.current;
      const sound = t.sound === undefined ? TONE_SOUND[t.tone] : t.sound;
      if (sound) play(sound);
      setItems((xs) => {
        const next = [...xs, { ...t, id }];
        // Over the limit: drop the oldest confirmation first, so a warning is never pushed off by a "saved".
        while (next.length > VISIBLE) {
          const i = next.findIndex((x) => !isPersistent(x));
          next.splice(i === -1 ? 0 : i, 1);
        }
        return next;
      });
      if (!isPersistent(t)) setTimeout(() => dismiss(id), t.tone === 'reward' ? 6500 : 5500);
    },
    [dismiss],
  );
  const value = useMemo(() => push, [push]);
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="toast-region" aria-live="polite" aria-atomic="false">
        <AnimatePresence initial={false}>
          {items.map((t) => {
            const I = ICON[t.tone];
            return (
              <motion.div
                key={t.id}
                layout
                initial={{ opacity: 0, y: 16, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 8, scale: 0.96 }}
                transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                className={`toast toast-${t.tone}`}
                role={t.tone === 'warning' ? 'alert' : 'status'}
              >
                <span className="toast-icon">{t.tone === 'reward' ? <Sparkles size={18} /> : <I size={18} />}</span>
                <div className="toast-text">
                  <b>{t.title}</b>
                  {t.body ? <span>{t.body}</span> : null}
                </div>
                <button className="toast-x" onClick={() => dismiss(t.id)} aria-label={`Dismiss: ${t.title}`}>
                  <X size={15} />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}
