import type { Metadata } from 'next';
import Link from 'next/link';
import { ReadingSource } from '@/components/ui/ReadingSource';
import {
  Activity,
  ChevronRight,
  Droplets,
  Dumbbell,
  Eye,
  Flame,
  Gauge,
  HeartPulse,
  type LucideIcon,
  Moon,
  Popcorn,
  Scale,
  Smile,
  Stethoscope,
  Thermometer,
  Timer,
  Wind,
} from '@/components/ui/icons';
import { getCatalog, getDashboard } from '@/lib/engine';
import { ageLabel, cx, symptomsText, unitFor } from '@/lib/format';
import { getSession } from '@/lib/session';
import type { MetricDef, Status } from '@/lib/types';
import s from './measure.module.css';

export const metadata: Metadata = { title: 'Measure' };

const STATUS_WORD: Record<Status, string> = { ok: 'Nominal', watch: 'Watch', act: 'Act' };

/** One icon per check, so the list can be scanned without reading. */
const METRIC_ICON: Record<string, LucideIcon> = {
  hr: HeartPulse,
  bp: Gauge,
  spo2: Activity,
  resp: Wind,
  temp: Thermometer,
  glucose: Flame,
  hydration: Droplets,
  mass: Scale,
  nutrition: Popcorn,
  sleep: Moon,
  mood: Smile,
  reaction: Timer,
  exercise: Dumbbell,
  vision: Eye,
  symptoms: Stethoscope,
};

export default async function MeasurePage() {
  const { crew, env } = await getSession();
  const [catalog, d] = await Promise.all([getCatalog(), getDashboard(crew, env)]);
  const pending = d.routine.tasks.filter((t) => t.state === 'due' || t.state === 'overdue');
  // Nothing due yet is not the same as everything done: point at the next scheduled check.
  const upcoming = d.routine.tasks.filter((t) => t.state === 'upcoming').toSorted((a, b) => a.time.localeCompare(b.time));
  const nextUp = upcoming[0];
  const taskFor = (mid: string) => pending.find((t) => t.metrics.includes(mid) && !t.logged.includes(mid));
  const groups = Object.entries(
    catalog.metrics.reduce<Record<string, MetricDef[]>>((acc, m) => {
      (acc[m.category] ??= []).push(m);
      return acc;
    }, {}),
  );

  const valueOf = (m: MetricDef) => {
    const st = d.metrics[m.id];
    if (!st.has_data) return 'No data';
    if (m.id === 'vision') return m.input.labels?.[st.value ?? 0] ?? '–';
    if (m.id === 'symptoms') return symptomsText(st.meta?.items, catalog.symptoms);
    return `${st.display} ${unitFor(m)}`;
  };
  const hrefOf = (m: MetricDef) => {
    const task = taskFor(m.id);
    return task ? `/measure/${m.id}?task=${task.id}` : `/measure/${m.id}`;
  };

  const row = (m: MetricDef) => {
    const st = d.metrics[m.id];
    const task = taskFor(m.id);
    const Icon = METRIC_ICON[m.id] ?? Activity;
    // The pill is always the health status; a pending routine task is its own neutral tag, so a group that
    // reads "All nominal" never shows an amber pill.
    return (
      <li key={m.id}>
        <Link href={hrefOf(m)} className={cx(s.row, `st-${st.status}`, st.stale && 'is-stale')}>
          <span className={s.icon} aria-hidden>
            <Icon size={17} />
          </span>
          <span className={s.name}>
            <span className={s.label}>
              {m.label}
              {task ? <span className={s.due}>Due</span> : null}
            </span>
            <small>
              {m.device}, {m.duration}
            </small>
          </span>
          <span className={s.value}>
            {valueOf(m)}
            <small>
              {ageLabel(st.age_days, st.time)} <ReadingSource source={st.source} />
            </small>
          </span>
          <span className={s.pill}>
            {STATUS_WORD[st.status]}
            {st.stale && st.has_data ? <span className="stale-word"> · stale</span> : null}
          </span>
          <ChevronRight size={16} className={s.chev} />
        </Link>
      </li>
    );
  };

  // Checks that need another look: flagged (Act first, then Watch) or out of date, and not already due.
  const rank = (m: MetricDef) => {
    const st = d.metrics[m.id];
    return st.has_data && st.status === 'act' ? 0 : st.has_data && st.status === 'watch' ? 1 : 2;
  };
  const recheck = catalog.metrics
    .filter((m) => {
      const st = d.metrics[m.id];
      return !taskFor(m.id) && ((st.has_data && st.status !== 'ok') || (st.has_data && st.stale));
    })
    .toSorted((x, y) => rank(x) - rank(y));

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h-page">Measure</h1>
          <p>Each check shows how to do it, why it matters in space, and what to do if the result looks off.</p>
        </div>
      </div>

      <div className={s.top}>
        {/* Due now: the next thing to do, with one big button. */}
        <section className={s.dueCard} aria-labelledby="due">
          <div className={s.cardHead}>
            <h2 id="due" className={s.h2}>
              Due now
            </h2>
            <Link href="/routine" className={s.link}>
              Full schedule ›
            </Link>
          </div>
          {pending.length ? (
            <ul className={s.dueList}>
              {pending.map((t) => {
                const next = t.metrics.find((m) => !t.logged.includes(m)) ?? t.metrics[0];
                const def = catalog.metrics.find((m) => m.id === next);
                const Icon = METRIC_ICON[next] ?? Activity;
                const late = t.state === 'overdue';
                return (
                  <li key={t.id}>
                    <Link href={`/measure/${next}?task=${t.id}`} className={cx(s.dueRow, late ? 'st-act' : 'st-watch')}>
                      <span className={s.dueIcon} aria-hidden>
                        <Icon size={20} />
                      </span>
                      <span className={s.dueText}>
                        <span className={s.dueWhen}>
                          {t.time} · {late ? 'Overdue' : 'Due'}
                        </span>
                        <b>{t.title}</b>
                        <small>
                          {t.metrics.length === 1 ? (
                            <>
                              One measurement
                              {def ? (
                                <>
                                  {' '}
                                  <span className={s.nowrap}>· {def.duration}</span>
                                </>
                              ) : null}
                            </>
                          ) : (
                            `${t.metrics.length} measurements, one after another`
                          )}
                        </small>
                      </span>
                      <span className="btn btn-primary">Start</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className={s.allDone}>
              {nextUp ? (
                <>
                  Nothing due right now. Next: <b>{nextUp.title}</b> at {nextUp.time}.{' '}
                  <Link
                    href={`/measure/${nextUp.metrics.find((m) => !nextUp.logged.includes(m)) ?? nextUp.metrics[0]}?task=${nextUp.id}`}
                    className={s.link}
                  >
                    Start early ›
                  </Link>
                </>
              ) : (
                'Every check for today is done.'
              )}
            </p>
          )}
        </section>

        {/* Needs re-check: one tap to measure again. */}
        {recheck.length ? (
          <section className={s.recheckCard} aria-labelledby="recheck">
            <div className={s.cardHead}>
              <h2 id="recheck" className={s.h2}>
                Needs re-check
              </h2>
              <span className={s.count}>{recheck.length}</span>
            </div>
            <ul className={s.chips}>
              {recheck.map((m) => {
                const st = d.metrics[m.id];
                const Icon = METRIC_ICON[m.id] ?? Activity;
                return (
                  <li key={m.id}>
                    <Link href={hrefOf(m)} className={cx(s.chip, `st-${st.status}`)}>
                      <Icon size={15} aria-hidden />
                      <span>{m.short || m.label}</span>
                      <b>{valueOf(m)}</b>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}
      </div>

      <h2 className={s.sectionTitle} id="all-checks">
        All checks
      </h2>
      {/* One card per body system, packed in columns so short groups leave no holes. */}
      <div className={s.groups}>
        {groups.map(([cat, ms]) => {
          const flagged = ms.filter((m) => d.metrics[m.id]?.has_data && d.metrics[m.id].status !== 'ok').length;
          return (
            <section key={cat} aria-label={cat} className={s.group}>
              <div className={s.groupHead}>
                <h3>{cat}</h3>
                <span className={cx(s.groupState, flagged ? 'st-watch' : 'st-ok')}>
                  {flagged ? `${flagged} to watch` : 'All nominal'}
                </span>
              </div>
              <ul className={s.list}>{ms.map((m) => row(m))}</ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
