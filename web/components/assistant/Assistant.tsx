'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Fragment, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { cx } from '@/lib/format';
import type { CrewMember } from '@/lib/types';
import { CrewAvatar } from '../ui/CrewAvatar';
import { ArrowUp, ChevronRight, Siren, Square, X } from '../ui/icons';
import s from './assistant.module.css';
import { alertSound } from '@/lib/sound';

/* ------------------------------------------------------------------ types */
type Status = 'ok' | 'watch' | 'act';
interface ReadingEnt {
  crew_id: string;
  crew: string;
  metric: string;
  label: string;
  value: string;
  unit: string;
  status: Status;
  age_days: number | null;
  href: string;
}
interface CrewEnt {
  id: string;
  name: string;
  role: string;
  overall: Status;
  eva: 'go' | 'caution' | 'nogo';
  issue: string | null;
  href: string;
}
interface ActionEnt {
  label: string;
  href: string;
  tone?: 'danger';
}
interface ProtocolEnt {
  name: string;
  steps: { title: string; detail: string }[];
}
interface Entities {
  reading: Record<string, ReadingEnt>;
  crew: Record<string, CrewEnt>;
  action: Record<string, ActionEnt>;
  protocol: Record<string, ProtocolEnt>;
}
interface Msg {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  entities?: Entities;
  error?: boolean;
}
interface Notice {
  id: string;
  /** reward: XP earned, a level reached or a badge (from the XP ledger), so a crew member sees what each check paid. */
  kind: 'alert' | 'ground' | 'reward';
  severity: Status | 'info';
  crew_id: string | null;
  crew: string;
  title: string;
  detail: string;
  at_label: string;
  ago: string;
  href: string;
}
interface NoticeLog {
  now_label: string;
  items: Notice[];
}

/** One crew member's notification log, or null if it could not be loaded. */
async function fetchNotices(crewId: string, signal?: AbortSignal): Promise<NoticeLog | null> {
  try {
    const res = await fetch(`/api/assistant/notifications?crew=${encodeURIComponent(crewId)}`, {
      cache: 'no-store',
      signal,
    });
    return res.ok ? ((await res.json()) as NoticeLog) : null;
  } catch {
    return null;
  }
}

/**
 * Sounds for the notification log: each new alert once (Act: 3 pulses, reminded while open; Watch: one soft tone,
 * only for the viewer's own), and a ping when a reply from Earth arrives. The engine remembers what was heard.
 */
function announce(items: Notice[], viewerId: string) {
  for (const n of items) {
    if (n.kind === 'ground') alertSound(n.id, 'receive');
    else if (n.kind === 'alert' && n.severity === 'act') alertSound(n.id, 'act');
    else if (n.kind === 'alert' && n.severity === 'watch' && n.crew_id === viewerId) alertSound(n.id, 'watch');
  }
}

const GENERAL = [
  'How is the whole crew today?',
  'What should I keep an eye on in my readings?',
  'Why was my exercise plan changed?',
  'Who needs attention first?',
];
const METRIC_NAME: Record<string, string> = {
  hr: 'heart rate', bp: 'blood pressure', spo2: 'blood oxygen', resp: 'breathing rate', temp: 'temperature',
  glucose: 'blood glucose', hydration: 'fluid intake', mass: 'body mass', nutrition: 'food intake', sleep: 'sleep',
  mood: 'mood', reaction: 'reaction time', exercise: 'exercise', vision: 'vision', symptoms: 'symptoms',
};

/** Suggested questions for the page being viewed, so the first question is one tap away. */
function suggestionsFor(path: string, query: string, crew: CrewMember[], viewerId: string): string[] {
  const profile = /^\/crew\/(\w+)/.exec(path)?.[1];
  const person = crew.find((c) => c.id === profile);
  if (person) {
    const n = person.name.split(' ')[0];
    return person.id === viewerId
      ? ['How is my health today?', 'How does my history affect today?', 'What should I measure next?', 'Am I cleared for EVA?']
      : [`How is ${n} doing today?`, `How does ${n}'s history affect today?`, `What should ${n} do about the open alerts?`, `Is ${n} cleared for EVA?`];
  }
  const metric = /^\/measure\/(\w+)/.exec(path)?.[1] ?? new URLSearchParams(query).get('m');
  if ((path.startsWith('/trends') || path.startsWith('/measure')) && metric && METRIC_NAME[metric]) {
    const m = METRIC_NAME[metric];
    return [`Explain my ${m} trend`, `Is my ${m} normal for me?`, `How do I measure ${m} correctly?`, `Who else in the crew has ${m} flagged?`];
  }
  if (path.startsWith('/exercise')) {
    return [
      'Why was my exercise plan changed?',
      "What does today's session protect?",
      "Can I swap today's session?",
      'How is the crew doing on exercise?',
    ];
  }
  if (path.startsWith('/crew')) return ['Who needs attention first?', 'How is the whole crew today?', 'Any replies from the ground?', 'Who is cleared for EVA?'];
  return GENERAL;
}
const CHAT_KEY = 'astra-assistant';
const SEEN_KEY = 'astra-assistant-seen';
const STATUS_WORD: Record<string, string> = { ok: 'Nominal', watch: 'Watch', act: 'Act' };
const EVA_WORD = { go: 'EVA go', caution: 'EVA caution', nogo: 'EVA no-go' } as const;
let seq = 0;
const newId = () => `${Date.now().toString(36)}-${(seq += 1)}`;
const readSet = (key: string) => {
  try {
    return new Set<string>(JSON.parse(localStorage.getItem(key) ?? '[]'));
  } catch {
    return new Set<string>();
  }
};
/** Phone width, where the panel is a full-screen sheet (same breakpoint as assistant.module.css). */
const PHONE = '(max-width: 767px)';
const onPhoneChange = (cb: () => void) => {
  const mq = window.matchMedia(PHONE);
  mq.addEventListener('change', cb);
  return () => mq.removeEventListener('change', cb);
};
const isPhone = () => window.matchMedia(PHONE).matches;

/* ------------------------------------------------------------------ live components inside answers */
function ReadingChip({ r }: { r: ReadingEnt }) {
  const age = r.age_days === null ? '' : r.age_days === 0 ? 'today' : `${r.age_days} d old`;
  return (
    <Link href={r.href} className={cx(s.reading, `st-${r.status}`)} title={`${r.crew}'s ${r.label}`}>
      <span className={s.readingLabel}>
        {r.crew} · {r.label}
      </span>
      <b>
        {r.value}
        {r.unit ? <small> {r.unit}</small> : null}
      </b>
      <span className={s.readingStatus}>
        {STATUS_WORD[r.status]}
        {age ? ` · ${age}` : ''}
      </span>
    </Link>
  );
}

function CrewCard({ c, member, compact }: { c: CrewEnt; member?: CrewMember; compact?: boolean }) {
  return (
    <Link href={c.href} className={cx(s.crewCard, compact && s.crewCompact, `st-${c.overall}`)}>
      {member ? <CrewAvatar member={member} size={compact ? 26 : 36} /> : null}
      <span className={s.crewText}>
        <b>{c.name}</b>
        <small>{c.issue ?? c.role}</small>
      </span>
      <span className={s.crewStatus}>
        <span className={s.statusWord}>{STATUS_WORD[c.overall]}</span>
        {compact ? null : <small>{EVA_WORD[c.eva]}</small>}
      </span>
      <ChevronRight size={16} className={s.crewArrow} aria-hidden />
    </Link>
  );
}

function ProtocolCard({ p }: { p: ProtocolEnt }) {
  return (
    <div className={s.protocol}>
      <b>
        <Siren size={15} aria-hidden /> {p.name}
      </b>
      <ol>
        {p.steps.map((st) => (
          <li key={st.title}>
            <strong>{st.title}.</strong> {st.detail}
          </li>
        ))}
      </ol>
    </div>
  );
}

function ActionButton({ a }: { a: ActionEnt }) {
  return (
    <Link href={a.href} className={cx(s.action, a.tone === 'danger' && s.actionDanger)}>
      {a.tone === 'danger' ? <Siren size={14} aria-hidden /> : null}
      {a.label}
      {a.tone === 'danger' ? null : <ChevronRight size={14} aria-hidden />}
    </Link>
  );
}

/* ------------------------------------------------------------------ answer renderer */
const TOKEN = /\[\[(reading|crew|action|protocol):([\w.:-]+)\]\]/g;

function fmt(text: string, key: string) {
  return text.split(/(\*\*[^*]+\*\*|_[^_\s][^_]*_)/g).map((part, i) => {
    const k = `${key}-${i}`;
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={k}>{part.slice(2, -2)}</strong>;
    if (part.length > 2 && part.startsWith('_') && part.endsWith('_')) return <em key={k}>{part.slice(1, -1)}</em>;
    return <Fragment key={k}>{part}</Fragment>;
  });
}

/** Text with **bold**, _italic_ and inline reading/action tokens. Unknown tokens are dropped, never shown raw. */
function inline(text: string, ents: Entities | undefined, keyBase: string) {
  const out: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    out.push(...fmt(text.slice(last, at), `${keyBase}t${last}`));
    const [kind, id] = [m[1], m[2]];
    const k = `${keyBase}k${at}`;
    if (kind === 'reading' && ents?.reading[id]) out.push(<ReadingChip key={k} r={ents.reading[id]} />);
    else if (kind === 'action' && ents?.action[id]) out.push(<ActionButton key={k} a={ents.action[id]} />);
    last = at + m[0].length;
  }
  out.push(...fmt(text.slice(last), `${keyBase}t${last}`));
  return out;
}

function Answer({ text, ents, crew }: { text: string; ents?: Entities; crew: CrewMember[] }) {
  // While streaming, hide a half-written token at the end ("[[read").
  const clean = text.replace(/\[\[[^\]]*\]?$/, '');
  const blocks: React.ReactNode[] = [];
  let list: { key: string; text: string }[] = [];
  let actions: React.ReactNode[] = [];
  // At most 2 action buttons per answer (the emergency button always counts first), however many the model wrote.
  let actionBudget = 2;
  const flushList = () => {
    if (list.length) {
      blocks.push(
        <ul key={`ul-${list[0].key}`}>
          {list.map((li) => (
            <li key={li.key}>{inline(li.text, ents, li.key)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  const flushActions = () => {
    if (actions.length) {
      blocks.push(
        <div key={`act-${blocks.length}`} className={s.actions}>
          {actions}
        </div>,
      );
      actions = [];
    }
  };
  // Three or more people in one answer: compact one-line rows instead of full cards.
  const compact = new Set([...clean.matchAll(TOKEN)].filter((m) => m[1] === 'crew').map((m) => m[2])).size >= 3;
  const crewCard = (id: string, key: string) =>
    ents?.crew[id] ? (
      <CrewCard key={key} c={ents.crew[id]} member={crew.find((c) => c.id === id)} compact={compact} />
    ) : null;

  clean.split('\n').forEach((raw, n) => {
    const line = raw.trim();
    const key = `l${n}`;
    if (!line) return;
    // A line made only of tokens becomes block components.
    if (line.replace(TOKEN, '').trim() === '') {
      flushList();
      for (const m of line.matchAll(TOKEN)) {
        const [kind, id] = [m[1], m[2]];
        const k = `${key}-${m.index}`;
        if (kind === 'action') {
          if (ents?.action[id] && actionBudget > 0) {
            actionBudget -= 1;
            actions.push(<ActionButton key={k} a={ents.action[id]} />);
          }
          continue;
        }
        flushActions();
        if (kind === 'crew') blocks.push(crewCard(id, k));
        else if (kind === 'protocol' && ents?.protocol[id]) blocks.push(<ProtocolCard key={k} p={ents.protocol[id]} />);
        else if (kind === 'reading' && ents?.reading[id])
          blocks.push(
            <div key={k} className={s.readingRow}>
              <ReadingChip r={ents.reading[id]} />
            </div>,
          );
      }
      return;
    }
    flushActions();
    const bullet = /^(?:[-*•]|\d+[.)])\s+(.*)$/.exec(line);
    if (bullet) {
      list.push({ key, text: bullet[1] });
      return;
    }
    flushList();
    // Crew or protocol tokens written inside a sentence still render as cards after it.
    const cards = [...line.matchAll(TOKEN)].filter((m) => m[1] === 'crew' || m[1] === 'protocol');
    blocks.push(<p key={key}>{inline(line.replace(/\[\[(crew|protocol):[\w.:-]+\]\]/g, '').trim(), ents, key)}</p>);
    for (const m of cards) {
      const k = `${key}-c${m.index}`;
      if (m[1] === 'crew') blocks.push(crewCard(m[2], k));
      else if (ents?.protocol[m[2]]) blocks.push(<ProtocolCard key={k} p={ents.protocol[m[2]]} />);
    }
  });
  flushList();
  flushActions();
  return <>{blocks}</>;
}

/* ------------------------------------------------------------------ main */
/**
 * The ASTRA specialist: a rounded launcher with an unseen-alert count, and a panel with two tabs. Chat streams
 * answers from ASTRA Core (relevant crew data + NVIDIA Nemotron via NIM); answers place live components (reading
 * chips, crew cards, protocol steps, buttons) whose values come from ASTRA's data, not from the model's text.
 * Alerts is the notification log: the person's own open alerts, everyone's Act alerts and ground replies, each
 * with the exact mission time it happened.
 */
export function Assistant({ viewerName, viewerId, crew }: { viewerName: string; viewerId: string; crew: CrewMember[] }) {
  const path = usePathname();
  const [open, setOpen] = useState(false);
  // The panel is built on its first open and then kept (hidden while closed), so it can animate both ways.
  const [mounted, setMounted] = useState(false);
  const returnFocus = useRef(false);
  const panel = useRef<HTMLElement>(null);
  const [tab, setTab] = useState<'chat' | 'alerts'>('chat');
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<NoticeLog>({ now_label: '', items: [] });
  const notices = log.items;
  const [seen, setSeen] = useState<Set<string>>(() => new Set());
  const abort = useRef<AbortController | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const phone = useSyncExternalStore(onPhoneChange, isPhone, () => false);
  const modal = open && phone;

  const fresh = notices.filter((n) => !seen.has(n.id));
  const earlier = notices.filter((n) => seen.has(n.id));
  const freshAlerts = fresh.filter((n) => n.kind !== 'reward');
  const freshRewards = fresh.length - freshAlerts.length;

  // Restore this tab's chat and the seen set.
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(CHAT_KEY);
      if (saved) {
        const restored = JSON.parse(saved) as Msg[];
        for (const m of restored) m.id ??= newId(); // chats saved before messages had ids
        // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time restore from browser storage after mount
        setMsgs(restored);
      }
    } catch {}
    setSeen(readSet(SEEN_KEY));
  }, []);
  // The notification log of whoever is viewing: load it now, poll it every minute, and start over when the viewer
  // changes (each person has their own alerts).
  useEffect(() => {
    const ctrl = new AbortController();
    const load = () =>
      fetchNotices(viewerId, ctrl.signal).then((data) => {
        if (!data) return;
        setLog(data);
        announce(data.items, viewerId);
      });
    void load();
    const t = setInterval(() => void load(), 60_000);
    // A new simulated reading just landed (LiveRefresh): look for new alerts now, not up to a minute later.
    const onData = () => void load();
    window.addEventListener('astra:data', onData);
    return () => {
      clearInterval(t);
      window.removeEventListener('astra:data', onData);
      ctrl.abort();
    };
  }, [viewerId]);
  useEffect(() => {
    try {
      sessionStorage.setItem(CHAT_KEY, JSON.stringify(msgs.slice(-30)));
    } catch {}
    list.current?.scrollTo({ top: list.current.scrollHeight });
  }, [msgs]);
  // While open, <html data-assistant="open"> lets the page make room for the docked panel on wide screens.
  useEffect(() => {
    const root = document.documentElement;
    if (open) root.dataset.assistant = 'open';
    else delete root.dataset.assistant;
    return () => {
      delete root.dataset.assistant;
    };
  }, [open]);
  useEffect(() => {
    if (!open) return;
    // preventScroll: the panel may still be sliding in, and nothing should scroll to chase it.
    if (tab === 'chat') input.current?.focus({ preventScroll: true });
    // Opened on Alerts: bring focus into the panel (unless it is already there, say on the Alerts tab itself).
    else if (!panel.current?.contains(document.activeElement)) panel.current?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        returnFocus.current = true;
        setOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, tab]);
  // Phone: the open panel is a full-screen sheet, so it is modal. What it covers (skip link, top bar, mission strip,
  // page, bottom navigation: its neighbours in the app shell) is inert until it closes or the window widens.
  useEffect(() => {
    const sheet = panel.current;
    if (!modal || !sheet?.parentElement) return;
    const covered = new Set<Element>(sheet.parentElement.children);
    for (const id of ['main-content', 'mission-strip']) {
      const el = document.getElementById(id);
      if (el) covered.add(el);
    }
    const made: HTMLElement[] = [];
    for (const el of covered) {
      if (el === sheet || el === button.current || !(el instanceof HTMLElement) || el.inert) continue;
      el.inert = true;
      made.push(el);
    }
    return () => {
      for (const el of made) el.inert = false;
    };
  }, [modal]);
  // Closing hands focus back to the launcher once it is shown again (it is hidden while the panel is open).
  useEffect(() => {
    if (open || !returnFocus.current) return;
    returnFocus.current = false;
    button.current?.focus();
  }, [open]);

  /** Mark everything in the log as read (when the Alerts tab is left or the panel closes). */
  const markSeen = () => {
    if (!fresh.length) return;
    const next = new Set([...seen, ...notices.map((n) => n.id)]);
    setSeen(next);
    try {
      localStorage.setItem(SEEN_KEY, JSON.stringify([...next].slice(-400)));
    } catch {}
  };
  const openPanel = () => {
    void fetchNotices(viewerId).then((data) => data && setLog(data));
    // New health alerts open first; otherwise the chat (new rewards wait in the Alerts tab).
    setTab(freshAlerts.length ? 'alerts' : 'chat');
    setMounted(true);
    setOpen(true);
  };
  const close = () => {
    if (tab === 'alerts') markSeen();
    returnFocus.current = true;
    setOpen(false);
  };
  const showTab = (next: 'chat' | 'alerts') => {
    if (tab === 'alerts' && next !== 'alerts') markSeen();
    setTab(next);
  };

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    showTab('chat');
    const history = msgs.filter((m) => !m.error).map(({ role, content }) => ({ role, content }));
    setMsgs((m) => [...m, { id: newId(), role: 'user', content: q }, { id: newId(), role: 'assistant', content: '' }]);
    setText('');
    setBusy(true);
    const ctrl = new AbortController();
    abort.current = ctrl;
    const patch = (fn: (m: Msg) => Msg) => setMsgs((all) => [...all.slice(0, -1), fn(all[all.length - 1])]);
    try {
      const res = await fetch('/api/assistant', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ question: q, history, page: `${window.location.pathname}${window.location.search}` }),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ error: `Error ${res.status}` }));
        patch((m) => ({ ...m, content: err.error ?? 'Something went wrong.', error: true }));
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      for (;;) {
        // Chunks must be read in order, one at a time.
        // eslint-disable-next-line no-await-in-loop
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.trim()) continue;
          const ev = JSON.parse(line) as { type: string; text?: string; entities?: Entities };
          if (ev.type === 'meta') patch((m) => ({ ...m, entities: ev.entities }));
          else if (ev.type === 'delta') patch((m) => ({ ...m, content: m.content + (ev.text ?? '') }));
        }
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError')
        patch((m) => ({ ...m, content: m.content || 'The specialist could not be reached.', error: true }));
    } finally {
      setBusy(false);
      abort.current = null;
    }
  };

  const renderNotice = (n: Notice, isNew: boolean) => {
    const member = crew.find((c) => c.id === n.crew_id);
    return (
      <li key={n.id} className={cx(s.notice, isNew && s.noticeNew)}>
        {member ? <CrewAvatar member={member} size={30} /> : <span className={s.noticeAvatar} />}
        <div className={s.noticeBody}>
          <div className={s.noticeTop}>
            <b>{n.title}</b>
            {n.kind === 'reward' ? (
              <span className={cx(s.sev, s.sevReward)}>XP</span>
            ) : n.severity !== 'info' ? (
              <span className={cx(s.sev, `st-${n.severity}`)}>{STATUS_WORD[n.severity]}</span>
            ) : (
              <span className={cx(s.sev, s.sevInfo)}>Ground</span>
            )}
          </div>
          {n.detail ? <p>{n.detail}</p> : null}
          <span className={s.noticeMeta}>
            {n.crew} · <time>{n.at_label}</time> · {n.ago}
          </span>
          <span className={s.noticeActions}>
            {n.kind === 'reward' ? (
              <button type="button" onClick={() => void ask('What should I do next today to keep my streak going and earn XP?')}>
                Next best step
              </button>
            ) : (
              <button type="button" onClick={() => void ask(`Explain this alert for ${n.crew}: "${n.title}". What should happen next?`)}>
                Ask ASTRA
              </button>
            )}
            <Link href={n.href} onClick={close}>
              Open
            </Link>
          </span>
        </div>
      </li>
    );
  };

  return (
    <>
      <button
        ref={button}
        type="button"
        hidden={open}
        className={s.fab}
        onClick={openPanel}
        aria-expanded={open}
        aria-controls="assistant-panel"
        aria-label={`Ask the ASTRA specialist${freshAlerts.length ? `, ${freshAlerts.length} new alert${freshAlerts.length > 1 ? 's' : ''}` : ''}${freshRewards ? `, ${freshRewards} new reward${freshRewards > 1 ? 's' : ''}` : ''}`}
      >
        {/* The real ASTRA mark; the pill is dark on both themes, so it uses the light-ink version. */}
        <span className={s.fabLogo} aria-hidden>
          {/* eslint-disable-next-line @next/next/no-img-element -- tiny static brand mark */}
          <img src="/logo-mark-dark.png" alt="" width={33} height={22} />
        </span>
        <span className={s.fabLabel}>Ask ASTRA</span>
        {/* Red count: health alerts only. New rewards alone get a small accent dot, so XP never looks urgent. */}
        {freshAlerts.length ? (
          <span className={s.badge} aria-hidden>
            {freshAlerts.length > 9 ? '9+' : freshAlerts.length}
          </span>
        ) : freshRewards ? (
          <span className={s.badgeReward} aria-hidden />
        ) : null}
      </button>

      {mounted ? (
        <section
          ref={panel}
          id="assistant-panel"
          tabIndex={-1}
          className={s.panel}
          role="dialog"
          aria-label="ASTRA specialist"
          aria-modal={modal || undefined}
          data-open={open}
          inert={!open}
        >
          <header className={s.head}>
            <div className={s.headText}>
              <h2>ASTRA specialist</h2>
              <p>Live crew data · asking as {viewerName}</p>
            </div>
            <button type="button" className={s.iconBtn} onClick={close} aria-label="Close">
              <X size={18} />
            </button>
          </header>
          <div className={s.tabs} role="tablist" aria-label="Specialist views">
            <button type="button" role="tab" aria-selected={tab === 'chat'} onClick={() => showTab('chat')}>
              Chat
            </button>
            <button type="button" role="tab" aria-selected={tab === 'alerts'} onClick={() => showTab('alerts')}>
              Alerts
              {fresh.length ? <span className={s.tabCount}>{fresh.length}</span> : null}
            </button>
            {tab === 'chat' && msgs.length ? (
              <button type="button" className={s.clear} onClick={() => setMsgs([])} disabled={busy}>
                New chat
              </button>
            ) : null}
          </div>

          {tab === 'alerts' ? (
            <div className={s.list} role="tabpanel" aria-label="Alerts">
              <p className={s.logHead}>Log as of {log.now_label || 'now'} (mission time)</p>
              {notices.length === 0 ? <p className={s.emptyLog}>No open alerts. Everything is nominal.</p> : null}
              {fresh.length ? (
                <>
                  <h3 className={s.groupHead}>New</h3>
                  <ul className={s.notices}>{fresh.map((n) => renderNotice(n, true))}</ul>
                </>
              ) : null}
              {earlier.length ? (
                <>
                  <h3 className={s.groupHead}>Earlier</h3>
                  <ul className={s.notices}>{earlier.map((n) => renderNotice(n, false))}</ul>
                </>
              ) : null}
            </div>
          ) : (
            <>
              <div ref={list} className={s.list} role="tabpanel" aria-label="Chat" aria-live="polite">
                {msgs.length === 0 ? (
                  <div className={s.empty}>
                    <p>
                      Ask about anyone&apos;s readings, history, exercise plan, radiation or the Earth link. Answers come
                      from ASTRA&apos;s live data.
                    </p>
                    <div className={s.suggestions}>
                      {suggestionsFor(path, typeof window === 'undefined' ? '' : window.location.search, crew, viewerId).map((q) => (
                        <button key={q} type="button" onClick={() => void ask(q)}>
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  msgs.map((m) =>
                    m.role === 'user' ? (
                      <div key={m.id} className={s.user}>
                        {m.content}
                      </div>
                    ) : (
                      <div key={m.id} className={cx(s.bot, m.error && s.botError)}>
                        {m.content ? (
                          <Answer text={m.content} ents={m.entities} crew={crew} />
                        ) : (
                          <span className={s.typing} aria-label="Thinking" />
                        )}
                      </div>
                    ),
                  )
                )}
              </div>
              <form
                className={s.form}
                onSubmit={(e) => {
                  e.preventDefault();
                  void ask(text);
                }}
              >
                <textarea
                  ref={input}
                  value={text}
                  rows={1}
                  maxLength={2000}
                  placeholder="Ask about the crew, readings or plans…"
                  aria-label="Your question"
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      void ask(text);
                    }
                  }}
                />
                {busy ? (
                  <button type="button" className={s.send} onClick={() => abort.current?.abort()} aria-label="Stop answering">
                    <Square size={14} />
                  </button>
                ) : (
                  <button type="submit" className={s.send} disabled={!text.trim()} aria-label="Send">
                    <ArrowUp size={17} />
                  </button>
                )}
              </form>
              <p className={s.disclaimer}>Not medical advice. In an emergency use the red Emergency button.</p>
            </>
          )}
        </section>
      ) : null}
    </>
  );
}
