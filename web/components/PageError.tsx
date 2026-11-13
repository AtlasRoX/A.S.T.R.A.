'use client';

import { RotateCcw, TriangleAlert } from './ui/icons';

/**
 * An error shown inside the page, with the header and navigation still around it.
 * Only this page failed; the rest of the app keeps working, and Retry runs the page's loaders again.
 */
export function PageError({ offline, onRetry }: { offline: boolean; onRetry: () => void }) {
  return (
    <div className="page" role="alert">
      <div className="card" style={{ maxWidth: 640, padding: 24 }}>
        <div className="row" style={{ gap: 10, marginBottom: 10 }}>
          <TriangleAlert size={20} style={{ color: 'var(--watch)' }} />
          <h1 className="h-card" style={{ margin: 0 }}>
            {offline ? 'ASTRA Core is not responding' : 'This page could not be loaded'}
          </h1>
        </div>
        <p className="muted" style={{ marginBottom: 16 }}>
          {offline
            ? 'The health engine stopped answering. The other pages keep what they already loaded; start the engine (npm run dev from the project root) and try again.'
            : 'Something went wrong while loading this page. The rest of the app is unaffected.'}
        </p>
        <button type="button" className="btn btn-primary" onClick={onRetry}>
          <RotateCcw size={16} /> Try again
        </button>
      </div>
    </div>
  );
}
