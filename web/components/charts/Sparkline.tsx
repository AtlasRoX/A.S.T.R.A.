import type { Status } from '@/lib/types';

/** Tiny trend line with the normal band shaded behind it. */
export function Sparkline({
  values,
  band,
  status,
  width = 96,
  height = 30,
}: {
  values: number[];
  band?: [number, number] | null;
  status: Status;
  width?: number;
  height?: number;
}) {
  if (values.length < 2) {
    return <svg width={width} height={height} aria-hidden />;
  }
  const lo = Math.min(...values, band ? band[0] : Infinity);
  const hi = Math.max(...values, band ? band[1] : -Infinity);
  const pad = (hi - lo) * 0.12 || 1;
  const y0 = lo - pad;
  const y1 = hi + pad;
  const x = (i: number) => 2 + (i * (width - 4)) / (values.length - 1);
  const y = (v: number) => height - 2 - ((v - y0) / (y1 - y0)) * (height - 4);
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const last = values[values.length - 1];
  const bandTop = band ? Math.max(2, y(Math.min(band[1], y1))) : 0;
  const bandBottom = band ? Math.min(height - 2, y(Math.max(band[0], y0))) : 0;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden className={`st-${status}`}
      style={{ overflow: 'visible' }}>
      {band ? (
        <rect x={0} y={bandTop} width={width} height={Math.max(0, bandBottom - bandTop)} rx={4}
          fill="var(--ok)" opacity={0.08} />
      ) : null}
      <polyline points={pts} fill="none" stroke="var(--st)" strokeWidth={1.8} strokeLinejoin="round"
        strokeLinecap="round" />
      <circle cx={x(values.length - 1)} cy={y(last)} r={3} fill="var(--st)" />
    </svg>
  );
}
