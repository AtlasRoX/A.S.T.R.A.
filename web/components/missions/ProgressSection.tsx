import Link from 'next/link';
import { Icon } from '@/components/ui/Icon';
import { Check, Flame, ShieldCheck } from '@/components/ui/icons';
import { cx } from '@/lib/format';
import type { GameHub } from '@/lib/types';
import s from './missions.module.css';

const CAL_WORD = {
  done: 'Checks done',
  eased: 'Core checks done while momentum was down',
  shielded: 'Missed, covered by a shield',
  missed: 'Missed',
  today: 'Today',
  none: 'Before your log started',
};
const LEDGER_ROWS = 8; // the rest of the XP log folds into "Show more", so it never becomes a scroll box

function LedgerRow({ e }: { e: GameHub['ledger'][number] }) {
  return (
    <li>
      <span>
        {e.reason.replace(/ \[[^\]]+\]$/, '')}
        <small>{e.at_label}</small>
      </span>
      <b>+{e.amount}</b>
    </li>
  );
}

function LevelRing({ level }: { level: GameHub['level'] }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  const pct = level.level_xp / level.xp_per_level;
  return (
    <div className={s.ring} role="img" aria-label={`Level ${level.level}, ${level.level_xp} of ${level.xp_per_level} XP to the next level`}>
      <svg width="84" height="84" viewBox="0 0 84 84" aria-hidden>
        <circle cx="42" cy="42" r={r} className={s.ringTrack} />
        <circle cx="42" cy="42" r={r} className={s.ringFill} strokeDasharray={c} strokeDashoffset={c * (1 - pct)} transform="rotate(-90 42 42)" />
      </svg>
      <span className={s.ringText}>
        <small>Level</small>
        <b>{level.level}</b>
      </span>
    </div>
  );
}

/**
 * A crew member's Honest Orbit progress, on their profile (the game lives with the person, not on a page of its
 * own): level, streak and XP today; on your own profile today's orbit with the next check and what it pays, and your
 * quests; badges with the closest ones; and, folded, the streak calendar, the XP log and how XP works.
 */
export function ProgressSection({ g, levels, isMe, firstName }: { g: GameHub; levels: string[]; isMe: boolean; firstName: string }) {
  const next = levels[g.level.level] ?? null;
  const toNext = g.level.xp_per_level - g.level.level_xp;
  const t = g.today;
  const earned = g.badges.filter((b) => b.earned);
  // The badges closest to being earned: the next goals, visible without opening the full list.
  const closest = g.badges
    .filter((b) => !b.earned && b.target > 1 && b.value > 0)
    .toSorted((a, b) => b.value / b.target - a.value / a.target)
    .slice(0, 3);
  const groups = Object.entries(g.badge_groups);

  return (
    <section id="progress" className={s.progress} aria-labelledby="progress-h">
      <div className={s.progressHead}>
        <h2 id="progress-h" className="h-card">
          Progress
        </h2>
        <span className="faint" style={{ fontSize: 13 }}>
          Honest Orbit: XP for doing the checks, never for what they show
        </span>
      </div>

      <div className={s.hero}>
        <div className={s.heroStats}>
          <div className={s.heroLevel}>
            <LevelRing level={g.level} />
            <div>
              <b className={s.heroTitle}>{g.level.title}</b>
              <span className={s.heroSub}>
                {g.level.xp.toLocaleString('en')} XP
                {next ? (
                  <>
                    {' '}
                    · {toNext} to <b>{next}</b>
                  </>
                ) : null}
              </span>
            </div>
          </div>
          <div className={s.heroStreak}>
            <Flame size={26} className={s.flame} aria-hidden />
            <div>
              <b className={s.heroTitle}>{g.streak.current}-day streak</b>
              <span className={s.heroSub}>
                Best {g.streak.best} ·{' '}
                <span className={s.shields} aria-label={`${g.streak.shields} of ${g.streak.shield_max} streak shields`}>
                  {Array.from({ length: g.streak.shield_max }, (_, i) => (
                    <ShieldCheck key={i} size={15} className={i < g.streak.shields ? s.shieldOn : s.shieldOff} aria-hidden />
                  ))}
                </span>{' '}
                {g.streak.shields} shield{g.streak.shields === 1 ? '' : 's'}
              </span>
            </div>
          </div>
          <div className={s.heroToday}>
            <b className={cx(s.heroTitle, t.xp > 0 && s.xpEarned)}>+{t.xp} XP</b>
            <span className={s.heroSub}>earned today</span>
          </div>
        </div>

        {t.total ? (
          <div className={s.orbit}>
            <div className={s.orbitHead}>
              <span className={s.nextLabel}>Today&apos;s orbit</span>
              <span className={s.orbitCount}>
                {t.done} of {t.total} checks
              </span>
              <span className={cx(s.orbitBonus, t.orbit_done && s.orbitBonusDone)}>
                {t.orbit_done ? `Full orbit done · +${t.orbit_xp} XP` : `Finish all for +${t.orbit_xp} XP`}
              </span>
            </div>
            <div
              className={s.orbitBar}
              role="progressbar"
              aria-label={isMe ? 'Checks done today' : `${firstName}'s checks done today`}
              aria-valuemin={0}
              aria-valuemax={t.total}
              aria-valuenow={t.done}
              aria-valuetext={`${t.done} of ${t.total} checks`}
            >
              <span style={{ width: `${(100 * t.done) / t.total}%` }} />
            </div>
            {/* The one thing to do next, and what it pays now: only on your own profile. */}
            {isMe && t.next ? (
              <div className={s.nextCheck}>
                <div className={s.nextBody}>
                  <span className={s.nextLabel}>{g.momentum.support ? 'Core check next' : 'Next check'}</span>
                  <b className={s.nextTitle}>
                    {t.next.title}
                    <span className={cx(s.nextTime, t.next.overdue && s.nextLate)}>
                      {t.next.time}
                      {t.next.overdue ? ' · overdue' : ''}
                    </span>
                  </b>
                  {t.next.lines.length > 1 ? (
                    <span className={s.nextLines}>
                      {t.next.lines
                        .slice(1)
                        .map((l) => `${l.reason} +${l.amount}`)
                        .join(' · ')}
                    </span>
                  ) : null}
                </div>
                <span className={s.worth}>+{t.next.worth} XP</span>
                <Link href={t.next.href} className="btn btn-primary">
                  Start
                </Link>
              </div>
            ) : isMe ? (
              <p className={s.allDone}>Every check today is done. Your streak is safe; see you tomorrow.</p>
            ) : null}
          </div>
        ) : null}
        {isMe && (g.momentum.support || g.momentum.trend === 'down') ? <p className={s.momentumNote}>{g.momentum.message}</p> : null}
      </div>

      <div className={s.progressGrid}>
        {isMe && g.quests.length ? (
          <section className="card" aria-labelledby="quest-h">
            <div className="card-head">
              <h3 id="quest-h" className="h-card">
                Your quests
              </h3>
              <span className="faint" style={{ fontSize: 13 }}>
                From your medical history
              </span>
            </div>
            <ul className={s.quests}>
              {g.quests.map((q) => (
                <li key={q.id} className={cx(s.quest, q.done && s.questDone)}>
                  <div className={s.questTop}>
                    <b>{q.title}</b>
                    <span className={s.reward}>{q.claimed ? 'Claimed' : `+${q.xp} XP`}</span>
                  </div>
                  <p>{q.reason}</p>
                  <div className={s.questFoot}>
                    <span className={s.pips} aria-label={`${q.progress} of ${q.target} days`}>
                      {Array.from({ length: q.target }, (_, i) => (
                        <i key={i} className={i < q.progress ? s.pipOn : undefined} />
                      ))}
                    </span>
                    {q.done ? (
                      <span className={s.doneWord}>
                        <Check size={14} aria-hidden /> Done this week
                      </span>
                    ) : (
                      <Link href={q.href} className="btn btn-sm btn-tonal">
                        Log it now
                      </Link>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        <section className="card" aria-labelledby="badge-h">
          <div className="card-head">
            <h3 id="badge-h" className="h-card">
              Badges
            </h3>
            <span className="faint" style={{ fontSize: 13 }}>
              {g.earned_count} of {g.badges.length}
            </span>
          </div>
          {earned.length ? (
            <ul className={s.earned} aria-label="Earned">
              {earned.map((b) => (
                <li key={b.id} title={b.description}>
                  <Icon name={b.icon} size={15} /> {b.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className={s.empty}>No badges yet. Finishing checks day after day earns the first ones.</p>
          )}
          {closest.length ? (
            <ul className={s.closest} aria-label="Closest to earning">
              {closest.map((b) => (
                <li key={b.id}>
                  <span className={s.badgeIcon}>
                    <Icon name={b.icon} size={16} />
                  </span>
                  <span className={s.badgeText}>
                    <b>{b.name}</b>
                    <small>{b.description}</small>
                    <span className={s.badgeBar} aria-label={`${b.value} of ${b.target}`}>
                      <i style={{ width: `${(100 * b.value) / b.target}%` }} />
                    </span>
                  </span>
                  <span className={s.badgeState}>
                    {b.value}/{b.target}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          <details className={s.fold}>
            <summary>All {g.badges.length} badges</summary>
            {groups.map(([gid, label]) => (
              <div key={gid} className={s.badgeGroup}>
                <h4>{label}</h4>
                <ul className={s.badges}>
                  {g.badges
                    .filter((b) => b.group === gid)
                    .map((b) => (
                      <li key={b.id} className={cx(s.badge, b.earned && s.badgeOn)}>
                        <span className={s.badgeIcon}>
                          <Icon name={b.icon} size={18} />
                        </span>
                        <span className={s.badgeText}>
                          <b>{b.name}</b>
                          <small>{b.description}</small>
                          {!b.earned && b.target > 1 ? (
                            <span className={s.badgeBar} aria-label={`${b.value} of ${b.target}`}>
                              <i style={{ width: `${(100 * b.value) / b.target}%` }} />
                            </span>
                          ) : null}
                        </span>
                        <span className={s.badgeState}>
                          {b.earned ? <Check size={16} aria-label="Earned" /> : b.target > 1 ? `${b.value}/${b.target}` : ''}
                        </span>
                      </li>
                    ))}
                </ul>
              </div>
            ))}
          </details>
        </section>
      </div>

      {/* Folded detail: open when you want it, out of the way when you do not. */}
      <div className={s.folds}>
        <details className={cx('card', s.foldCard)}>
          <summary>Streak calendar · last 4 weeks</summary>
          <ol className={s.calendar}>
            {g.streak.calendar.map((d) => {
              const label = `Day ${d.day}: ${CAL_WORD[d.status]}${d.total ? ` (${d.done} of ${d.total} checks)` : ''}`;
              return (
                <li key={d.day} className={cx(s.cell, s[`c_${d.status}`])} title={label}>
                  <span aria-hidden>{d.day}</span>
                  <span className="sr-only">{label}</span>
                  {d.status === 'shielded' ? <ShieldCheck size={12} aria-hidden /> : null}
                </li>
              );
            })}
          </ol>
          <p className={s.legend}>
            <span className={s.legendItem}>
              <i className={s.c_done} /> Done
            </span>
            <span className={s.legendItem}>
              <i className={s.c_eased} /> Core checks (eased)
            </span>
            <span className={s.legendItem}>
              <i className={s.c_shielded} /> Shield used
            </span>
            <span className={s.legendItem}>
              <i className={s.c_missed} /> Missed
            </span>
            <span className={s.legendItem}>
              <i className={s.c_today} /> Today
            </span>
          </p>
          <p className={s.note}>
            A day counts at 75% of its checks. A shield is earned every {g.streak.shield_every} streak days (max{' '}
            {g.streak.shield_max}) and covers one missed day; when momentum drops, a day also counts once the core checks
            are done.
          </p>
        </details>

        {isMe ? (
          <details className={cx('card', s.foldCard)}>
            <summary>
              XP log <span className="faint">· +{g.seed_xp.toLocaleString('en')} XP before launch</span>
            </summary>
            {g.ledger.length ? (
              <>
                <ol className={s.ledger}>
                  {g.ledger.slice(0, LEDGER_ROWS).map((e) => (
                    <LedgerRow key={e.id} e={e} />
                  ))}
                </ol>
                {g.ledger.length > LEDGER_ROWS ? (
                  <details className={s.ledgerMore}>
                    <summary>Show {g.ledger.length - LEDGER_ROWS} more</summary>
                    <ol className={s.ledger} start={LEDGER_ROWS + 1}>
                      {g.ledger.slice(LEDGER_ROWS).map((e) => (
                        <LedgerRow key={e.id} e={e} />
                      ))}
                    </ol>
                  </details>
                ) : null}
              </>
            ) : (
              <p className={s.empty}>No XP yet this mission. Your first finished check starts the log.</p>
            )}
          </details>
        ) : null}

        <details className={cx('card', s.foldCard)}>
          <summary>How XP works</summary>
          <div className={s.pledge}>
            <b>Honest Orbit</b>
            <span>XP never depends on what a reading says. Hiding a symptom can never pay.</span>
          </div>
          <table className={s.rules}>
            <tbody>
              {g.rules.map((r) => (
                <tr key={r.what} className={r.xp === '0' ? s.ruleZero : undefined}>
                  <th scope="row">{r.what}</th>
                  <td className={s.ruleXp}>{r.xp === '0' ? '0 XP' : `+${r.xp}`}</td>
                  <td>{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <details className={s.why}>
            <summary>Why it works this way</summary>
            <ul>
              <li>
                <b>Rewards follow actions, not values.</b> Pilots hide conditions to avoid being grounded; a game that paid
                for good numbers would pay crew to do the same. Rewards for completing logs raised compliance without
                changing the answers (JMIR 2019).
              </li>
              <li>
                <b>One crew, one score.</b> Competition sustained activity best in the STEP UP trial (JAMA Internal
                Medicine, 2019), but NASA treats crew conflict as a mission risk, so the crew competes with its own last
                week instead of with each other.
              </li>
              <li>
                <b>Paced to the mission.</b> Morale tends to dip in the third quarter of long isolated missions (Stuster
                2010; Bechtel &amp; Berning 1991) and activity falls over time (Mars-500, PNAS 2013). Goals ease when
                momentum drops.
              </li>
              <li>
                <b>Forgiving streaks.</b> Broken streaks make people quit and repairs soften it (Silverman &amp; Barasch,
                2023); missing one day does not stop a habit forming, which takes about 66 days (Lally et al., 2010).
              </li>
            </ul>
          </details>
        </details>
      </div>
    </section>
  );
}
