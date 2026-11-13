'use client';

import { OfflineProtocols } from './OfflineProtocols';
import { Logo } from './ui/Logo';
import { RotateCcw, Satellite } from './ui/icons';

export function EngineOffline({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <main
      style={{
        minHeight: '100dvh',
        display: 'grid',
        placeItems: 'start center',
        padding: 24,
      }}
    >
      <div className="card rise" style={{ maxWidth: 720, width: '100%', padding: 32 }}>
        <div className="row" style={{ gap: 12, marginBottom: 20 }}>
          <Logo height={28} />
          <span className="overline">Onboard health</span>
        </div>
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: 16,
            display: 'grid',
            placeItems: 'center',
            background: 'var(--watch-soft)',
            color: 'var(--watch)',
            marginBottom: 16,
          }}
        >
          <Satellite size={28} />
        </div>
        <h1 className="h-page" style={{ fontSize: 26 }}>
          ASTRA Core is not responding
        </h1>
        <p className="muted" style={{ margin: '10px 0 18px' }}>
          {message} The health engine (Python) runs beside this interface. Start both from the project root:
        </p>
        <pre
          className="inset num"
          style={{ margin: '0 0 20px', fontSize: 13, overflowX: 'auto', whiteSpace: 'pre-wrap' }}
        >
          npm run dev
        </pre>
        <button
          className="btn btn-primary"
          onClick={() => (onRetry ? onRetry() : window.location.reload())}
        >
          <RotateCcw size={17} />
          Retry connection
        </button>
        <OfflineProtocols />
      </div>
    </main>
  );
}
