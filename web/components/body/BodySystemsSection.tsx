'use client';

import { useState, useSyncExternalStore } from 'react';
import { ChevronDown } from '@/components/ui/icons';
import { cx } from '@/lib/format';
import s from '@/app/overview.module.css';

const WIDE = '(min-width: 1024px)';
const isWide = () => window.matchMedia(WIDE).matches;
function subscribeWide(cb: () => void) {
  const mq = window.matchMedia(WIDE);
  mq.addEventListener('change', cb);
  return () => mq.removeEventListener('change', cb);
}
const noop = () => () => {};

export function BodySystemsSection({
  title,
  note,
  statusClass,
  children,
}: {
  title: string;
  note: string;
  statusClass?: string;
  children: React.ReactNode;
}) {
  // Desktop (>= 1024px) opens by default; portrait tablet / mobile (< 1024px) starts collapsed. The width is read
  // through useSyncExternalStore so the server render and the first client render agree (no hydration mismatch);
  // once the user toggles, their choice wins.
  const wide = useSyncExternalStore(subscribeWide, isWide, () => true);
  const [choice, setChoice] = useState<boolean | null>(null);
  const open = choice ?? wide;
  // The content (the 3D body in it is heavy: WebGL, model, shaders) mounts the first time the section is open after
  // hydration and stays mounted after. The hydration render matches the server's open section; where the section
  // then starts collapsed, the content unmounts again before it loads anything.
  const hydrated = useSyncExternalStore(noop, () => true, () => false);
  const [kept, setKept] = useState(false);
  if (hydrated && open && !kept) setKept(true);
  const show = open || kept;

  return (
    <details
      id="body-systems"
      className={cx(s.block, s.collapsibleBlock)}
      open={open}
      onToggle={(e) => {
        if (e.currentTarget.open !== open) setChoice(e.currentTarget.open);
      }}
    >
      <summary className={s.collapsibleSummary}>
        <div className={s.blockHead}>
          <h2 className={s.h2}>{title}</h2>
          <span className={cx(s.blockNote, statusClass)}>{note}</span>
        </div>
        <ChevronDown
          size={18}
          className={s.collapseChevron}
          style={{
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.15s ease',
          }}
        />
      </summary>
      <div className={s.collapsibleContent}>{show ? children : null}</div>
    </details>
  );
}
