'use client';

import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { ReadingSource } from '../ui/ReadingSource';
import { Component, type ReactNode, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { ageLabel, cx, fmt, signed, STATUS_LABEL, unitFor } from '@/lib/format';
import type { Hazard, MetricDef, MetricState, OrganDef, Status, Symptom, SystemState } from '@/lib/types';
import { Sparkline } from '../charts/Sparkline';
import { SourceList } from '../ui/SourceTag';
import { ArrowRight, ChevronLeft } from '../ui/icons';
import { Anatomy } from './Anatomy';
import type { BodyView, Layers, SkinMode } from './Body3D';
import s from './body.module.css';
import s3 from './body3d.module.css';

// Three.js only runs in the browser; load it lazily so the page stays fast.
const Body3D = dynamic(() => import('./Body3D').then((m) => m.Body3D), {
  ssr: false,
  loading: () => <div className={s3.fallback}>Loading anatomy</div>,
});
const MODEL_URL = '/models/astra-anatomy.glb';

let webglCache: boolean | null = null;
function hasWebGL() {
  if (webglCache === null) {
    try {
      const c = document.createElement('canvas');
      webglCache = Boolean(c.getContext('webgl2') ?? c.getContext('webgl'));
    } catch {
      webglCache = false;
    }
  }
  return webglCache;
}
const noop = () => () => {};
// Muscles view needs a hovering pointer for the x-ray lens.
const canHover = () => window.matchMedia('(hover: hover) and (pointer: fine)').matches;

/** If the 3D model can't load (missing file, GPU error), show the 2D body map instead of crashing. */
class Fallback3D extends Component<{ fallback: ReactNode; children: ReactNode; onFail: () => void },
  { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.warn('3D anatomy unavailable, using the 2D body map instead.', error);
    this.props.onFail();
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

const LAYER_LABEL = { skeleton: 'Skeleton', organs: 'Organs' } as const;
const SKIN_OPTIONS: { id: SkinMode; label: string }[] = [
  { id: 'muscles', label: 'Muscle' },
  { id: 'skeletal', label: 'Skeletal' },
];
const VIEW_OPTIONS: { id: BodyView; label: string }[] = [
  { id: 'anatomy', label: 'Natural' },
  { id: 'status', label: 'Status' },
];
const NO_READING = 'No recent reading';

/** Neutral grey only when nothing is flagged: a stale Watch or Act keeps its colour. */
const isGrey = (st: MetricState) => st.status === 'ok' && (!st.has_data || st.stale === true);
const toneClass = (st: Status, grey: boolean) => (grey ? s.none : `st-${st}`);
const prettify = (id: string) => (id.charAt(0).toUpperCase() + id.slice(1)).replace(/_/g, ' ');
/** Exercise and fluids are graded on a rolling average: show it, so the status matches what is displayed. */
const basisOf = (m: MetricDef, st: MetricState) =>
  st.basis ? `${st.basis.days}-day avg ${fmt(st.basis.average, m.decimals)} ${unitFor(m)}`.trim() : '';
/** When a reading was taken and how it compares: body mass against the mission reference, the rest against usual. */
function detailOf(m: MetricDef, st: MetricState) {
  const when = st.stale && st.has_data && st.age_days !== null ? `Last reading ${st.age_days} days ago`
    : ageLabel(st.age_days, st.time);
  const parts = [when];
  if (m.id === 'mass' && st.change_pct !== undefined && st.change_pct !== null) {
    parts.push(`${signed(st.change_pct, 1)}% vs reference mass`);
  } else if (st.delta !== null && m.id !== 'symptoms' && m.id !== 'vision') {
    parts.push(`${signed(st.delta, m.id === 'mood' ? 1 : m.decimals)} vs your usual`);
  }
  const basis = basisOf(m, st);
  if (basis) parts.push(basis);
  return parts.join(', ');
}
const NO_SYSTEMS: SystemState[] = [];
const NO_SYMPTOMS: Symptom[] = [];

/** Single-choice button group with arrow-key navigation and a roving tab stop. */
function Choice<T extends string>({ label, options, value, onChange, disabled, title, className }: {
  label: string;
  options: { id: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  disabled?: boolean;
  title?: string;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKeyDown = (e: React.KeyboardEvent, i: number) => {
    const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = (i + d + options.length) % options.length;
    onChange(options[next].id);
    refs.current[next]?.focus();
  };
  return (
    <div className={cx(s.group, disabled && s.disabled, className)} role="radiogroup" aria-label={label}
      aria-disabled={disabled || undefined} title={title}>
      {options.map((o, i) => (
        <button key={o.id} ref={(el) => {
          refs.current[i] = el;
        }} type="button" role="radio" aria-checked={value === o.id} tabIndex={value === o.id ? 0 : -1}
          disabled={disabled} className={cx(s.tool, value === o.id && s.on)} onClick={() => onChange(o.id)}
          onKeyDown={(e) => onKeyDown(e, i)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function BodyExplorer({
  organs,
  organStatus,
  systems = NO_SYSTEMS,
  symptoms = NO_SYMPTOMS,
  metrics,
  states,
  hazards,
  heartRate,
  breathRate,
  crewName,
}: {
  organs: OrganDef[];
  organStatus: Record<string, Status>;
  /** Per-system state from the dashboard: staleness and the symptoms that belong to it. */
  systems?: SystemState[];
  /** Symptom catalog, for labels. */
  symptoms?: Symptom[];
  metrics: Record<string, MetricDef>;
  states: Record<string, MetricState>;
  hazards: Hazard[];
  heartRate: number;
  breathRate: number;
  crewName?: string;
}) {
  const [focus, setFocus] = useState<string | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  // Natural colouring shows status only as small highlights, so when anything is flagged open on Status.
  const [view, setView] = useState<BodyView>(() =>
    Object.values(organStatus).some((st) => st !== 'ok') ? 'status' : 'anatomy',
  );
  const [layers, setLayers] = useState<Layers>({ skeleton: true, organs: true });
  const webgl = useSyncExternalStore(noop, hasWebGL, () => true);
  const hoverable = useSyncExternalStore(noop, canHover, () => true);
  const reduced = useReducedMotion() ?? false;
  const [skinChoice, setSkinChoice] = useState<SkinMode | null>(null);
  const skinMode: SkinMode = skinChoice ?? 'muscles';
  const [failed3d, setFailed3d] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLElement>(null);
  /** Where keyboard focus goes once the panel has swapped: its heading, or a system's button in the list. */
  const focusTo = useRef<string | null>(null);

  // Check the model is there (headers only) while the 3D code downloads; Body3D preloads the model itself.
  const [model, setModel] = useState<'checking' | 'ok' | 'missing'>('checking');
  useEffect(() => {
    if (!webgl) return;
    let alive = true;
    void import('./Body3D');
    fetch(MODEL_URL, { method: 'HEAD' })
      .then((r) => alive && setModel(r.ok ? 'ok' : 'missing'))
      .catch(() => alive && setModel('missing'));
    return () => {
      alive = false;
    };
  }, [webgl]);
  const use3d = webgl && model !== 'missing' && !failed3d;

  const symptomLabel = useMemo(() => {
    const byId = new Map(symptoms.map((x) => [x.id, x.label]));
    return (id: string) => byId.get(id) ?? prettify(id);
  }, [symptoms]);
  // Systems in grey: stale (no fresh reading) and nothing flagged.
  const grey = useMemo(() => {
    const out: Record<string, boolean> = {};
    for (const o of organs) {
      const sys = systems.find((x) => x.id === o.id);
      const stale = sys?.stale ?? o.metrics.every((mid) => !states[mid] || !states[mid].has_data || states[mid].stale);
      out[o.id] = (organStatus[o.id] ?? 'ok') === 'ok' && Boolean(stale);
    }
    return out;
  }, [organs, systems, states, organStatus]);

  const open = (id: string | null) => setFocus(id);
  /** Back to all readings; keyboard focus returns to the system's button when it was in the panel. */
  const back = () => {
    if (focus && panel.current?.contains(document.activeElement)) focusTo.current = focus;
    setFocus(null);
  };

  // Escape returns to the whole body, unless another popup owns it or focus is elsewhere on the page.
  useEffect(() => {
    if (!focus) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return;
      if (document.querySelector('[aria-haspopup][aria-expanded="true"], [aria-modal="true"], dialog[open], [role="dialog"]')) {
        return;
      }
      const a = document.activeElement;
      if (a && a !== document.body && !root.current?.contains(a)) return;
      back();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const organ = focus ? organs.find((o) => o.id === focus) : undefined;
  const organSt = organ ? (organStatus[organ.id] ?? 'ok') : 'ok';
  const organGrey = organ ? grey[organ.id] : false;
  const word = (st: Status, g: boolean) => (g ? NO_READING : STATUS_LABEL[st]);
  const sysSymptoms = organ ? (systems.find((x) => x.id === organ.id)?.symptoms ?? []) : [];

  const valueOf = (m: MetricDef, st: MetricState) => {
    if (!st.has_data) return '–';
    if (m.id === 'vision') return m.input.labels?.[st.value ?? 0] ?? '–';
    if (m.id === 'symptoms') {
      const items = st.meta?.items ?? [];
      return items.length ? items.map(symptomLabel).join(', ') : 'None';
    }
    return st.display;
  };

  /** One reading in the all-systems list: name (and grading basis), trend, value, status. */
  const readingRow = (mid: string) => {
    const m = metrics[mid];
    const ms = states[mid];
    if (!m || !ms) return null;
    const mg = isGrey(ms);
    const value = valueOf(m, ms);
    const basis = basisOf(m, ms);
    return (
      <Link key={mid} href={`/trends?m=${mid}`} className={cx(s.row, toneClass(ms.status, mg))}>
        <span className={s.rowName}>
          {m.label}
          {basis ? <small>{basis}</small> : null}
        </span>
        <span className={s.spark}>
          {mid !== 'symptoms' && mid !== 'vision' ? (
            <Sparkline values={ms.spark} band={ms.band?.ok ?? null} status={ms.status} width={56} height={18} />
          ) : null}
        </span>
        <span className={s.rowValue} title={mid === 'symptoms' ? value : undefined}>
          {value}
          {mid !== 'vision' && ms.has_data ? <small>{unitFor(m)}</small> : null}
        </span>
        <span className={s.dot} aria-hidden />
        <span className="sr-only">{ms.personal ? 'Unusual for you' : word(ms.status, mg)}</span>
      </Link>
    );
  };
  // Readings that belong to no single system (the symptom check: each symptom raises its own system).
  const general = Object.keys(metrics).filter((id) => !organs.some((o) => o.metrics.includes(id)));

  const flat = (
    <Anatomy organs={organs} organStatus={organStatus} grey={grey} selected={focus} hover={hover} view={view}
      layers={layers} onSelect={open} onHover={setHover} />
  );
  const flagged = organ
    ? organ.metrics.filter((mid) => metrics[mid] && states[mid] && states[mid].status !== 'ok')
    : [];

  const hint = use3d
    ? hoverable
      ? skinMode === 'muscles' && view === 'anatomy'
        ? 'Point to see inside · click a system · drag to turn'
        : 'Click a system · drag to turn · scroll to zoom'
      : skinMode === 'muscles' && view === 'anatomy'
        ? 'Tap a system to see inside · pinch to zoom'
        : 'Tap a system · drag to turn · pinch to zoom'
    : hoverable
      ? 'Click a system for its readings'
      : 'Tap a system for its readings';
  const fade = reduced ? { duration: 0 } : { duration: 0.18 };

  return (
    <div ref={root} className={s.explorer}>
      <div className={s.stage}>
        <div className={s.canvasBox}>
          {webgl && model === 'checking' ? (
            <div className={s3.fallback}>Loading anatomy</div>
          ) : use3d ? (
            <Fallback3D fallback={flat} onFail={() => setFailed3d(true)}>
              <Body3D organs={organs} organStatus={organStatus} grey={grey} focus={focus} hover={hover} view={view}
                layers={layers} skinMode={skinMode} heartRate={heartRate} breathRate={breathRate} crewName={crewName}
                reduced={reduced} onSelect={open} onHover={setHover} />
            </Fallback3D>
          ) : (
            flat
          )}
        </div>

        {use3d ? (
          <Choice
            label="Body view"
            className={s.modes}
            options={SKIN_OPTIONS}
            value={skinMode}
            onChange={(m) => {
              setSkinChoice(m);
              if (focus) setFocus(null);
              if (view === 'status') setView('anatomy');
            }}
          />
        ) : null}

        {view === 'status' ? (
          <ul className={s.legend} aria-label="Status colours">
            {(['ok', 'watch', 'act'] as const).map((st) => (
              <li key={st} className={`st-${st}`}>
                <i aria-hidden />
                {STATUS_LABEL[st]}
              </li>
            ))}
            <li className={s.none}>
              <i aria-hidden />
              {NO_READING}
            </li>
          </ul>
        ) : !focus ? (
          <p className={s.hint}>{hint}</p>
        ) : null}

        <div className={s.toolbar} role="toolbar" aria-label="Body view">
          <div className={s.group} role="group" aria-label="Layers">
            {(Object.keys(LAYER_LABEL) as (keyof typeof LAYER_LABEL)[]).map((k) => (
              <button key={k} type="button" aria-pressed={layers[k]} className={cx(s.tool, layers[k] && s.on)}
                onClick={() => setLayers((l) => ({ ...l, [k]: !l[k] }))}>
                {LAYER_LABEL[k]}
              </button>
            ))}
          </div>
          <Choice label="Colour" options={VIEW_OPTIONS} value={view} onChange={setView} />
        </div>
      </div>

      <aside ref={panel} className={s.panel}>
        <p className="sr-only" aria-live="polite">
          {organ ? `${organ.name}: ${word(organSt, organGrey)}` : ''}
        </p>
        <AnimatePresence mode="wait" initial={false}>
          {organ ? (
            <motion.div key={organ.id} initial={reduced ? false : { opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }}
              exit={reduced ? undefined : { opacity: 0 }} transition={fade}>
              <button type="button" className={s.back} onClick={back}>
                <ChevronLeft size={16} /> All readings
              </button>
              <div className={cx(s.systemHead, toneClass(organSt, organGrey))}>
                <h2 tabIndex={-1} ref={(el) => {
                  if (el && focusTo.current === 'heading') {
                    focusTo.current = null;
                    el.focus({ preventScroll: true });
                  }
                }}>
                  {organ.name}
                </h2>
                <span className={s.statusWord}>{word(organSt, organGrey)}</span>
              </div>
              <p className={s.lead}>{organ.function}</p>
              <ul className={s.readings}>
                {organ.metrics.map((mid) => {
                  const m = metrics[mid];
                  const st = states[mid];
                  if (!m || !st) return null;
                  const g = isGrey(st);
                  return (
                    <li key={mid} className={toneClass(st.status, g)}>
                      <Link href={`/trends?m=${mid}`} className={s.reading}>
                        <span className={s.rName}>
                          {m.label}
                          {st.source === 'sim' ? (
                            <span style={{ marginLeft: 6 }}>
                              <ReadingSource source="sim" />
                            </span>
                          ) : null}
                          <small>{detailOf(m, st)}</small>
                        </span>
                        <span className={cx(s.rValue, mid === 'symptoms' && s.rText)}>
                          {valueOf(m, st)}
                          {mid !== 'vision' && st.has_data ? <small>{unitFor(m)}</small> : null}
                        </span>
                        <span className={s.rStatus}>{st.personal ? 'Unusual for you' : word(st.status, g)}</span>
                      </Link>
                      <Link href={`/measure/${mid}`} className={s.measure}>
                        Measure
                      </Link>
                    </li>
                  );
                })}
              </ul>
              {sysSymptoms.length ? (
                <p className={cx(s.symptoms, `st-${organSt}`)}>
                  Reported in the last symptom check: {sysSymptoms.map(symptomLabel).join(', ')}.
                </p>
              ) : null}
              <h3 className={s.sub}>In space</h3>
              <p className={s.text}>{organ.space}</p>
              <h3 className={s.sub}>What to do</h3>
              {flagged.length ? (
                <ul className={s.guides}>
                  {flagged.map((mid) => {
                    const m = metrics[mid];
                    const st = states[mid].status;
                    return (
                      <li key={mid} className={`st-${st}`}>
                        <b>{m.label}</b>
                        <span>{m.guide[st]}</span>
                        {st === 'act' && m.escalate ? <span className={s.escalate}>{m.escalate}</span> : null}
                      </li>
                    );
                  })}
                </ul>
              ) : null}
              <ul className={s.actions}>
                {organ.actions.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
              <p className={s.hazards}>
                Affected by: {organ.hazards.map((h) => hazards.find((x) => x.id === h)?.name ?? h).join(', ')}.
              </p>
              {organ.id === 'metabolism' || organ.id === 'immune' ? (
                <p className={s.i4Link}>
                  <Link href="/data/inspiration4">
                    See this in real astronauts <ArrowRight size={13} />
                  </Link>
                  <small>
                    Four Inspiration4 crew members flew a 3-day mission in 2021. Their actual blood panels are plotted
                    against their own reference ranges.
                  </small>
                </p>
              ) : null}
              <div className={s.organSources}>
                <SourceList ids={organ.sources} label="Evidence" />
              </div>
            </motion.div>
          ) : (
            <motion.div key="all" initial={reduced ? false : { opacity: 0 }} animate={{ opacity: 1 }}
              exit={reduced ? undefined : { opacity: 0 }} transition={reduced ? fade : { duration: 0.15 }}>
              <h3 className={s.panelTitle}>All readings by system</h3>
              <p className={s.lead}>
                {hoverable
                  ? 'Point at a system to find it on the body. Click it for what to do.'
                  : 'Tap a system for what to do.'}
              </p>
              <div className={s.systems}>
                {organs.map((o) => {
                  const st = organStatus[o.id] ?? 'ok';
                  const g = grey[o.id];
                  return (
                    // Hover previews the system on the body; a touch tap opens it instead (no sticky hover).
                    <section key={o.id} className={cx(s.system, hover === o.id && s.hot)}
                      onPointerEnter={(e) => {
                        if (e.pointerType !== 'touch') setHover(o.id);
                      }}
                      onPointerLeave={() => setHover((h) => (h === o.id ? null : h))}>
                      <button type="button" data-system={o.id} className={cx(s.systemBtn, toneClass(st, g))}
                        ref={(el) => {
                          if (el && focusTo.current === o.id) {
                            focusTo.current = null;
                            el.focus({ preventScroll: true });
                          }
                        }}
                        onClick={() => {
                          focusTo.current = 'heading';
                          open(o.id);
                        }}
                        // Keyboard focus previews the system on the body; focus left by a mouse click doesn't.
                        onFocus={(e) => {
                          if (e.currentTarget.matches(':focus-visible')) setHover(o.id);
                        }}
                        onBlur={() => setHover((h) => (h === o.id ? null : h))}>
                        <span>{o.name}</span>
                        {st !== 'ok' || g ? <span className={s.statusWord}>{word(st, g)}</span> : null}
                      </button>
                      {o.metrics.map(readingRow)}
                    </section>
                  );
                })}
                {general.length ? (
                  <section className={s.system}>
                    <p className={s.systemBtn}>
                      <span>General</span>
                    </p>
                    {general.map(readingRow)}
                  </section>
                ) : null}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <p className={s.credit}>
          3D anatomy:{' '}
          <a href="https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html" target="_blank" rel="noopener noreferrer">
            BodyParts3D, DBCLS (CC BY 4.0, modified)
          </a>
        </p>
        <p className={s.credit}>ASTRA supports decisions; it does not diagnose.</p>
      </aside>
    </div>
  );
}
