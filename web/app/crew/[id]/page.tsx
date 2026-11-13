import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import s from '@/components/crew/profile.module.css';
import { ViewAs } from '@/components/crew/ViewAs';
import { CrewAvatar } from '@/components/ui/CrewAvatar';
import { Icon } from '@/components/ui/Icon';
import { ChevronLeft } from '@/components/ui/icons';
import { ProgressSection } from '@/components/missions/ProgressSection';
import { EngineError, getCatalog, getDashboard, getGame, getProfile } from '@/lib/engine';
import { cx, unitFor } from '@/lib/format';
import { getSession } from '@/lib/session';
import type { HistoryItem, MetricState, Status } from '@/lib/types';

const STATUS_WORD: Record<Status, string> = { ok: 'Nominal', watch: 'Watch', act: 'Act' };
const EVA = { go: ['ok', 'Go'], caution: ['watch', 'Caution'], nogo: ['act', 'No-go'] } as const;
const HISTORY_WORD: Record<HistoryItem['status'], string> = {
  resolved: 'Resolved',
  managed: 'Managed',
  monitoring: 'Monitoring',
};
const RANK: Record<Status, number> = { act: 0, watch: 1, ok: 2 };

async function load(id: string) {
  try {
    return await getProfile(id);
  } catch (e) {
    if (e instanceof EngineError && e.status === 404) return null;
    throw e;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const p = await load((await params).id);
  return { title: p ? `${p.crew.title} ${p.crew.name}` : 'Crew member' };
}

export default async function CrewProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const [{ id }, { crew: viewer, env }] = await Promise.all([params, getSession()]);
  const profile = await load(id);
  if (!profile) notFound();
  const [catalog, d, g] = await Promise.all([getCatalog(), getDashboard(id, env), getGame(id, env)]);
  const c = profile.crew;
  const isMe = viewer === id;
  const metricLabel = (m: string) => catalog.metrics.find((x) => x.id === m)?.label ?? m;
  /** A reading with its unit, e.g. "75.5 kg"; vision and symptoms have none. */
  const withUnit = (m: string, display: string) => {
    const def = catalog.metrics.find((x) => x.id === m);
    const u = def ? unitFor(def) : '';
    return u ? `${display} ${u}` : display;
  };

  // Each past condition, with today's readings for the indicators it affects. Active ones (Watch/Act now) first.
  const links = profile.history
    .map((h) => {
      const now = h.watch
        .map((m) => ({ id: m, st: d.metrics[m] as MetricState | undefined }))
        .filter((x): x is { id: string; st: MetricState } => Boolean(x.st?.has_data));
      const worst = now.reduce<Status>((w, x) => (RANK[x.st.status] < RANK[w] ? x.st.status : w), 'ok');
      return { h, now, worst };
    })
    .toSorted((a, b) => RANK[a.worst] - RANK[b.worst]);
  const active = links.filter((l) => l.worst !== 'ok').length;

  const [evaSt, evaLabel] = EVA[d.eva.status];
  const mass = d.metrics.mass;

  return (
    <div className="page">
      <Link href="/crew" className={s.back}>
        <ChevronLeft size={16} aria-hidden /> Crew
      </Link>

      {/* Who they are */}
      <header className={cx(s.hero, `st-${d.overall}`)}>
        <span className={s.heroAvatar}>
          <CrewAvatar member={c} size={88} />
        </span>
        <div className={s.heroText}>
          <h1 className="h-page">
            {c.title} {c.name}
          </h1>
          <p className={s.heroRole}>
            {c.role}
            {c.is_cmo ? ' · Medical lead for the crew' : ''}
          </p>
          <p className={s.heroMeta}>
            {profile.age} years · {profile.nationality} · Blood type {profile.blood_type}
          </p>
          <p className={s.heroBg}>{profile.background}</p>
        </div>
        <div className={s.heroSide}>
          <dl className={s.heroStatus}>
            <div>
              <dt>Overall</dt>
              <dd className={`st-${d.overall}`}>{STATUS_WORD[d.overall]}</dd>
            </div>
            <div title={d.eva.reasons.join('. ')}>
              <dt>EVA</dt>
              <dd className={`st-${evaSt}`}>{evaLabel}</dd>
            </div>
          </dl>
          <ViewAs id={c.id} name={`${c.title} ${c.name}`} current={isMe} variant="block" className={s.viewAs} />
        </div>
      </header>

      {/* Body and career at a glance */}
      <dl className={s.facts}>
        <div>
          <dt>Height</dt>
          <dd>{profile.height_cm} cm</dd>
        </div>
        <div>
          <dt>Body mass</dt>
          <dd>{mass?.has_data ? withUnit('mass', mass.display) : `${c.mass_ref} kg`}</dd>
          <small>Pre-flight {c.mass_ref} kg</small>
        </div>
        <div>
          <dt>Days in space</dt>
          <dd>{profile.career.days_in_space}</dd>
          <small>{profile.missions.length ? `${profile.missions.length + 1} missions` : 'First mission'}</small>
        </div>
        <div>
          <dt>Spacewalks</dt>
          <dd>{profile.career.evas}</dd>
          <small>{profile.career.eva_hours ? `${profile.career.eva_hours} h total` : 'None yet'}</small>
        </div>
        <div className={`st-${d.radiation.status}`}>
          <dt>Career radiation</dt>
          <dd className={s.stValue}>{Math.round(d.radiation.career_msv)} mSv</dd>
          <small>{d.radiation.percent}% of the {d.radiation.limit_msv} mSv limit</small>
        </div>
      </dl>

      {/* The point of the page: how their history shows up today */}
      <section className="card" aria-labelledby="links-h">
        <div className="card-head">
          <h2 id="links-h" className="h-card">
            How their history affects today
          </h2>
          {active ? (
            <span className="chip chip-watch chip-dot">
              {active} showing in today&apos;s readings
            </span>
          ) : (
            <span className="chip chip-ok chip-dot">Nothing showing today</span>
          )}
        </div>
        <ul className={s.links}>
          {links.map(({ h, now, worst }) => (
            <li key={h.condition} className={cx(s.link, `st-${worst}`, worst !== 'ok' && s.linkActive)}>
              <div className={s.linkHead}>
                <b>{h.condition}</b>
                <span className={s.linkMeta}>
                  {h.year} · {HISTORY_WORD[h.status]}
                </span>
              </div>
              <p className={s.linkWhy}>{h.influence}</p>
              <ul className={s.linkNow} aria-label="Today's readings">
                {h.watch.map((m) => {
                  const st = now.find((x) => x.id === m)?.st;
                  const body = (
                    <>
                      <Icon name={m} size={14} />
                      <span>{metricLabel(m)}</span>
                      <b>{st ? withUnit(m, st.display) : 'No reading'}</b>
                    </>
                  );
                  return (
                    <li key={m} className={cx(s.reading, st ? `st-${st.status}` : s.noData)}>
                      {isMe ? (
                        <Link href={`/trends?m=${m}`} title={`${metricLabel(m)}: open trend`}>
                          {body}
                        </Link>
                      ) : (
                        <span title={st ? `${metricLabel(m)}: ${STATUS_WORD[st.status]}` : undefined}>{body}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>
      </section>

      <div className={s.gridWrap}>
      <div className={s.grid}>
        <section className="card" aria-labelledby="meds-h">
          <div className="card-head">
            <h2 id="meds-h" className="h-card">
              Allergies & medication
            </h2>
          </div>
          <dl className={s.kv}>
            <dt>Allergies</dt>
            <dd>
              {profile.allergies.length ? (
                profile.allergies.map((a) => (
                  <span key={a} className="chip chip-act">
                    {a}
                  </span>
                ))
              ) : (
                <span className="faint">None known</span>
              )}
            </dd>
            <dt>Medication</dt>
            <dd>
              {profile.medications.length ? (
                profile.medications.map((m) => (
                  <span key={m} className={s.med}>
                    {m}
                  </span>
                ))
              ) : (
                <span className="faint">None</span>
              )}
            </dd>
          </dl>
        </section>

        <section className="card" aria-labelledby="ex-h">
          <div className="card-head">
            <h2 id="ex-h" className="h-card">
              Exercise
            </h2>
          </div>
          <p className="faint" style={{ margin: '0 0 12px', fontSize: 13.5 }}>
            Two hours a day, adjusted for this history and today&apos;s readings.
          </p>
          <Link href={`/exercise?crew=${c.id}`} className="btn btn-ghost btn-sm">
            Open {c.name.split(' ')[0]}&apos;s plan ›
          </Link>
        </section>

        <section className="card" aria-labelledby="missions-h">
          <div className="card-head">
            <h2 id="missions-h" className="h-card">
              Missions
            </h2>
          </div>
          <ol className={s.missions}>
            <li className={s.current}>
              <b>Current mission</b>
              <span>
                Day {d.clock.day} · {d.env.name}
              </span>
            </li>
            {profile.missions.toReversed().map((m) => (
              <li key={m.name}>
                <b>{m.name}</b>
                <span>
                  {m.year} · {m.days} days
                </span>
              </li>
            ))}
          </ol>
        </section>

      </div>
      </div>

      {/* Honest Orbit lives with the person: level, streak, today's orbit, quests, badges and the XP log. */}
      <ProgressSection g={g} levels={catalog.levels} isMe={isMe} firstName={c.name.split(' ')[0]} />
    </div>
  );
}
