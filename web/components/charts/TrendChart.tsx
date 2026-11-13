'use client';

import { useId, useMemo, useState } from 'react';
import { STATUS_LABEL } from '@/lib/format';
import type { Band, SeriesPoint } from '@/lib/types';
import { useWidth } from '@/lib/useWidth';
import s from './chart.module.css';

export interface CompareSeries {
  label: string;
  unit: string;
  decimals: number;
  axis: [number, number];
  points: { day: number; value: number }[];
}

interface Props {
  points: SeriesPoint[];
  band: Band;
  axis: [number, number];
  baseline: number | null;
  unit: string;
  decimals: number;
  today: number;
  days: number;
  compare?: CompareSeries | null;
  label: string;
}

function niceTicks(a: number, b: number, n = 5): number[] {
  const span = b - a || 1;
  const raw = span / (n - 1);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((x) => x >= raw) ?? raw;
  const start = Math.ceil(a / step) * step;
  const out: number[] = [];
  for (let v = start; v <= b + 1e-9; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

export function TrendChart({ points, band, axis, baseline, unit, decimals, today, days, compare, label }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const gid = useId();
  const W = Math.max(width, 280);
  const H = W < 520 ? 230 : 300;
  const L = 46;
  const R = compare ? 46 : 16;
  const T = 16;
  const B = 30;
  const d0 = today - days + 1;
  const [y0, y1] = axis;
  const x = (day: number) => L + ((day - d0) / Math.max(1, days - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - (Math.min(Math.max(v, y0), y1) - y0) / (y1 - y0)) * (H - T - B);
  const yc = compare
    ? (v: number) =>
        T + (1 - (Math.min(Math.max(v, compare.axis[0]), compare.axis[1]) - compare.axis[0]) /
          (compare.axis[1] - compare.axis[0] || 1)) * (H - T - B)
    : null;
  const dual = points.some((p) => p.value2 !== null && p.value2 !== undefined);
  const ticks = useMemo(() => niceTicks(y0, y1), [y0, y1]);

  const zones = [
    { from: y0, to: band.watch[0], cls: s.zoneAct },
    { from: band.watch[0], to: band.ok[0], cls: s.zoneWatch },
    { from: band.ok[0], to: band.ok[1], cls: s.zoneOk },
    { from: band.ok[1], to: band.watch[1], cls: s.zoneWatch },
    { from: band.watch[1], to: y1, cls: s.zoneAct },
  ].filter((z) => Math.min(z.to, y1) > Math.max(z.from, y0));

  const line = (vals: (number | null)[]) =>
    points
      .map((p, i) => (vals[i] === null ? null : `${x(p.day).toFixed(1)},${y(vals[i] as number).toFixed(1)}`))
      .filter(Boolean)
      .join(' L');
  const main = line(points.map((p) => p.value));
  const second = dual ? line(points.map((p) => p.value2)) : '';
  const area = points.length
    ? `M${x(points[0].day)},${H - B} L${main} L${x(points[points.length - 1].day)},${H - B} Z`
    : '';
  const cmp = compare && yc
    ? compare.points
        .filter((p) => p.day >= d0)
        .map((p) => `${x(p.day).toFixed(1)},${yc(p.value).toFixed(1)}`)
        .join(' L')
    : '';
  const step = W < 520 ? (days > 14 ? 7 : 3) : days > 14 ? 3 : days > 7 ? 2 : 1;
  const xLabels: number[] = [];
  for (let d = today; d >= d0; d -= step) xLabels.push(d);

  const onMove = (clientX: number) => {
    const el = ref.current;
    if (!el || !points.length) return;
    const rect = el.getBoundingClientRect();
    const vx = ((clientX - rect.left) / rect.width) * W;
    let best = 0;
    let bd = Infinity;
    points.forEach((p, i) => {
      const dd = Math.abs(x(p.day) - vx);
      if (dd < bd) {
        bd = dd;
        best = i;
      }
    });
    setHover(best);
  };
  const hp = hover !== null ? points[hover] : null;
  const focusPoint = points[hover ?? points.length - 1];
  const valueText = focusPoint
    ? `Day ${focusPoint.day}: ${focusPoint.display} ${unit}, ${STATUS_LABEL[focusPoint.status]}`
    : 'No data';
  const hc = hp && compare ? compare.points.find((p) => p.day === hp.day) : null;

  // Baseline pill: sized to its text (mono, ~0.6em per character), above the line (below it near the top).
  let pill: { text: string; w: number; x: number; y: number } | null = null;
  if (baseline !== null) {
    const text = `baseline ${baseline.toFixed(decimals)}`;
    const w = Math.round(text.length * 7.3 + 16);
    const py = y(baseline) - 23 < 2 ? y(baseline) + 5 : y(baseline) - 23;
    const covers = (px: number) =>
      points.some((p) =>
        [p.value, p.value2].some(
          (v) =>
            v !== null && v !== undefined &&
            x(p.day) > px - 10 && x(p.day) < px + w + 10 && y(v) > py - 10 && y(v) < py + 28,
        ),
      );
    const right = W - R - w - 6;
    const left = L + 6;
    pill = { text, w, y: py, x: covers(right) && !covers(left) ? left : right };
  }

  return (
    <div
      ref={ref}
      className={s.wrap}
      tabIndex={0}
      role="slider"
      aria-label={`${label} over the last ${days} days. Use the arrow keys to inspect each day.`}
      aria-valuemin={0}
      aria-valuemax={Math.max(0, points.length - 1)}
      aria-valuenow={hover ?? Math.max(0, points.length - 1)}
      aria-valuetext={valueText}
      onPointerMove={(e) => onMove(e.clientX)}
      onPointerDown={(e) => onMove(e.clientX)}
      // A finger lift fires pointerleave: keep the tapped day's tooltip until focus moves away.
      onPointerLeave={(e) => e.pointerType !== 'touch' && setHover(null)}
      onBlur={() => setHover(null)}
      onKeyDown={(e) => {
        if (!points.length) return;
        if (e.key === 'ArrowLeft') setHover((h) => Math.max(0, (h ?? points.length) - 1));
        if (e.key === 'ArrowRight') setHover((h) => Math.min(points.length - 1, (h ?? -1) + 1));
        if (e.key === 'Home') setHover(0);
        if (e.key === 'End') setHover(points.length - 1);
        if (e.key === 'Escape') setHover(null);
      }}
    >
      {width > 0 ? (
        <svg className={s.svg} width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--accent)" stopOpacity="0.22" />
              <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {zones.map((z) => (
            <rect key={`${z.cls}-${z.from}`} className={z.cls} x={L} width={W - L - R} y={y(Math.min(z.to, y1))}
              height={Math.max(0, y(Math.max(z.from, y0)) - y(Math.min(z.to, y1)))} />
          ))}
          {/* Threshold lines: the edge of the normal range (amber) and of the watch range (red), labelled, so
              the zones can be told apart without the legend. */}
          {[
            { id: 'ok-low', v: band.ok[0], cls: s.edgeWatch },
            { id: 'ok-high', v: band.ok[1], cls: s.edgeWatch },
            { id: 'act-low', v: band.watch[0], cls: s.edgeAct },
            { id: 'act-high', v: band.watch[1], cls: s.edgeAct },
          ]
            // One line per position: a normal range of a single value (0 to 0) has both edges in the same place.
            .filter((e, i, all) => e.v > y0 && e.v < y1 && all.findIndex((o) => o.v === e.v) === i)
            .map((e) => (
              <line key={e.id} className={e.cls} x1={L} x2={W - R} y1={y(e.v)} y2={y(e.v)} />
            ))}
          {band.ok2 ? (
            <rect className={s.band2} x={L} width={W - L - R} y={y(band.ok2[1])}
              height={Math.max(0, y(band.ok2[0]) - y(band.ok2[1]))} rx={4} />
          ) : null}
          {ticks.map((t) => (
            <g key={t}>
              <line className={s.grid} x1={L} x2={W - R} y1={y(t)} y2={y(t)} />
              <text className={s.axis} x={L - 8} y={y(t) + 4} textAnchor="end">
                {Number(t.toFixed(decimals > 0 && y1 - y0 < 8 ? 1 : 0))}
              </text>
            </g>
          ))}
          {compare && yc
            ? niceTicks(compare.axis[0], compare.axis[1], 4).map((t) => (
                <text key={`c${t}`} className={s.axisR} x={W - R + 8} y={yc(t) + 4}>
                  {Number(t.toFixed(compare.decimals))}
                </text>
              ))
            : null}
          {xLabels.map((d) => (
            <text key={d} className={s.axis} x={x(d)} y={H - 9} textAnchor="middle">
              {d === today ? 'Today' : `D${d}`}
            </text>
          ))}
          {baseline !== null ? (
            <line className={s.baseline} x1={L} x2={W - R} y1={y(baseline)} y2={y(baseline)} />
          ) : null}
          {area && !dual ? <path className={s.area} d={area} fill={`url(#${gid})`} /> : null}
          {main ? <path key={`m-${points.length}-${days}-${label}`} className={s.line} pathLength={1} d={`M${main}`} /> : null}
          {second ? (
            <path key={`s-${points.length}-${days}`} className={`${s.line} ${s.line2}`} pathLength={1} d={`M${second}`} />
          ) : null}
          {cmp ? <path className={s.compare} d={`M${cmp}`} /> : null}
          {hp ? <line className={s.cross} x1={x(hp.day)} x2={x(hp.day)} y1={T} y2={H - B} /> : null}
          {points.map((p, i) => {
            const isToday = i === points.length - 1;
            const r = hover === i ? 6 : isToday ? 5.5 : 3.8;
            return (
              <g key={p.day} className={`st-${p.status}`}>
                {isToday ? <circle className={s.today} cx={x(p.day)} cy={y(p.value)} r={10} /> : null}
                <circle className={s.pt} cx={x(p.day)} cy={y(p.value)} r={r} />
                {dual && p.value2 !== null ? (
                  <circle className={s.pt} cx={x(p.day)} cy={y(p.value2)} r={hover === i ? 5 : 3} />
                ) : null}
              </g>
            );
          })}
          {/* Baseline label on top of the points, at the right end unless points sit there and not on the left. */}
          {pill ? (
            <g>
              <rect className={s.basePill} x={pill.x} y={pill.y} width={pill.w} height={18} rx={9} />
              <text className={s.baseText} x={pill.x + 8} y={pill.y + 13}>
                {pill.text}
              </text>
            </g>
          ) : null}
        </svg>
      ) : (
        <div className={s.placeholder} />
      )}
      {hp && width > 0 ? (
        <div
          className={s.tip}
          style={{
            left: Math.min(Math.max(x(hp.day), 90), W - 90),
            top: Math.max(y(hp.value), 70),
          }}
        >
          <div className={s.tipRow}>
            <span className="faint">{hp.day === today ? 'Today' : `Day ${hp.day}`} · {hp.time}</span>
            <span className={`chip chip-dot chip-${hp.status}`}>{STATUS_LABEL[hp.status]}</span>
          </div>
          <div style={{ marginTop: 6 }}>
            <b>{hp.display}</b> <span className="faint">{unit}</span>
          </div>
          {hp.items && hp.items.length ? (
            <div className="faint" style={{ fontSize: 12, marginTop: 2 }}>{hp.items.join(', ').replaceAll('_', ' ')}</div>
          ) : null}
          {hc && compare ? (
            <div style={{ marginTop: 4, color: 'var(--accent)', fontSize: 12.5 }}>
              {compare.label}: {hc.value.toFixed(compare.decimals)} {compare.unit}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
