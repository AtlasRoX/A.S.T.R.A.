/**
 * A loading screen shaped like the page it stands in for: the real title appears at once, so the crew
 * sees which page is coming instead of a generic grid, and the layout does not jump when it arrives.
 */
export function PageLoading({
  title,
  blocks = 3,
  columns = false,
}: {
  title: string;
  /** How many content blocks to sketch. */
  blocks?: number;
  /** Sketch a two-column layout (list + detail). */
  columns?: boolean;
}) {
  return (
    <div className="page" aria-busy="true" aria-live="polite">
      <div className="page-head">
        <div>
          <h1 className="h-page">{title}</h1>
          <p className="faint">Loading…</p>
        </div>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: columns ? 'minmax(200px, 1fr) minmax(0, 2.4fr)' : '1fr',
          gap: 16,
        }}
      >
        {Array.from({ length: blocks }, (_, i) => (
          <div key={i} className="skeleton" style={{ height: i === 0 ? 120 : 160 }} aria-hidden="true" />
        ))}
      </div>
    </div>
  );
}
