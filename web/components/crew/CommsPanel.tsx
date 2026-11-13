'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState, useTransition } from 'react';
import { sendGroundMessage } from '@/app/actions';
import { clockTime, cx, formatUtc } from '@/lib/format';
import type { Comms, Packet } from '@/lib/types';
import {
  Globe,
  Inbox,
  LoaderCircle,
  MessageSquare,
  RadioTower,
  Rocket,
  Send,
  Siren,
  TriangleAlert,
} from '../ui/icons';
import { useToast } from '../ui/Toast';
import { SourceTag } from '../ui/SourceTag';
import s from './crew.module.css';

/** Seconds since the latest server snapshot; restarts whenever fresh data arrives. */
function useTicker(snapshot: unknown) {
  const [now, setNow] = useState(() => Date.now());
  const [base, setBase] = useState(() => ({ snapshot, at: now }));
  if (base.snapshot !== snapshot) setBase({ snapshot, at: now });
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  return Math.max(0, (now - base.at) / 1000);
}

function live(p: Packet, dt: number) {
  if (p.kind === 'cmo' || p.status === 'replied') return { ...p };
  const eta = Math.max(0, p.eta_s - dt);
  const replyEta = p.reply_eta_s === null ? null : Math.max(0, p.reply_eta_s - dt);
  const status = eta > 0 ? 'in_transit' : replyEta && replyEta > 0 ? 'delivered' : 'replied';
  const progress = p.delay_s > 0 ? Math.min(1, 1 - eta / p.delay_s) : 1;
  return { ...p, eta_s: eta, reply_eta_s: replyEta, status, progress } as Packet;
}

const KIND_ICON = { alert: TriangleAlert, message: MessageSquare, emergency: Siren, cmo: Inbox } as const;

export function CommsPanel({ comms }: { comms: Comms }) {
  const router = useRouter();
  const toast = useToast();
  const dt = useTicker(comms);
  const [text, setText] = useState('');
  const [sending, startSend] = useTransition();
  const packets = comms.ground.map((p) => live(p, dt));
  const refreshed = useRef(new Set<number>());

  // When a packet is answered client-side, fetch the reply text from ASTRA Core once.
  useEffect(() => {
    for (const p of packets) {
      const orig = comms.ground.find((o) => o.id === p.id);
      if (orig && orig.status !== 'replied' && p.status === 'replied' && !refreshed.current.has(p.id)) {
        refreshed.current.add(p.id);
        router.refresh();
      }
    }
  });

  const inTransit = packets.filter((p) => p.status === 'in_transit');
  // Answered packets pile up over the mission: keep the two latest (the list is newest first) and fold the rest, so
  // the composer stays in reach on a phone.
  const [showEarlier, setShowEarlier] = useState(false);
  const recentReplied = new Set(packets.filter((p) => p.status === 'replied').slice(0, 2).map((p) => p.id));
  const shownPackets = showEarlier
    ? packets
    : packets.filter((p) => p.status !== 'replied' || recentReplied.has(p.id));
  const earlier = packets.length - shownPackets.length;
  const send = () => {
    const t = text.trim();
    if (!t) return;
    startSend(async () => {
      const res = await sendGroundMessage(t);
      if (res.ok) {
        setText('');
        toast({ tone: 'info', sound: 'send', title: 'Message sent to the flight surgeon',
          body: comms.live ? 'Live link: reply expected shortly.' : `Arrives in ${comms.delay_label}.` });
        router.refresh();
      } else toast({ tone: 'warning', title: 'Could not send', body: res.error });
    });
  };
  return (
    <div className="stack">
      <section className="card">
        <div className="card-head">
          <h2 className="h-card">
            <RadioTower size={17} /> Earth link
          </h2>
          <span className={cx('chip chip-dot', comms.live ? 'chip-ok' : 'chip-watch')}>
            {comms.live ? 'Live link' : `${comms.delay_label} one way`}
          </span>
        </div>
        <div className={s.link}>
          <span className={s.node}>
            <Rocket size={20} />
            <small>{comms.env_name}</small>
          </span>
          <div className={s.track}>
            <svg viewBox="0 0 400 40" preserveAspectRatio="none" aria-hidden>
              <path d="M4 20 C 120 4, 280 36, 396 20" className={s.trackPath} />
            </svg>
            {inTransit.map((p, i) => (
              <span key={p.id} className={cx(s.packetDot, p.priority >= 2 && s.hot)}
                // Keep every dot on the track (not under the node) and alternate lanes so packets sent together stay apart.
                style={{
                  left: `${4 + p.progress * 92}%`,
                  ['--lane' as string]: inTransit.length > 1 ? `${i % 2 ? 7 : -7}px` : '0px',
                }}
                title={`${p.title} · arrives in ${clockTime(p.eta_s)}`} />
            ))}
          </div>
          <span className={s.node}>
            <Globe size={20} />
            <small>Mission Control</small>
          </span>
        </div>
        <div className={s.linkStats}>
          <div>
            <span className="overline">One way</span>
            <b className="num">{comms.live ? '< 1 s' : comms.delay_label}</b>
          </div>
          <div>
            <span className="overline">Round trip</span>
            <b className="num">{comms.live ? '~1 s' : comms.round_trip_label}</b>
          </div>
          <div>
            <span className="overline">Next window</span>
            <b className="num">{comms.next_window.time}</b>
          </div>
        </div>
        <p className="faint" style={{ fontSize: 13, marginTop: 10 }}>
          {comms.delay_note.charAt(0).toUpperCase() + comms.delay_note.slice(1)}. ASTRA never waits for Earth: all
          guidance runs on board, and the ground gets
          store-and-forward summaries.
        </p>
        {comms.light_time_source ? (
          <div className={s.delaySource}>
            <SourceTag
              label="Light time from JPL Horizons"
              title={comms.light_time_source === 'horizons-scaled' ? 'Horizons (scaled)' : 'JPL Horizons'}
            />
            {comms.utc ? <span className="faint" style={{ fontSize: 12.5 }}>Mission time {formatUtc(comms.utc)}</span> : null}
          </div>
        ) : null}
        {comms.conjunction ? (
          <div className={cx(s.conjunction, comms.conjunction.status === 'act' && s.conjunctionAct)} role="alert">
            <TriangleAlert size={16} />
            <div>
              <b>{comms.conjunction.label}</b>
              <span>{comms.conjunction.detail}</span>
              <SourceTag sourceId="horizons-mars-lt" title="JPL Horizons · Sun–Mars angle" />
            </div>
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="card-head">
          <h2 className="h-card">
            <MessageSquare size={17} /> Packets to the flight surgeon
          </h2>
          <span className="faint" style={{ fontSize: 12.5 }}>
            Live countdowns
          </span>
        </div>
        {packets.length ? (
          <ul id="ground-packets" className={s.packets}>
            {shownPackets.map((p) => {
              const I = KIND_ICON[p.kind];
              return (
                <li key={p.id} className={cx(s.packet, p.priority >= 2 && s.priority)}>
                  <span className={s.pIcon}>
                    <I size={16} />
                  </span>
                  <div className={s.pBody}>
                    <div className="row wrap" style={{ gap: 8 }}>
                      <b>{p.title}</b>
                      <span className={cx('chip', p.status === 'replied' ? 'chip-ok' : p.status === 'delivered' ? 'chip-accent' : 'chip-watch')}>
                        {p.status === 'in_transit' ? 'In transit' : p.status === 'delivered' ? 'Delivered' : 'Replied'}
                      </span>
                    </div>
                    <small className="faint">
                      {p.crew_name} · sent {p.created}
                    </small>
                    {p.status === 'in_transit' ? (
                      <div className={s.progress}>
                        <div className="bar" style={{ height: 6 }}>
                          <i style={{ width: `${p.progress * 100}%` }} />
                        </div>
                        <span className="num">arrives in {clockTime(p.eta_s)}</span>
                      </div>
                    ) : p.status === 'delivered' ? (
                      <div className={s.progress}>
                        <span className="num faint">Ground is reviewing · earliest reply in {clockTime(p.reply_eta_s ?? 0)}</span>
                      </div>
                    ) : null}
                    {p.reply ? <p className={s.reply}>{p.reply}</p> : null}
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="empty">No packets yet.</p>
        )}
        {earlier > 0 || showEarlier ? (
          <button
            type="button"
            className={`btn btn-text btn-sm ${s.earlierBtn}`}
            aria-expanded={showEarlier}
            aria-controls="ground-packets"
            onClick={() => setShowEarlier(!showEarlier)}
          >
            {showEarlier ? 'Show fewer' : `Show ${earlier} earlier`}
          </button>
        ) : null}
        <div className={s.composer}>
          <textarea
            className="textarea"
            placeholder="Ask the flight surgeon a question or describe how you feel…"
            value={text}
            maxLength={600}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send();
            }}
            aria-label="Message to the flight surgeon"
          />
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="faint" style={{ fontSize: 12.5 }}>
              {comms.live ? 'Live link' : `Delivery takes ${comms.delay_label}`} ·{' '}
              {text.trim() ? 'Ctrl+Enter to send' : 'Type a message to send it'}
            </span>
            <button type="button" className="btn btn-primary btn-sm" onClick={send} disabled={!text.trim() || sending}>
              {sending ? <LoaderCircle size={15} className="spin" /> : <Send size={15} />} Send
            </button>
          </div>
        </div>
      </section>

    </div>
  );
}
