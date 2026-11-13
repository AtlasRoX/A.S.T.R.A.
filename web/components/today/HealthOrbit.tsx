import type { Status } from '@/lib/types';
import s from './today.module.css';

export interface OrbitSegment {
  id: string;
  label: string;
  status: Status;
  /** No reading yet: counted on the track, not in a coloured arc. */
  missing: boolean;
}

const ORDER: Status[] = ['act', 'watch', 'ok'];
const COLOR: Record<Status, string> = { ok: 'var(--ok)', watch: 'var(--watch)', act: 'var(--act)' };
const WORD: Record<Status, string> = { ok: 'nominal', watch: 'watch', act: 'act' };

/**
 * A donut of the crew member's health indicators: one arc per status (Act, Watch, Nominal, clockwise from the
 * top), each as long as its share, on a soft track that also stands for indicators with no reading yet. The
 * nominal count sits in the middle.
 */
export function HealthOrbit({ segments, size = 120 }: { segments: OrbitSegment[]; size?: number }) {
  const n = segments.length;
  const stroke = 11;
  const c = size / 2;
  const r = c - stroke / 2 - 2;
  const circumference = 2 * Math.PI * r;
  // Round caps reach past an arc's end by half the stroke; leave that much plus a small gap between arcs.
  const capLen = stroke / 2;
  const gapLen = 3;

  const groups = ORDER.map((status) => ({
    status,
    items: segments.filter((g) => !g.missing && g.status === status),
  })).filter((g) => g.items.length > 0);
  const nominal = segments.filter((g) => !g.missing && g.status === 'ok').length;
  const multiple = groups.length > 1;

  const arcs = groups.map((g, i) => {
    // Where this arc starts: the full length of every arc before it.
    const before = groups.slice(0, i).reduce((sum, p) => sum + (p.items.length / n) * circumference, 0);
    const full = (g.items.length / n) * circumference;
    const trim = multiple ? 2 * capLen + gapLen : 0;
    const len = Math.max(0.01, full - trim);
    const offset = before + (multiple ? capLen + gapLen / 2 : 0);
    return { ...g, len, offset };
  });

  const summary = groups.map((g) => `${g.items.length} ${WORD[g.status]}`).join(', ');

  return (
    <svg
      className={s.orbit}
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`${nominal} of ${n} health indicators nominal${summary ? `: ${summary}` : ''}`}
    >
      <circle cx={c} cy={c} r={r} fill="none" className={s.orbitTrack} strokeWidth={stroke} />
      {/* Arcs start at 12 o'clock and run clockwise. */}
      <g transform={`rotate(-90 ${c} ${c})`}>
        {arcs.map((a, i) => (
          <circle
            key={a.status}
            cx={c}
            cy={c}
            r={r}
            fill="none"
            stroke={COLOR[a.status]}
            strokeWidth={stroke}
            strokeLinecap={multiple ? 'round' : 'butt'}
            strokeDasharray={`${a.len} ${circumference}`}
            strokeDashoffset={-a.offset}
            className={s.orbitArc}
            style={{ animationDelay: `${i * 120}ms` }}
          >
            <title>{`${a.items.length} ${WORD[a.status]}: ${a.items.map((g) => g.label).join(', ')}`}</title>
          </circle>
        ))}
      </g>
      <text x={c} y={c + 2} textAnchor="middle" className={s.orbitNum}>
        {nominal}
        <tspan className={s.orbitOf}>/{n}</tspan>
      </text>
      <text x={c} y={c + 19} textAnchor="middle" className={s.orbitLabel}>
        nominal
      </text>
    </svg>
  );
}
