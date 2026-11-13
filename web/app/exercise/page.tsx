import type { Metadata } from 'next';
import Link from 'next/link';
import { AstroFigure } from '@/components/exercise/AstroFigure';
import s from '@/components/exercise/exercise.module.css';
import { VideoButton } from '@/components/exercise/VideoButton';
import { WeekList } from '@/components/exercise/WeekList';
import { CrewAvatar } from '@/components/ui/CrewAvatar';
import { Activity, Bike, Dumbbell, type LucideIcon, Moon, Stethoscope, Zap } from '@/components/ui/icons';
import { getCatalog, getExercise } from '@/lib/engine';
import { cx } from '@/lib/format';
import { getSession } from '@/lib/session';
import type { SessionItem, SessionKind } from '@/lib/types';

export const metadata: Metadata = { title: 'Exercise' };

const KIND_ICON: Record<SessionKind, LucideIcon> = {
  resistance: Dumbbell,
  intervals: Zap,
  continuous: Bike,
  rest: Moon,
  light: Moon,
};
const ROLE: Record<SessionItem['role'], string> = { 'warm-up': 'Warm-up', main: 'Main', second: 'Second part' };

function dose(it: SessionItem) {
  const parts = [];
  if (it.sets && it.reps) parts.push(`${it.sets} × ${it.reps}`);
  else if (it.sets) parts.push(`${it.sets} rounds`);
  parts.push(it.intensity);
  return parts.join(' · ');
}

export default async function ExercisePage({ searchParams }: { searchParams: Promise<{ crew?: string }> }) {
  const [{ crew: asked }, { crew: viewer, env }] = await Promise.all([searchParams, getSession()]);
  const catalog = await getCatalog();
  const member = catalog.crew.find((c) => c.id === asked) ?? catalog.crew.find((c) => c.id === viewer)!;
  const isMe = member.id === viewer;
  const plan = await getExercise(member.id, env);
  const envName = catalog.environments.find((e) => e.id === plan.env)?.name ?? plan.env;
  const today = plan.today;
  const TodayIcon = KIND_ICON[today.kind];
  const maxWeek = Math.max(120, ...plan.week.map((w) => Math.max(w.planned_min, w.done_min ?? 0)));

  return (
    <div className={cx('page', s.wrap)}>
      <div className="page-head">
        <div>
          <h1 className="h-page">Exercise</h1>
          <p>
            Two hours a day keeps bones and muscles from wasting in low gravity. The plan changes with your medical
            history and today&apos;s readings.
          </p>
        </div>
        {!isMe ? (
          <Link href={`/crew/${member.id}`} className={s.whose}>
            <CrewAvatar member={member} size={28} />
            <span>
              Plan for <b>{member.name}</b>
            </span>
          </Link>
        ) : null}
      </div>

      {/* The week at a glance */}
      <section className={cx('card', s.weekCard)} aria-labelledby="week-h">
        <div className="card-head">
          <h2 id="week-h" className="h-card">
            This week
          </h2>
          <span className="faint" style={{ fontSize: 13 }}>
            3 strength · 3 cardio · 1 rest, as in NASA&apos;s SPRINT study
          </span>
        </div>
        <WeekList>
          {plan.week.map((w) => {
            const Icon = KIND_ICON[w.kind];
            const done = w.done_min ?? 0;
            const met = done >= w.planned_min;
            return (
              <li
                key={w.day}
                className={cx(s.weekDay, w.today && s.weekToday, w.past && s.weekPast)}
                aria-current={w.today ? 'date' : undefined}
              >
                <span className={s.weekName}>
                  {w.weekday}
                  <small>Day {w.day}</small>
                </span>
                <span className={cx(s.weekKind, s[`k_${w.kind}`])}>
                  <Icon size={15} aria-hidden />
                  {w.title}
                  {w.adjusted ? <i className={s.adjDot} title="Changed for today" aria-label="changed for today" /> : null}
                </span>
                <span className={s.weekBar} aria-hidden>
                  <i className={s.weekPlan} style={{ width: `${(100 * w.planned_min) / maxWeek}%` }} />
                  {w.done_min !== null ? (
                    <i className={cx(s.weekDone, met && s.weekMet)} style={{ width: `${(100 * Math.min(done, maxWeek)) / maxWeek}%` }} />
                  ) : null}
                </span>
                <span className={s.weekMin}>
                  {w.done_min !== null ? (
                    <>
                      <b>{Math.round(done)}</b> / {w.planned_min} min
                    </>
                  ) : w.past ? (
                    <span className="faint">Not logged</span>
                  ) : (
                    <>{w.planned_min} min planned</>
                  )}
                </span>
              </li>
            );
          })}
        </WeekList>
      </section>

      <div className={s.layout}>
        <div className={s.main}>
          {/* Today */}
          <section aria-labelledby="today-h">
            <div className={s.todayHead}>
              <span className={cx(s.todayIcon, s[`k_${today.kind}`])}>
                <TodayIcon size={22} aria-hidden />
              </span>
              <div>
                <h2 id="today-h" className={s.todayTitle}>
                  Today: {today.title}
                </h2>
                <p className={s.todayMeta}>
                  {plan.time} · {today.minutes} min of exercise
                  {today.block_min > today.minutes ? ` in the ${today.block_min / 60} h block, with setup and cool-down` : ''} ·{' '}
                  {envName}
                </p>
              </div>
              {isMe ? (
                <Link href="/measure/exercise" className="btn btn-primary">
                  Log minutes
                </Link>
              ) : null}
            </div>

            <ol className={s.session}>
              {today.items.map((it, i) => {
                const ex = plan.exercises[it.id];
                const dev = plan.devices[it.device];
                if (it.role === 'warm-up') {
                  return (
                    <li key={`${it.id}-${it.role}`} className={s.warmRow}>
                      <span className={s.exStep}>{i + 1}</span>
                      <span>
                        <b>Warm-up</b> · {it.intensity} on the {dev?.name ?? it.device}
                      </span>
                      <span className={s.exMin}>{it.minutes} min</span>
                    </li>
                  );
                }
                return (
                  <li key={`${it.id}-${it.role}`} className={s.exCard}>
                    <AstroFigure anim={ex.anim} label={ex.name} />
                    <div className={s.exBody}>
                      <div className={s.exTop}>
                        <span className={s.exStep}>{i + 1}</span>
                        <h3 className={s.exName}>{ex.name}</h3>
                        <span className={s.exRole}>{ROLE[it.role]}</span>
                        <span className={s.exMin}>{it.minutes} min</span>
                      </div>
                      <p className={s.exDose}>{dose(it)}</p>
                      <p className={s.exDevice} title={dev?.note}>
                        On the <b>{dev?.name ?? it.device}</b>
                        {dev && dev.full !== dev.name ? <span className="faint"> ({dev.full})</span> : null}
                      </p>
                      <ol className={s.cues}>
                        {ex.cues.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ol>
                      <p className={s.exWhy}>{ex.why}</p>
                      <div className={s.exFoot}>
                        <ul className={s.targets} aria-label="Works">
                          {ex.targets.map((t) => (
                            <li key={t}>{t}</li>
                          ))}
                        </ul>
                        {ex.video ? <VideoButton video={ex.video} /> : null}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
          <p className={s.source}>{plan.source}</p>
        </div>

        <aside className={s.side}>
          {/* Why today's plan looks the way it does */}
          <section className="card" aria-labelledby="adj-h">
            <div className="card-head">
              <h2 id="adj-h" className="h-card">
                Adjusted for {isMe ? 'you' : member.name.split(' ')[0]}
              </h2>
            </div>
            {plan.adjustments.length ? (
              <ul className={s.adjList}>
                {plan.adjustments.map((a) => {
                  const fromReading = a.source === "Today's reading";
                  const Icon = fromReading ? Activity : Stethoscope;
                  return (
                    <li key={a.title} className={cx(s.adj, `st-${a.severity}`)}>
                      <span className={s.adjIcon} aria-hidden>
                        <Icon size={16} />
                      </span>
                      <div>
                        <b>{a.title}</b>
                        <p>{a.reason}</p>
                        <span className={s.adjSource}>
                          {fromReading ? "From today's reading" : 'From medical history'}
                          {a.metric && isMe ? (
                            <>
                              {' · '}
                              <Link href={`/trends?m=${a.metric}`}>See trend</Link>
                            </>
                          ) : null}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="faint" style={{ margin: 0, fontSize: 14 }}>
                No changes today: the standard plan fits.
              </p>
            )}
          </section>

          <section className="card" aria-labelledby="dev-h">
            <div className="card-head">
              <h2 id="dev-h" className="h-card">
                Hardware here
              </h2>
            </div>
            <dl className={s.devices}>
              {Object.entries(plan.devices).map(([id, d]) => (
                <div key={id}>
                  <dt>{d.full}</dt>
                  <dd>{d.note}</dd>
                </div>
              ))}
            </dl>
          </section>
        </aside>
      </div>
    </div>
  );
}
