import { cx } from '@/lib/format';

/**
 * Where a reading came from, as a small glyph plus a text label for assistive technology.
 *
 *   manual  pencil   entered by the crew member
 *   sensor  dot      from a connected device (none exist in this demo)
 *   sim     diamond  written by the telemetry simulator
 *   seed    clock    the synthetic demo history
 *
 * Simulated readings get a tinted diamond (no word) and the full label as a tooltip and for screen readers.
 */
const SOURCES: Record<string, { label: string; path: React.ReactNode }> = {
  manual: {
    label: 'Entered by hand',
    path: <path d="M4 20l1-4L16.5 4.5a2 2 0 013 3L8 19l-4 1z" />,
  },
  sensor: {
    label: 'From a sensor',
    path: (
      <>
        <circle cx="12" cy="12" r="3" />
        <circle cx="12" cy="12" r="8" />
      </>
    ),
  },
  sim: { label: 'Live telemetry', path: <path d="M12 3l9 9-9 9-9-9z" /> },
  seed: {
    label: 'Demo history',
    path: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
  },
};

export function ReadingSource({ source, className }: { source?: string | null; className?: string }) {
  const s = SOURCES[source ?? 'manual'];
  if (!s) return null;
  const isSim = source === 'sim';
  return (
    <span
      className={cx('reading-source', isSim && 'reading-source-sim', className)}
      title={s.label}
      data-source={source ?? 'manual'}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {s.path}
      </svg>
      <span className="sr-only">{s.label}</span>
    </span>
  );
}
