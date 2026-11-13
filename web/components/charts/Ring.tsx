'use client';

import { animate, useMotionValue, useTransform, motion } from 'motion/react';
import { useEffect, useId } from 'react';
import type { Status } from '@/lib/types';

/** Animated progress ring with a count-up number in the middle. */
export function Ring({
  value,
  max = 100,
  size = 140,
  stroke = 11,
  status,
  label,
  sub,
}: {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  status: Status | 'accent';
  label?: string;
  sub?: string;
}) {
  const id = useId();
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => Math.round(v).toString());
  const offset = useTransform(mv, (v) => c * (1 - Math.min(v, max) / max));
  useEffect(() => {
    const ctl = animate(mv, value, { duration: 1.1, ease: [0.16, 1, 0.3, 1] });
    return () => ctl.stop();
  }, [mv, value]);
  const color = status === 'accent' ? 'var(--accent)' : `var(--${status})`;
  return (
    <div style={{ position: 'relative', width: size, height: size, flex: 'none' }} role="img"
      aria-label={`${label ?? ''} ${value} of ${max}`}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={color} />
            <stop offset="1" stopColor={status === 'ok' || status === 'accent' ? 'var(--accent-2)' : color}
              stopOpacity={status === 'ok' || status === 'accent' ? 1 : 0.7} />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <motion.circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={`url(#${id})`} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c} style={{ strokeDashoffset: offset }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeContent: 'center', textAlign: 'center' }}>
        <motion.span className="num" style={{ fontSize: size * 0.27, fontWeight: 600, lineHeight: 1 }}>
          {text}
        </motion.span>
        {sub ? <span className="overline" style={{ marginTop: 6, fontSize: Math.max(9, size * 0.07) }}>{sub}</span> : null}
      </div>
    </div>
  );
}
