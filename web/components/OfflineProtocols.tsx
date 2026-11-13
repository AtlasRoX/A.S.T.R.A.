'use client';

import { useEffect, useState } from 'react';
import { Siren } from './ui/icons';

interface Step {
  id: string;
  title: string;
  detail?: string;
}
interface Protocol {
  id: string;
  name: string;
  summary: string;
  pre: Step[];
  tracks: { id: string; label: string; steps: Step[] }[];
  post: Step[];
  note?: string;
}

function Steps({ steps }: { steps: Step[] }) {
  return (
    <ol style={{ margin: '6px 0 12px', paddingLeft: 22, display: 'flex', flexDirection: 'column', gap: 8 }}>
      {steps.map((s) => (
        <li key={s.id}>
          <b style={{ fontSize: '1rem' }}>{s.title}</b>
          {s.detail ? <div className="muted" style={{ fontSize: '0.9375rem' }}>{s.detail}</div> : null}
        </li>
      ))}
    </ol>
  );
}

/**
 * The emergency protocols, readable when ASTRA Core is not running.
 *
 * They come from a static copy (public/emergency-protocols.json) that an engine test keeps identical to
 * the catalog. There is no timer, no patient record and no message to Earth here: those need the engine.
 */
export function OfflineProtocols() {
  const [protocols, setProtocols] = useState<Protocol[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    fetch('/emergency-protocols.json')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: Protocol[]) => alive && setProtocols(data))
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section aria-labelledby="offline-protocols" style={{ marginTop: 28 }}>
      <h2 id="offline-protocols" className="h-card" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Siren size={18} /> Emergency protocols, available offline
      </h2>
      <p className="faint" style={{ fontSize: '0.875rem', margin: '6px 0 12px' }}>
        Read-only. Without ASTRA Core there is no timer, no record and no alert to Mission Control: call it out on
        the crew loop and tell the ground by radio yourself.
      </p>
      {failed ? (
        <p className="muted">The protocol list could not be loaded.</p>
      ) : !protocols ? (
        <p className="faint">Loading protocols…</p>
      ) : (
        <div className="stack" style={{ gap: 8 }}>
          {protocols.map((p) => (
            <details key={p.id} className="inset" style={{ padding: '4px 14px' }}>
              <summary style={{ minHeight: 44, display: 'flex', alignItems: 'center', fontWeight: 600, cursor: 'pointer' }}>
                {p.name}
              </summary>
              <p className="muted" style={{ margin: '0 0 8px' }}>{p.summary}</p>
              <Steps steps={p.pre} />
              {p.tracks.map((t) => (
                <div key={t.id}>
                  <div className="overline">{t.label}</div>
                  <Steps steps={t.steps} />
                </div>
              ))}
              {p.post.length ? (
                <>
                  <div className="overline">Always</div>
                  <Steps steps={p.post} />
                </>
              ) : null}
              {p.note ? <p className="faint" style={{ fontSize: '0.8125rem' }}>{p.note}</p> : null}
            </details>
          ))}
        </div>
      )}
    </section>
  );
}
