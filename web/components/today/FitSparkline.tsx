'use client';

import { useLayoutEffect, useRef, useState } from 'react';
import { Sparkline } from '@/components/charts/Sparkline';
import type { Status } from '@/lib/types';

/**
 * A sparkline as wide as its box: the box is measured on the client (and again when it resizes); until then, and
 * on the server, it draws at the given width.
 */
export function FitSparkline({
  className,
  width,
  ...line
}: {
  className?: string;
  values: number[];
  band?: [number, number] | null;
  status: Status;
  width: number;
  height?: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState<number | null>(null);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.floor(entry.contentRect.width);
      if (w > 0) setFit(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={box} className={className}>
      <Sparkline {...line} width={fit ?? width} />
    </div>
  );
}
