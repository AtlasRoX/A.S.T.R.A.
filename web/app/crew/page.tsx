import type { Metadata } from 'next';
import Link from 'next/link';
import { AttentionQueue } from '@/components/attention/AttentionQueue';
import { CommsPanel } from '@/components/crew/CommsPanel';
import s from '@/components/crew/crew.module.css';
import { ShipSense } from '@/components/crew/ShipSense';
import { CrewWatch } from '@/components/crew/CrewWatch';
import { ViewAs } from '@/components/crew/ViewAs';
import { CrewAvatar } from '@/components/ui/CrewAvatar';
import { CrewMission } from '@/components/missions/CrewMission';
import { getAttention, getCatalog, getCrewOverview, getCrewWatch, getGame } from '@/lib/engine';
import { cx } from '@/lib/format';
import { getSession } from '@/lib/session';

export const metadata: Metadata = { title: 'Crew & comms' };

const EVA = {
  go: ['ok', 'Go'],
  caution: ['watch', 'Caution'],
  nogo: ['act', 'No-go'],
} as const;
const STATUS_WORD = { ok: 'Nominal', watch: 'Watch', act: 'Act' } as const;
/** Most urgent first on the roster. */
const SEVERITY = { act: 0, watch: 1, ok: 2 } as const;

export default async function CrewPage() {
  const { crew, env } = await getSession();
  const [catalog, data, attentionData, g, watch] = await Promise.all([
    getCatalog(),
    getCrewOverview(env),
    getAttention(undefined, env),
    getGame(crew, env),
    getCrewWatch(),
  ]);
  const label = (id: string) => catalog.metrics.find((m) => m.id === id)?.short ?? id;
  const cmo = catalog.crew.find((c) => c.is_cmo);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h-page">Crew & comms</h1>
          <p>
            Every crew member at a glance, most urgent first, and the store-and-forward link to flight surgeons on
            Earth.
            {cmo ? ` ${cmo.title} ${cmo.name} is the Crew Medical Officer.` : ''}
          </p>
        </div>
      </div>

      {/* Ship Sense: a shared cause (the cabin air) behind symptoms several crew report, before separate patients */}
      <ShipSense sense={data.ship_sense} crew={catalog.crew} />

      {/* Crew Watch: the on-board agent that links symptoms to causes and writes the handover to Earth */}
      <CrewWatch initial={watch.last} />

      <ul className={s.roster} aria-label="Crew">
        {data.crew
          .toSorted((a, b) => SEVERITY[a.overall] - SEVERITY[b.overall])
          .map((r) => {
            const [evaSt, evaLabel] = EVA[r.eva.status];
            const current = r.crew.id === crew;
            const issue = r.top_insight && r.top_insight.severity !== 'ok' ? r.top_insight : null;
            const pct = r.total ? (100 * r.done) / r.total : 0;
            return (
              <li
                key={r.crew.id}
                data-crew={r.crew.id}
                className={cx(s.member, `st-${r.overall}`, current && s.current)}
              >
                <div className={s.memberHead}>
                  {/* Photo and name open the profile; the photo link is a duplicate, so it is hidden from AT. */}
                  <Link href={`/crew/${r.crew.id}`} className={s.avatarRing} tabIndex={-1} aria-hidden="true">
                    <CrewAvatar member={r.crew} size={40} />
                  </Link>
                  <Link href={`/crew/${r.crew.id}`} className={s.memberName}>
                    <b>
                      {r.crew.title} {r.crew.name}
                    </b>
                    <small>
                      {r.crew.role}
                      <span className={s.profileHint}> · Profile ›</span>
                    </small>
                  </Link>
                  <ViewAs id={r.crew.id} name={`${r.crew.title} ${r.crew.name}`} current={current} />
                </div>

                <dl className={s.memberStats}>
                  <div>
                    <dt>Overall</dt>
                    <dd className={`st-${r.overall}`}>{STATUS_WORD[r.overall]}</dd>
                  </div>
                  <div title={r.eva.reasons.join('. ')}>
                    <dt>EVA</dt>
                    <dd className={`st-${evaSt}`}>{evaLabel}</dd>
                  </div>
                  <div className={current && r.done < r.total ? s.statLink : undefined}>
                    <dt>Checks</dt>
                    <dd>
                      {current && r.done < r.total ? (
                        <Link href="/measure" aria-label={`${r.done} of ${r.total} checks done. Open Measure`}>
                          {r.done}
                          <span>/{r.total}</span>
                        </Link>
                      ) : (
                        <>
                          {r.done}
                          <span>/{r.total}</span>
                        </>
                      )}
                    </dd>
                    <span className={s.miniMeter} aria-hidden>
                      <i style={{ width: `${pct}%` }} />
                    </span>
                  </div>
                </dl>

                <div className={s.memberIssue}>
                  {issue ? (
                    <>
                      <p className={`st-${issue.severity}`}>
                        <i aria-hidden />
                        {issue.title}
                      </p>
                      {r.flags.length ? (
                        <ul className={s.flagChips} aria-label="Flagged indicators">
                          {r.flags.map((f) => (
                            <li key={f.metric} className={`st-${f.status}`}>
                              {current ? (
                                <Link
                                  href={`/trends?m=${f.metric}`}
                                  title={`${label(f.metric)}: ${f.display}. Open trend`}
                                >
                                  {label(f.metric)}
                                </Link>
                              ) : (
                                <span title={`${label(f.metric)}: ${f.display}`}>{label(f.metric)}</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </>
                  ) : (
                    <p className="st-ok">
                      <i aria-hidden />
                      Nothing flagged
                    </p>
                  )}
                </div>
              </li>
            );
          })}
      </ul>

      <div className={s.commsLayout}>
        <AttentionQueue wholeCrew initialData={attentionData} isCmo={cmo?.id === crew} currentUser={crew} />
        <div className={s.side}>
          <CommsPanel comms={data.comms} />
          <section className="card">
            <div className="card-head">
              <h2 className="h-card">Who handles what</h2>
            </div>
            <ol className={s.ladder}>
              {catalog.escalation.map((tier) => (
                <li key={tier.tier}>
                  <span className={s.tier}>{tier.tier}</span>
                  <div>
                    <b>{tier.name}</b>
                    <small>{tier.when}</small>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>

      {/* The crew's side of Honest Orbit: the mission chapter, this week's crew operation and crew rewards. */}
      <CrewMission g={g} crew={catalog.crew} />
    </div>
  );
}
