import { STATUS_LABEL } from '@/lib/format';
import type { Status } from '@/lib/types';

/**
 * Horizontal zone bar: ACT | WATCH | NOMINAL | WATCH | ACT with a marker for the value.
 * Makes "where am I relative to normal?" readable at a glance.
 */
export function RangeBar({
  value,
  ok,
  watch,
  axis,
  status,
  unit,
  baseline,
}: {
  value: number;
  ok: [number, number];
  watch: [number, number];
  axis: [number, number];
  status: Status;
  unit: string;
  baseline?: number | null;
}) {
  const [a0, a1] = [Math.min(axis[0], value), Math.max(axis[1], value)];
  const pct = (v: number) => ((Math.min(Math.max(v, a0), a1) - a0) / (a1 - a0)) * 100;
  const all: { from: number; to: number; s: Status }[] = [
    { from: a0, to: watch[0], s: 'act' },
    { from: watch[0], to: ok[0], s: 'watch' },
    { from: ok[0], to: ok[1], s: 'ok' },
    { from: ok[1], to: watch[1], s: 'watch' },
    { from: watch[1], to: a1, s: 'act' },
  ];
  const zones = all.filter((z) => pct(z.to) - pct(z.from) > 0.2);
  const normalText =
    ok[1] >= a1 * 2
      ? `target ≥ ${ok[0]} ${unit}`.trim()
      : ok[0] <= a0 / 2
        ? `target ≤ ${ok[1]} ${unit}`.trim()
        : `normal ${ok[0]}–${ok[1]}`;

  // One sentence for assistive technology: the bar itself is a picture, the numbers are the content.
  const summary =
    `Reading ${value} ${unit}, ${STATUS_LABEL[status]}. ${normalText}. ` +
    `Watch range ${watch[0]} to ${watch[1]}.` +
    (baseline !== null && baseline !== undefined ? ` Your baseline is ${baseline}.` : '');

  return (
    <div role="img" aria-label={summary} style={{ padding: '12px 0 4px', width: '100%' }}>
      {/* Visual Bar Track with Markers */}
      <div
        style={{
          position: 'relative',
          height: 24,
          display: 'flex',
          alignItems: 'center',
          userSelect: 'none',
        }}
      >
        {/* The Colored Range Track */}
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            height: 10,
            borderRadius: 999,
            overflow: 'hidden',
            display: 'flex',
            boxShadow: 'inset 0 1px 2px rgba(0, 0, 0, 0.12)',
            background: 'var(--surface-3)',
          }}
        >
          {zones.map((z) => (
            <span
              key={`${z.s}-${z.from}`}
              style={{
                width: `${pct(z.to) - pct(z.from)}%`,
                background: `var(--${z.s})`,
                opacity: z.s === 'ok' ? 0.6 : 0.35,
              }}
            />
          ))}
        </div>

        {/* Baseline Marker */}
        {baseline !== null && baseline !== undefined ? (
          <div
            title={`Your baseline: ${baseline} ${unit}`}
            style={{
              position: 'absolute',
              left: `${pct(baseline)}%`,
              top: '50%',
              transform: 'translate(-50%, -50%)',
              width: 2,
              height: 20,
              background: 'var(--text-3)',
              borderRadius: 2,
              zIndex: 1,
            }}
          />
        ) : null}

        {/* The Selected Value Knob - perfectly vertically centered on the track */}
        <div
          className={`st-${status}`}
          title={`Reading: ${value} ${unit} (${status.toUpperCase()})`}
          style={{
            position: 'absolute',
            left: `${pct(value)}%`,
            top: '50%',
            transform: 'translate(-50%, -50%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 2,
          }}
        >
          <span
            style={{
              width: 20,
              height: 20,
              borderRadius: '50%',
              background: 'var(--st)',
              border: '3px solid var(--surface)',
              boxShadow: '0 0 0 1.5px var(--st), 0 2px 6px rgba(0, 0, 0, 0.25)',
              flexShrink: 0,
            }}
          />
        </div>
      </div>

      {/* Axis Scale Labels */}
      <div
        className="row faint num"
        style={{
          justifyContent: 'space-between',
          fontSize: 12,
          marginTop: 6,
          color: 'var(--text-3)',
        }}
      >
        <span>
          {a0} {unit}
        </span>
        <span style={{ fontWeight: 500, color: 'var(--text-2)' }}>
          {normalText}
        </span>
        <span>
          {a1} {unit}
        </span>
      </div>
    </div>
  );
}
