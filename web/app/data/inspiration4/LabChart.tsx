'use client';

import { STATUS_LABEL } from '@/lib/format';
import type { LabSeries } from '@/lib/types';
import { useWidth } from '@/lib/useWidth';
import { SUBJECT_COLOR, SUBJECT_LABEL, TIMEPOINT_LABEL } from './subjects';
import s from './i4.module.css';

/** One analyte: a small chart with a reference band and one line per crew member. */
export function LabChart({
  series,
  subjects,
  flight,
}: {
  series: LabSeries;
  subjects: string[];
  flight: { from: number | null; to: number | null };
}) {
  // Drawn at the card's own width, so the axis text stays 12px instead of scaling down with a viewBox.
  const [ref, width] = useWidth<HTMLDivElement>();
  const W = Math.max(width, 240);
  const H = 170;
  const L = 44;
  const R = 20;
  const T = 10;
  const B = 26;

  const days = [...new Set(series.points.map((p) => p.day))].toSorted((a, b) => a - b);
  const timepoint = new Map(series.points.map((p) => [p.day, p.timepoint]));
  const values = series.points.map((p) => p.value);
  const lo = Math.min(...values, series.ref_low ?? Infinity);
  const hi = Math.max(...values, series.ref_high ?? -Infinity);
  const pad = (hi - lo) * 0.15 || 1;
  const y0 = lo - pad;
  const y1 = hi + pad;

  // Ordinal x: one even slot per sampling day. The days run from 92 before launch to 194 after return, so a
  // day scale stacked the samples either side of the flight 3px apart.
  const slot = (W - L - R) / Math.max(1, days.length - 1);
  const x = (day: number) => L + days.indexOf(day) * slot;
  const y = (v: number) => T + (1 - (v - y0) / (y1 - y0 || 1)) * (H - T - B);

  // The flight happened between the last pre-launch (L-) sample and the first post-return (R+) one.
  const pre = days.findLastIndex((d) => timepoint.get(d)?.startsWith('L'));
  const post = days.findIndex((d) => timepoint.get(d)?.startsWith('R'));
  const showFlight = flight.from !== null && flight.to !== null && pre >= 0 && post === pre + 1;

  const line = (subject: string) =>
    series.points
      .filter((p) => p.subject === subject)
      .toSorted((a, b) => a.day - b.day)
      .map((p) => `${x(p.day).toFixed(1)},${y(p.value).toFixed(1)}`)
      .join(' L');

  const decimals = hi - lo < 8 ? 1 : 0;

  return (
    <article className={s.card}>
      <header className={s.cardHead}>
        <h3>{series.label}</h3>
        <span className="faint">{series.unit}</span>
      </header>
      <div ref={ref} className={s.plot}>
        {width > 0 ? (
          <svg className={s.svg} width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img"
            aria-label={`${series.label} for ${subjects.length} Inspiration4 crew members, reference range ${series.ref_low} to ${series.ref_high} ${series.unit}`}>
            {series.ref_low !== null && series.ref_high !== null ? (
              <rect
                className={s.refBand}
                x={L}
                width={W - L - R}
                y={y(series.ref_high)}
                height={Math.max(0, y(series.ref_low) - y(series.ref_high))}
                rx={3}
              />
            ) : null}
            {showFlight ? (
              <rect
                className={s.flightBand}
                x={x(days[pre]) + slot * 0.25}
                width={slot * 0.5}
                y={T}
                height={H - T - B}
              />
            ) : null}
            {series.ref_low !== null ? (
              <line className={s.refLine} x1={L} x2={W - R} y1={y(series.ref_low)} y2={y(series.ref_low)} />
            ) : null}
            {series.ref_high !== null ? (
              <line className={s.refLine} x1={L} x2={W - R} y1={y(series.ref_high)} y2={y(series.ref_high)} />
            ) : null}
            {subjects.map((sub) => (
              <path key={`l-${sub}`} className={s.line} d={`M${line(sub)}`} style={{ stroke: SUBJECT_COLOR[sub] }} />
            ))}
            {series.points.map((p) => (
              <g key={`${p.subject}-${p.day}`} className={`st-${p.status}`}>
                <title>
                  {SUBJECT_LABEL[p.subject] ?? p.subject} · {TIMEPOINT_LABEL[p.timepoint] ?? p.timepoint}: {p.value}{' '}
                  {series.unit} ({STATUS_LABEL[p.status]})
                </title>
                <circle className={s.hit} cx={x(p.day)} cy={y(p.value)} r={10} />
                <circle className={s.pt} cx={x(p.day)} cy={y(p.value)} r={4.5} style={{ fill: SUBJECT_COLOR[p.subject] }} />
                {p.status !== 'ok' ? <circle className={s.ring} cx={x(p.day)} cy={y(p.value)} r={6} /> : null}
              </g>
            ))}
            <text className={s.axis} x={L - 6} y={y(hi) + 4} textAnchor="end">
              {Number(hi.toFixed(decimals))}
            </text>
            <text className={s.axis} x={L - 6} y={y(lo) + 4} textAnchor="end">
              {Number(lo.toFixed(decimals))}
            </text>
            {days.map((d) => (
              <text key={d} className={s.axis} x={x(d)} y={H - 8} textAnchor="middle">
                {timepoint.get(d)}
              </text>
            ))}
          </svg>
        ) : null}
      </div>
      <footer className={s.cardFoot}>
        <span className="faint">
          Reference {series.ref_low ?? '–'}–{series.ref_high ?? '–'} {series.unit}
          {series.ranges_differ ? ' (widest; ranges differ by crew member)' : ''}
        </span>
      </footer>
    </article>
  );
}
