'use client';

import { radioGroupKeys } from '@/lib/a11y';
import { AnimatePresence, motion } from 'motion/react';
import Link from 'next/link';
import { useId, useMemo, useState, useTransition } from 'react';
import { evaluateReading, saveReading } from '@/app/actions';
import { cx, fmtMetric, unitFor } from '@/lib/format';
import type {
  Environment,
  EscalationTier,
  Evaluation,
  Hazard,
  MeasureContext,
  MetricDef,
  MetricState,
  SaveResult,
  Symptom,
  Task,
} from '@/lib/types';
import { RangeBar } from '../charts/RangeBar';
import { Icon } from '../ui/Icon';
import { SourceList } from '../ui/SourceTag';
import {
  ArrowRight,
  Check,
  ChevronLeft,
  CircleAlert,
  CircleCheck,
  Clock,
  LoaderCircle,
  RadioTower,
  RotateCcw,
  Siren,
  Sparkles,
  Stethoscope,
  TriangleAlert,
  Users,
} from '../ui/icons';
import { StatusChip } from '../ui/StatusChip';
import { useToast } from '../ui/Toast';
import { AmslerTest, MoodPicker, NumberInput, ReactionTest, SymptomPicker } from './inputs';
import s from './wizard.module.css';

const STEPS = ['Prepare', 'Why it matters', 'Measure', 'Result'];
const ANOMALY: Record<string, number | [number, number]> = {
  hr: 128, bp: [148, 95], spo2: 89, resp: 26, temp: 38.6, glucose: 52, hydration: 1.2, sleep: 5.2, exercise: 40, nutrition: 55,
};

interface Props {
  metric: MetricDef;
  state: MetricState;
  task: Task | null;
  bundle: { id: string; label: string }[];
  symptoms: Symptom[];
  hazards: Hazard[];
  env: Environment;
  contexts: MeasureContext[];
  /** The escalation tiers from the catalog, so the ladder always matches the rules. */
  escalation: EscalationTier[];
}

/** Routine tasks whose readings are taken after exertion by design (mirrors the engine's TASK_CONTEXT). */
const TASK_CONTEXT: Record<string, MeasureContext['id']> = { post_eva: 'after_eva' };

export function MeasureWizard({ metric, state, task, bundle, symptoms, hazards, env, contexts, escalation }: Props) {
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [value, setValue] = useState<number | null>(null);
  const [value2, setValue2] = useState<number | null>(null);
  const [items, setItems] = useState<string[]>([]);
  const [context, setContext] = useState<MeasureContext['id'] | null>(task ? (TASK_CONTEXT[task.id] ?? null) : null);
  const askContext = Boolean(metric.context_sensitive) && contexts.length > 0;
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [saved, setSaved] = useState<SaveResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const reasonId = useId();
  const kind = metric.input.kind;
  const { min, max } = metric.input;

  const valid =
    kind === 'symptoms' ||
    (kind === 'bp'
      ? value !== null && value2 !== null && value >= min && value <= max && value2 >= 30 && value2 < value
      : value !== null && value >= min && value <= max);

  const missingReason = useMemo(() => {
    if (valid) return null;
    if (kind === 'bp') {
      if (value === null && value2 === null) return 'Enter systolic and diastolic';
      if (value === null) return 'Enter systolic';
      if (value < min || value > max) return `Systolic must be ${min}–${max}`;
      if (value2 === null) return 'Enter diastolic';
      if (value2 < 30 || value2 >= value) return `Diastolic must be 30–${value ? value - 1 : max}`;
      return 'Enter valid blood pressure';
    }
    if (value === null) {
      if (kind === 'mood') return 'Pick how you feel';
      if (kind === 'reaction') return 'Finish all three trials';
      if (kind === 'amsler') return 'Check both eyes';
      return `Enter ${metric.label.toLowerCase()}`;
    }
    if (value < min || value > max) return `Value must be ${min}–${max} ${metric.unit}`;
    return 'Enter a valid reading';
  }, [valid, kind, value, value2, min, max, metric]);

  const input = () => ({
    metric: metric.id,
    value: kind === 'symptoms' ? items.length : value,
    value2: kind === 'bp' ? value2 : null,
    meta: kind === 'symptoms' ? { items } : askContext && context ? { context } : null,
    task_id: task?.id ?? null,
  });

  const evaluate = () => {
    if (!valid) return;
    setError(null);
    start(async () => {
      const res = await evaluateReading(input());
      if (res.ok) {
        setEvaluation(res.data);
        setStep(3);
      } else setError(res.error);
    });
  };

  const save = () => {
    setError(null);
    start(async () => {
      const res = await saveReading(input());
      if (!res.ok) {
        setError(res.error);
        return;
      }
      setSaved(res.data);
      const r = res.data;
      // The bonuses on top of the base XP, e.g. "On time +10 · 3-day streak +6".
      const extras = (r.xp_breakdown ?? []).slice(1).map((l) => `${l.reason} +${l.amount}`).join(' · ');
      toast({
        tone: 'success',
        // Saved, but out of range: the caution tone, so the ear hears what the screen says.
        sound: r.evaluation.status === 'ok' ? 'success' : 'warning',
        title: `${metric.label} saved · +${r.xp_gained} XP`,
        body: [r.task?.completed ? `${r.task.title} complete` : '', extras].filter(Boolean).join('. ') || undefined,
      });
      if (r.level_up)
        toast({ tone: 'reward', title: `Level ${r.level_up.level} reached: ${r.level_up.title}`, body: 'Every check you finish counts.' });
      if ((r.xp_breakdown ?? []).some((l) => l.reason.startsWith('Full orbit')))
        toast({ tone: 'reward', title: 'Full orbit · +40 XP', body: 'Every scheduled check today is done.' });
      for (const b of r.badges_unlocked) toast({ tone: 'reward', title: `Badge unlocked: ${b.name}`, body: b.description });
      if (r.loop_closed)
        toast({ tone: 'reward', title: 'Loop closed · +10 XP', body: 'Thanks for re-measuring. The follow-up counts, whatever the value.' });
      for (const q of r.quests_completed ?? []) toast({ tone: 'reward', title: 'Quest complete · +30 XP', body: q });
      if (r.packet && r.packet.kind !== 'cmo') {
        toast({ tone: 'warning', title: 'Priority packet sent to Earth', body: r.packet.title });
      }
    });
  };

  const simulate = (anomaly: boolean) => {
    const b = state.baseline;
    if (kind === 'bp') {
      if (anomaly) {
        const [a1, a2] = ANOMALY.bp as [number, number];
        setValue(a1);
        setValue2(a2);
      } else {
        setValue(Math.round((b ?? 116) + (Math.random() - 0.5) * 8));
        setValue2(Math.round((state.baseline2 ?? 76) + (Math.random() - 0.5) * 6));
      }
      return;
    }
    if (anomaly) {
      if (metric.id === 'mass') setValue(Number(((b ?? 70) * 0.93).toFixed(1)));
      else setValue(ANOMALY[metric.id] as number);
      return;
    }
    const base = b ?? Number(metric.input.placeholder);
    const v = base + (Math.random() - 0.5) * metric.min_sd * 2;
    setValue(Number(Math.min(max, Math.max(min, v)).toFixed(metric.decimals)));
  };

  const remaining = saved?.task?.remaining ?? [];
  const nextId = remaining[0];
  const nextLabel = bundle.find((b) => b.id === nextId)?.label;

  return (
    <div className={s.wizard}>
      <div className={s.top}>
        <Link href={task ? '/routine' : '/measure'} className="btn btn-text btn-sm">
          <ChevronLeft size={16} /> {task ? 'Routine' : 'All measurements'}
        </Link>
        {task ? (
          <div className={s.bundle}>
            <span className="overline">
              {task.title} · {task.metrics.indexOf(metric.id) + 1} of {task.metrics.length}
            </span>
            <div className={s.bundleDots}>
              {bundle.map((b) => (
                <span key={b.id} className={cx(s.bundleDot, task.logged.includes(b.id) && s.bundleDone,
                  b.id === metric.id && s.bundleNow)} title={b.label} />
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className={cx('card', s.card)}>
        <div className={s.titleRow}>
          <span className={s.icon}>
            <Icon name={metric.id} size={26} />
          </span>
          <div>
            <span className="overline">{metric.category}</span>
            <h1 className={s.title}>{metric.label}</h1>
          </div>
          <span className="spacer" />
          <span className="chip chip-neutral">
            <Clock size={13} /> {metric.duration}
          </span>
        </div>

        {!saved ? (
          <ol className={s.steps} aria-label="Progress">
            {STEPS.map((label, i) => (
              <li key={label} className={cx(i === step && s.stepOn, i < step && s.stepDone)}
                aria-current={i === step ? 'step' : undefined}>
                <span>{i < step ? <Check size={13} /> : i + 1}</span>
                <em>{label}</em>
              </li>
            ))}
          </ol>
        ) : null}

        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={saved ? 'saved' : step}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
            className={s.body}
          >
            {saved ? (
              <Saved saved={saved} metric={metric} nextId={nextId} nextLabel={nextLabel} task={task} env={env} />
            ) : step === 0 ? (
              <>
                <h2 className={s.h2}>How to measure</h2>
                <ol className={s.how}>
                  {metric.how.map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ol>
                {askContext ? (
                  <p className={s.contextHint}>
                    Just exercised or back from an EVA? You can still measure. Tell ASTRA in the next steps and it
                    uses recovery ranges instead of resting ones.
                  </p>
                ) : null}
                <div className={s.meta}>
                  <span className="chip chip-accent">
                    <Stethoscope size={13} /> {metric.device}
                  </span>
                  {hazards.map((h) => (
                    <span key={h.id} className="chip chip-neutral" title={h.summary}>
                      <span className="hz" style={{ width: 18, height: 18, fontSize: 12 }}>{h.id}</span> {h.name}
                    </span>
                  ))}
                </div>
              </>
            ) : step === 1 ? (
              <>
                <h2 className={s.h2}>Why it matters</h2>
                <p className={s.lead}>{metric.why}</p>
                <div className={s.spaceBox}>
                  <span className="overline">What space does to it</span>
                  <p>{metric.space}</p>
                </div>
                <div className={s.ranges}>
                  <div>
                    <span className="overline">Normal range</span>
                    <b className="num">
                      {metric.id === 'bp' && metric.ok2
                        ? `${metric.ok[0]}–${metric.ok[1]} / ${metric.ok2[0]}–${metric.ok2[1]}`
                        : metric.rule === 'relative'
                          ? `within ±${metric.ok[1]}% of reference`
                          : metric.id === 'vision'
                            ? 'No distortion'
                            : metric.id === 'symptoms'
                              ? 'None'
                              : `${metric.ok[0]}–${metric.ok[1]}`}{' '}
                      <small>{metric.rule === 'relative' || metric.id === 'vision' ? '' : unitFor(metric)}</small>
                    </b>
                  </div>
                  {metric.active ? (
                    <div>
                      <span className="overline">After exercise</span>
                      <b className="num">
                        {metric.id === 'bp' && metric.active.ok2
                          ? `${metric.active.ok[0]}–${metric.active.ok[1]} / ${metric.active.ok2[0]}–${metric.active.ok2[1]}`
                          : `${metric.active.ok[0]}–${metric.active.ok[1]}`}{' '}
                        <small>{unitFor(metric)}</small>
                      </b>
                    </div>
                  ) : null}
                  <div>
                    <span className="overline">Your baseline</span>
                    <b className="num">
                      {state.baseline !== null
                        ? fmtMetric(metric, state.baseline, state.baseline2 ?? null)
                        : '–'}{' '}
                      <small>{unitFor(metric)}</small>
                    </b>
                  </div>
                  <div>
                    <span className="overline">Last reading</span>
                    <b className="num">
                      {state.has_data ? fmtMetric(metric, state.value, state.value2) : '–'}{' '}
                      <small>{unitFor(metric)}</small>
                    </b>
                  </div>
                </div>
                <div className={s.evidence}>
                  <span className="overline">Where this comes from</span>
                  <SourceList ids={metric.sources} />
                </div>
              </>
            ) : step === 2 ? (
              <>
                <h2 className={s.h2}>
                  {kind === 'reaction' ? 'Alertness test' : kind === 'amsler' ? 'Amsler grid check' : kind === 'symptoms'
                    ? 'Any symptoms in the last 24 hours?' : kind === 'mood' ? 'How do you feel right now?' : 'Enter your reading'}
                </h2>
                {askContext ? (
                  <fieldset className={s.context}>
                    <legend>What were you doing just before?</legend>
                    <div className={s.contextOpts} role="radiogroup" aria-label="Measurement context" onKeyDown={radioGroupKeys} tabIndex={-1}>
                      {contexts.map((c, i) => (
                        <button key={c.id} type="button" role="radio" aria-checked={context === c.id}
                          tabIndex={i === Math.max(0, contexts.findIndex((x) => x.id === context)) ? 0 : -1}
                          className={cx(s.contextOpt, context === c.id && s.contextOn)}
                          onClick={() => setContext(context === c.id ? null : c.id)}>
                          <b>
                            {c.label}
                            {context === c.id ? <Check size={14} aria-hidden /> : null}
                          </b>
                          <small>{c.detail}</small>
                        </button>
                      ))}
                    </div>
                    <p className="faint" style={{ fontSize: 12.5, margin: 0 }}>
                      If you skip this, ASTRA assumes you are resting, unless you logged exercise in the last 30 minutes.
                    </p>
                  </fieldset>
                ) : null}
                {kind === 'number' ? (
                  <NumberInput metric={metric} value={value} onChange={setValue} onEnter={evaluate} focusOnMount />
                ) : kind === 'bp' ? (
                  <div className={s.bpRow}>
                    <NumberInput metric={metric} value={value} onChange={setValue} label="Systolic" focusOnMount />
                    <span className={s.slash}>/</span>
                    <NumberInput metric={metric} value={value2} onChange={setValue2} label="Diastolic" onEnter={evaluate} />
                  </div>
                ) : kind === 'mood' ? (
                  <MoodPicker value={value} onChange={setValue} labels={metric.input.labels ?? []} />
                ) : kind === 'reaction' ? (
                  <ReactionTest onDone={setValue} />
                ) : kind === 'amsler' ? (
                  <AmslerTest labels={metric.input.labels ?? []} onChange={setValue} />
                ) : (
                  <SymptomPicker symptoms={symptoms} value={items} onChange={setItems} />
                )}
                {kind === 'number' || kind === 'bp' ? (
                  <div className={s.sim}>
                    <span className="faint" style={{ fontSize: 12.5 }}>No sensor connected:</span>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => simulate(false)}>
                      Typical reading
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => simulate(true)}>
                      Unusual reading
                    </button>
                  </div>
                ) : null}
              </>
            ) : evaluation ? (
              <Result ev={evaluation} metric={metric} escalation={escalation} />
            ) : null}
          </motion.div>
        </AnimatePresence>

        {error ? (
          <div className={s.error} role="alert">
            <CircleAlert size={18} /> {error}
          </div>
        ) : null}

        {!saved && step === 2 && !valid && missingReason ? (
          <p id={reasonId} className={cx(s.hint, s.footHint)}>
            {missingReason}
          </p>
        ) : null}

        {!saved ? (
          <div className={s.foot}>
            {step > 0 ? (
              <button type="button" className="btn btn-ghost" onClick={() => setStep(step === 3 ? 2 : step - 1)}
                disabled={pending}>
                {step === 3 ? (
                  <>
                    <RotateCcw size={16} /> Measure again
                  </>
                ) : (
                  'Back'
                )}
              </button>
            ) : (
              <span />
            )}
            {step < 2 ? (
              <div className="row" style={{ gap: 8 }}>
                {/* Skips "Why it matters"; on that step "Start measuring" already goes straight to the reading. */}
                {step === 0 ? (
                  <button type="button" className="btn btn-text" onClick={() => setStep(2)}
                    title="Go straight to entering the reading, for checks you already know">
                    Quick entry
                  </button>
                ) : null}
                <button type="button" className="btn btn-primary btn-lg" onClick={() => setStep(step + 1)}>
                  {step === 0 ? "I'm ready" : 'Start measuring'} <ArrowRight size={17} />
                </button>
              </div>
            ) : step === 2 ? (
              <button
                type="button"
                className="btn btn-primary btn-lg"
                onClick={evaluate}
                disabled={!valid || pending}
                aria-describedby={!valid && missingReason ? reasonId : undefined}
              >
                {pending ? <LoaderCircle size={17} className="spin" /> : null}
                See result <ArrowRight size={17} />
              </button>
            ) : (
              <button type="button" className="btn btn-primary btn-lg" onClick={save} disabled={pending}>
                {pending ? <LoaderCircle size={17} className="spin" /> : <Check size={17} />} Save reading
              </button>
            )}
          </div>
        ) : null}
      </div>
      <p className={s.disclaimer}>
        ASTRA supports decisions; it does not diagnose. Ranges are simplified for this prototype.
      </p>
    </div>
  );
}

const TIER_ICON = { 0: CircleCheck, 1: Users, 2: RadioTower } as const;

function Result({ ev, metric, escalation }: { ev: Evaluation; metric: MetricDef; escalation: EscalationTier[] }) {
  const showBar = ['number', 'bp', 'mood', 'reaction'].includes(metric.input.kind);
  const axis: [number, number] = metric.axis ?? [ev.band.watch[0] - 2, ev.band.watch[1] + 2];
  const I = ev.status === 'ok' ? CircleCheck : ev.status === 'watch' ? TriangleAlert : CircleAlert;
  const isCategorical = metric.id === 'vision' || metric.id === 'symptoms' || metric.id === 'mood';
  const displayValue = metric.id === 'vision' ? (metric.input.labels?.[ev.value] ?? ev.display) : ev.display;
  const unit = isCategorical ? '' : unitFor(metric);

  // Clean duplicate tier prefix in escalation text (e.g. "Self-care. Self-care..." -> "Self-care: ...")
  const cleanEscalation = ev.escalation
    ? ev.escalation.replace(new RegExp(`^${ev.tier_name}[.:\\s]+`, 'i'), '').trim()
    : '';

  return (
    <div className={cx(`st-${ev.status}`, s.resultContainer)}>
      {/* Primary Result Card: clean symmetrical status frame, no tacky side-border */}
      <div className={s.resultHero}>
        <div className={s.resultHeroTop}>
          <div className={s.resultBadgeGroup}>
            <StatusChip status={ev.status} size="lg" label={ev.personal ? 'Watch · unusual for you' : undefined} />
            <span className={s.resultCategory}>{metric.label} assessment</span>
          </div>
          {ev.delta_text ? (
            <span className={s.resultDelta}>{ev.delta_text}</span>
          ) : null}
        </div>

        <div className={s.resultHeroMain}>
          <span className={s.resultIcon} aria-hidden>
            <I size={22} />
          </span>
          <div className={s.resultValueWrap}>
            <div className={cx(s.resultValue, isCategorical && s.resultValueText)}>
              <span className={isCategorical ? s.valText : 'num'}>
                {displayValue}
              </span>
              {unit ? <small className={s.resultUnit}>{unit}</small> : null}
            </div>
          </div>
        </div>

        {showBar ? (
          <div className={s.resultBarWrap}>
            <RangeBar value={ev.value} ok={ev.band.ok} watch={ev.band.watch} axis={axis} status={ev.status}
              unit={unitFor(metric)} baseline={ev.baseline} />
          </div>
        ) : null}
      </div>

      {/* Exertion / Recovery Context (if applicable) */}
      {ev.context && ev.context_label ? (
        <div className={cx(s.contextResult, ev.active && s.contextResultActive)}>
          <span className="chip chip-neutral">
            {ev.context_label}
            {ev.context_inferred ? ' · assumed' : ''}
          </span>
          <span>
            {ev.active
              ? `Graded on recovery ranges (normal ${ev.band.ok[0]}–${ev.band.ok[1]} ${unitFor(metric)}). Measure again at rest in ${ev.recheck_after_min} minutes.`
              : 'Graded on resting ranges.'}
            {ev.context_note ? <em> {ev.context_note}</em> : null}
          </span>
        </div>
      ) : null}

      {ev.meta?.items && ev.meta.items.length ? (
        <p className="muted" style={{ margin: '4px 0' }}>Reported: {ev.meta.items.join(', ').replaceAll('_', ' ')}</p>
      ) : null}

      {/* Clinical Guidance / What to do */}
      <div className={s.guide}>
        <div className={s.guideHead}>
          <Stethoscope size={15} className={s.guideIcon} aria-hidden />
          <span className="overline">Clinical guidance</span>
        </div>
        <p className={s.guideText}>{ev.guidance}</p>
      </div>

      {/* Escalation & Triage Protocol */}
      <div className={s.escalationSection}>
        <div className={s.escalationHead}>
          <span className="overline">Triage & Escalation Protocol</span>
          <span className={s.currentTierPill}>
            Tier {ev.tier} Active
          </span>
        </div>

        <div className={s.ladder} role="group" aria-label="Escalation tiers">
          {escalation.map((e) => ({ t: e.tier, name: e.name, subtitle: e.who, icon: TIER_ICON[e.tier] })).map((x) => {
            const isCurrent = x.t === ev.tier;
            const isPast = x.t < ev.tier;
            return (
              <div key={x.t} className={cx(s.rung, isCurrent && s.rungOn, isPast && s.rungPast)}>
                <span className={s.rungIconWrap}>
                  <x.icon size={15} />
                </span>
                <span className={s.rungText}>
                  <small className={s.rungTier}>Tier {x.t}</small>
                  <b className={s.rungName}>{x.name}</b>
                  <span className={s.rungSubtitle}>{x.subtitle}</span>
                </span>
                {isCurrent ? <span className={s.rungActiveDot} title="Current tier" aria-hidden /> : null}
              </div>
            );
          })}
        </div>

        <div className={s.escalationDetail}>
          <p className={s.escalationText}>
            <b>{ev.tier_name}:</b> {cleanEscalation || ev.escalation}
            {ev.tier_reasons.length ? <span className={s.escalationReasons}> ({ev.tier_reasons.join('; ')})</span> : null}
          </p>
        </div>
      </div>

      {ev.suggest_emergency ? (
        <div className={s.redAlertBig} role="alert">
          <Siren size={22} />
          <div>
            <b>Red flag: {ev.red_flags.join(', ')}</b>
            <span>If the crew member is unwell, start the emergency protocol now.</span>
          </div>
          <Link href="/emergency" className="btn btn-danger">
            Open emergency
          </Link>
        </div>
      ) : null}
    </div>
  );
}

function Saved({ saved, metric, nextId, nextLabel, task, env }: { saved: SaveResult; metric: MetricDef;
  nextId?: string; nextLabel?: string; task: Task | null; env: Environment }) {
  const ev = saved.evaluation;
  return (
    <div className={s.saved}>
      <motion.span className={s.savedCheck} initial={{ scale: 0.4, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 380, damping: 18 }}>
        <Check size={34} />
      </motion.span>
      <h2 className={s.h2} style={{ textAlign: 'center' }}>Saved to your health record</h2>
      <p className="muted" style={{ textAlign: 'center' }}>
        {metric.label} {ev.display} {unitFor(metric)} · <StatusChip status={ev.status} />
      </p>
      <div className={s.rewards}>
        <span className={s.xp}>
          <Sparkles size={16} /> +{saved.xp_gained} XP
        </span>
        {saved.task?.completed ? <span className="chip chip-lg chip-ok">✓ {saved.task.title} complete</span> : null}
        {saved.badges_unlocked.map((b) => (
          <span key={b.id} className="chip chip-lg chip-accent">
            <Icon name={b.icon} size={14} /> {b.name}
          </span>
        ))}
      </div>
      {saved.level_up ? (
        <motion.p className={s.levelUp} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15, duration: 0.3 }}>
          Level {saved.level_up.level} reached: <b>{saved.level_up.title}</b>
        </motion.p>
      ) : null}
      {(saved.xp_breakdown?.length ?? 0) > 1 ? (
        <ul className={s.xpLines} aria-label="How this XP was earned">
          {saved.xp_breakdown?.map((l) => (
            <li key={`${l.reason}-${l.amount}`}>
              <span>{l.reason}</span>
              <b>+{l.amount}</b>
            </li>
          ))}
        </ul>
      ) : null}
      {saved.packet ? (
        <div className="inset" style={{ marginTop: 6 }}>
          <div className="row" style={{ gap: 10 }}>
            {saved.packet.kind === 'cmo' ? <Users size={18} /> : <RadioTower size={18} />}
            <b style={{ fontSize: 14 }}>
              {saved.packet.kind === 'cmo' ? 'Crew Medical Officer alerted on board' : 'Priority packet sent to the flight surgeon'}
            </b>
          </div>
          <p className="faint" style={{ fontSize: 13, marginTop: 6 }}>
            {saved.packet.kind === 'cmo'
              ? 'They will review your trend with you.'
              : env.delay_s < 5
                ? 'Live link: the ground can respond now.'
                : `Arrives at Earth in about ${Math.round(env.delay_s / 60)} minutes. Track it in Crew & comms.`}
          </p>
        </div>
      ) : null}
      <div className={s.savedActions}>
        {nextId && task ? (
          <Link href={`/measure/${nextId}?task=${task.id}`} className="btn btn-primary btn-lg">
            Next: {nextLabel} <ArrowRight size={17} />
          </Link>
        ) : (
          <Link href="/" className="btn btn-primary btn-lg">
            Back to overview
          </Link>
        )}
        <Link href={`/trends?m=${metric.id}`} className="btn btn-ghost btn-lg">
          View trend
        </Link>
      </div>
    </div>
  );
}
