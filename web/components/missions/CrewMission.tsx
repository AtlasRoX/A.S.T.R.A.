import { CrewAvatar } from '@/components/ui/CrewAvatar';
import { Icon } from '@/components/ui/Icon';
import { Lock } from '@/components/ui/icons';
import { cx } from '@/lib/format';
import type { CrewMember, GameHub } from '@/lib/types';
import { PerkApprove } from './PerkApprove';
import s from './missions.module.css';

/**
 * The crew's side of Honest Orbit, on the Crew page: where the mission is (its chapter and the third-quarter
 * guard), this week's cooperative crew operation, and the crew rewards the Commander approves.
 */
export function CrewMission({ g, crew }: { g: GameHub; crew: CrewMember[] }) {
  const op = g.crew.operation;
  const striped = g.chapter.chapters.some((c) => c.id === 'long_middle');
  return (
    <section className={s.crewMission} aria-labelledby="mission-h">
      <div className={cx('card', s.arc)}>
        <div className="card-head">
          <h2 id="mission-h" className="h-card">
            Mission · Chapter {g.chapter.index + 1} of {g.chapter.count}: {g.chapter.name}
          </h2>
          {g.chapter.guard ? <span className="chip chip-watch">Morale guard on</span> : null}
        </div>
        <div className={s.track} aria-hidden>
          {g.chapter.chapters.map((c, i) => (
            <span key={c.id} className={cx(s.segment, i < g.chapter.index && s.segPast, i === g.chapter.index && s.segNow, c.id === 'long_middle' && s.segQ3)}>
              <i style={i === g.chapter.index ? { width: `${(100 * (g.day - c.start + 1)) / (c.end - c.start + 1)}%` } : undefined} />
              <small>{c.name}</small>
            </span>
          ))}
        </div>
        {striped ? (
          <p className={s.trackKey} aria-hidden>
            <i /> Striped: third-quarter morale guard
          </p>
        ) : null}
        <p className={s.arcText}>
          <b>
            Day {g.day} of {g.chapter.transit_days} · {g.chapter.focus}.
          </b>{' '}
          {g.chapter.detail}
        </p>
      </div>

      <div className={s.crewGrid}>
        <section className="card" aria-labelledby="op-h">
          <div className="card-head">
            <h3 id="op-h" className="h-card">
              Crew operation · week {g.crew.week}
            </h3>
            {op.boost > 1 ? <span className="chip chip-watch">×{op.boost} third-quarter boost</span> : null}
            {op.done ? <span className="chip chip-ok">Complete</span> : null}
          </div>
          <p className={s.opName}>
            <b>{op.name}</b> {op.detail}
          </p>
          <div className={s.opBar} aria-label={`${op.value} of ${op.target} ${op.unit}`}>
            <i style={{ width: `${(100 * op.value) / op.target}%` }} />
          </div>
          <p className={s.opCount}>
            <b>{op.value}</b> / {op.target} {op.unit}
            {op.boost > 1 ? ` (${op.raw} done, counted ×${op.boost})` : ''} · Days {g.crew.start_day}–{g.crew.end_day}
          </p>
          {op.per_crew.some((p) => p.value !== null) ? (
            <ul className={s.team} aria-label="Contributions">
              {op.per_crew.map((p) => {
                const member = crew.find((c) => c.id === p.crew_id);
                return (
                  <li key={p.crew_id}>
                    {member ? <CrewAvatar member={member} size={28} /> : null}
                    <span>{p.name}</span>
                    <b>{p.value}</b>
                  </li>
                );
              })}
            </ul>
          ) : null}
          <div className={s.versus}>
            <span>
              Crew vs last week
              <small>
                {g.crew.versus.days > 1
                  ? `First ${g.crew.versus.days} days of each week`
                  : g.crew.versus.days === 1
                    ? 'First day of each week'
                    : 'Starts after the first full day'}
              </small>
            </span>
            {g.crew.versus.this_week !== null ? (
              <b className={g.crew.versus.ahead ? s.ahead : s.behind}>
                {g.crew.versus.this_week}% <small>vs {g.crew.versus.last_week}%</small>
              </b>
            ) : (
              <b>–</b>
            )}
          </div>
        </section>

        <section className="card" aria-labelledby="perk-h">
          <div className="card-head">
            <h3 id="perk-h" className="h-card">
              Crew rewards
            </h3>
            <span className="faint" style={{ fontSize: 13 }}>
              {g.crew.goal_days} of 7 crew-goal days
            </span>
          </div>
          <ol className={s.perks}>
            {g.crew.perks.map((p) => (
              <li key={p.name} className={cx(s.perk, p.unlocked && s.perkOn)}>
                <span className={s.perkIcon}>{p.unlocked ? <Icon name={p.icon} size={16} /> : <Lock size={14} />}</span>
                <span className={s.perkText}>
                  <b>{p.name}</b>
                  <small>
                    {!p.unlocked
                      ? `${p.days} crew-goal days`
                      : p.approved_by
                        ? `Approved by ${crew.find((c) => c.id === p.approved_by)?.name ?? 'the Commander'}`
                        : 'Unlocked · waiting for the Commander'}
                  </small>
                </span>
                {p.unlocked && !p.approved_by && g.can_approve ? <PerkApprove week={g.crew.week} days={p.days} name={p.name} /> : null}
              </li>
            ))}
          </ol>
          <p className={s.note}>
            A crew-goal day is one where the whole crew finishes 90% of its checks. Unlocked rewards take effect once the
            Commander approves them.
          </p>
        </section>
      </div>
    </section>
  );
}
