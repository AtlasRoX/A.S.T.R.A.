'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { soundVolume } from '@/lib/sound';
import type { ProtocolStepCue } from '@/lib/types';
import { Volume2, VolumeX } from '../ui/icons';
import s from './emergency.module.css';

export function MetronomeCue({ cue }: { cue?: ProtocolStepCue | null }) {
  const [active, setActive] = useState(false);
  const [beat, setBeat] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    return false;
  });
  const audioCtxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
      const listener = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
      mq.addEventListener('change', listener);
      return () => mq.removeEventListener('change', listener);
    }
  }, []);

  const playClick = useCallback(() => {
    // Follows ASTRA's sound settings (off, volume); the visual beat still runs when silent.
    const vol = soundVolume();
    if (vol <= 0) return;
    try {
      if (!audioCtxRef.current) {
        const AudioCtx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        audioCtxRef.current = new AudioCtx();
      }
      const ctx = audioCtxRef.current;
      if (ctx.state === 'suspended') {
        ctx.resume();
      }
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.28 * vol, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.04);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.04);
    } catch {
      // AudioContext unavailable or restricted
    }
  }, []);

  useEffect(() => {
    if (!active || !cue?.rate_per_min) {
      return;
    }

    const intervalMs = (60 / cue.rate_per_min) * 1000;
    playClick();

    const t = window.setInterval(() => {
      playClick();
      if (!reducedMotion) {
        setBeat(true);
        setTimeout(() => setBeat(false), 80);
      }
    }, intervalMs);

    return () => {
      clearInterval(t);
    };
  }, [active, cue, playClick, reducedMotion]);

  useEffect(() => {
    return () => {
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
    };
  }, []);

  if (!cue || !cue.rate_per_min) return null;

  return (
    <div className={s.metronomeWrap}>
      <button
        type="button"
        className={active ? s.metronomeActive : s.metronomeBtn}
        onClick={() => setActive((v) => !v)}
        aria-pressed={active}
        aria-label={`${cue.rate_per_min} beats per minute metronome${cue.source ? ' from ' + cue.source : ''}. ${active ? 'Active, click to stop' : 'Click to start'}`}
      >
        {active ? <Volume2 size={16} /> : <VolumeX size={16} />}
        <span>
          {active ? `Metronome active (${cue.rate_per_min} bpm)` : `▶ ${cue.rate_per_min} bpm metronome`}
        </span>
        <span
          className={s.beatIndicator}
          style={{
            opacity: active ? (reducedMotion ? 1 : beat ? 1 : 0.25) : 0,
            transform: !reducedMotion && beat ? 'scale(1.3)' : 'scale(1)',
          }}
          aria-hidden="true"
        />
      </button>
      {cue.source ? (
        <span className={s.cueSource}>Source: {cue.source}</span>
      ) : null}
    </div>
  );
}
