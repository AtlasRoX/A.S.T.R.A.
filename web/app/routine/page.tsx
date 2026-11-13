import type { Metadata } from 'next';
import Link from 'next/link';
import { getCatalog, getDashboard } from '@/lib/engine';
import { cx } from '@/lib/format';
import { getSession } from '@/lib/session';
import type { Task } from '@/lib/types';
import s from './routine.module.css';

export const metadata: Metadata = { title: 'Routine' };

const STATE_LABEL = { done: 'Done', due: 'Due now', overdue: 'Overdue', upcoming: 'Later' } as const;
/** Status colour per task state; a later task has none, so it falls back to the neutral text colours. */
const STATE_ST = { done: 'st-ok', due: 'st-watch', overdue: 'st-act', upcoming: null } as const;

export default async function RoutinePage() {
  const { crew, env } = await getSession();
  const [catalog, d] = await Promise.all([getCatalog(), getDashboard(crew, env)]);
  const label = (id: string) => catalog.metrics.find((m) => m.id === id)?.label ?? id;
  const goal = d.game.crew_goal;
  const left = Math.max(0, goal.target - goal.done);
  // The task to do next: overdue first, then due now, then the next one still to come.
  const nextUp =
    d.routine.tasks.find((t) => t.state === 'overdue') ??
    d.routine.tasks.find((t) => t.state === 'due') ??
    d.routine.tasks.find((t) => t.state === 'upcoming') ??
    null;
  // Where "now" falls in the day: the index of the first task later than the clock (-1 = after the last).
  const nowIndex = d.routine.tasks.findIndex((t) => t.time > d.clock.time);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h-page">Today&apos;s routine</h1>
          <p>
            {d.routine.done} of {d.routine.total} checks done
            {d.routine.overdue ? `, ${d.routine.overdue} overdue` : ', nothing overdue'}. Your streak is{' '}
            {d.game.streak} days. Small, regular checks build the baseline ASTRA compares you against.
          </p>
        </div>
      </div>

      <div className={s.layout}>
        <section aria-labelledby="tl">
          <div className={s.head}>
            <h2 id="tl" className={s.h2}>
              Day {d.routine.day}
            </h2>
            <span className={s.now}>Now {d.clock.time}</span>
          </div>
          {nextUp ? (
            <div className={cx(s.nextUp, STATE_ST[nextUp.state])}>
              <div>
                <span className="overline">{nextUp.state === 'upcoming' ? 'Next up' : STATE_LABEL[nextUp.state]}</span>
                <b>
                  {nextUp.time} · {nextUp.title}
                </b>
                <small>{nextUp.metrics.map(label).join(', ')}</small>
              </div>
              <Link
                href={`/measure/${nextUp.metrics.find((m) => !nextUp.logged.includes(m)) ?? nextUp.metrics[0]}?task=${nextUp.id}`}
                className="btn btn-primary"
              >
                Start
              </Link>
            </div>
          ) : (
            <p className="faint" style={{ marginBottom: 12 }}>
              All of today&apos;s checks are done.
            </p>
          )}
          <ol className={s.timeline}>
            {d.routine.tasks.flatMap((t, i) => [
              ...(i === nowIndex ? [<NowLine key="now" time={d.clock.time} />] : []),
              <TaskRow key={t.id} t={t} label={label} />,
            ])}
            {nowIndex === -1 ? <NowLine key="now" time={d.clock.time} /> : null}
          </ol>
        </section>

        <aside className={s.side} aria-labelledby="goal">
          <h2 id="goal" className={s.h2}>
            Crew goal
          </h2>
          <p className={s.goalText}>
            {left === 0
              ? `Goal reached: ${goal.reward.toLowerCase()} is on.`
              : `${left} more crew checks today and everyone gets ${goal.reward.toLowerCase()}.`}
          </p>
          <div className={s.goalBar} role="img" aria-label={`${goal.done} of ${goal.target} crew checks`}>
            <i style={{ width: `${Math.min(100, (goal.done / goal.target) * 100)}%` }} />
          </div>
          <ul className={s.crew}>
            {goal.per_crew.map((c) => (
              <li key={c.crew_id} className={cx(c.crew_id === crew && s.me)}>
                <span>{catalog.crew.find((x) => x.id === c.crew_id)?.name ?? c.initials}</span>
                <span className={s.count}>
                  {c.done} of {c.total}
                </span>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}

/** A line across the timeline at the current mission time, so past and upcoming tasks are told apart. */
function NowLine({ time }: { time: string }) {
  return (
    <li className={s.nowLine} aria-label={`Now, ${time}`}>
      <span>{time}</span>
      <i aria-hidden />
      <em>Now</em>
    </li>
  );
}

function TaskRow({ t, label }: { t: Task; label: (id: string) => string }) {
  const next = t.metrics.find((m) => !t.logged.includes(m)) ?? t.metrics[0];
  return (
    <li className={cx(s.row, s[t.state], STATE_ST[t.state])}>
      <span className={s.time}>{t.time}</span>
      <span className={s.node} aria-hidden />
      <div className={s.body}>
        <b>
          {t.title}
          {t.weekly ? <span className={s.tag}>Weekly</span> : null}
        </b>
        <small>{t.metrics.map(label).join(', ')}</small>
      </div>
      <div className={s.end}>
        {t.state === 'done' ? (
          <span className={s.state}>Done {t.done_at}</span>
        ) : (
          <>
            <span className={s.state}>{STATE_LABEL[t.state]}</span>
            <Link href={`/measure/${next}?task=${t.id}`}
              className={cx('btn btn-sm', t.state === 'upcoming' ? 'btn-ghost' : 'btn-primary')}>
              Start
            </Link>
          </>
        )}
      </div>
    </li>
  );
}
