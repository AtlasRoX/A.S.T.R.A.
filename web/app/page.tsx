import { Fragment } from 'react';
import Link from 'next/link';
import { AttentionQueue, type AttentionTrend } from '@/components/attention/AttentionQueue';
import { FitSparkline } from '@/components/today/FitSparkline';
import { HealthOrbit, type OrbitSegment } from '@/components/today/HealthOrbit';
import t from '@/components/today/today.module.css';
import { BodyExplorer } from '@/components/body/BodyExplorer';
import { BodySystemsSection } from '@/components/body/BodySystemsSection';
import { Sparkline } from '@/components/charts/Sparkline';
import { StatusChip } from '@/components/ui/StatusChip';
import { ReadingSource } from '@/components/ui/ReadingSource';
import { SourceList, SourceTag } from '@/components/ui/SourceTag';
import { Check, ChevronDown, Flame, TriangleAlert } from '@/components/ui/icons';
import { getCatalog, getDashboard } from '@/lib/engine';
import { ageLabel, cx, duration, fmt, signed, STATUS_LABEL, unitFor, worst } from '@/lib/format';
import { getSession } from '@/lib/session';
import type { Cabin, Comms, Dashboard, Hazard, MetricDef, MetricState, Radiation, Status, Task } from '@/lib/types';
import s from './overview.module.css';

/** The indicators the challenge names: blood pressure, heart rate, blood sugar, temperature, sleep and mood. */
const CORE = ['bp', 'hr', 'glucose', 'temp', 'sleep', 'mood'];

const STATUS_WORD: Record<Status, string> = { ok: 'Nominal', watch: 'Watch', act: 'Act' };
const EVA = { go: ['ok', 'Go'], caution: ['watch', 'Caution'], nogo: ['act', 'No-go'] } as const;
const ORDER = { overdue: 0, due: 1, upcoming: 2, done: 3 } as const;

/** Ring order: Act, Watch, Nominal, then no reading. */
const orbitRank = (g: OrbitSegment) => (g.missing ? 3 : g.status === 'act' ? 0 : g.status === 'watch' ? 1 : 2);

export default async function OverviewPage() {
  const { crew, env } = await getSession();
  const [catalog, d] = await Promise.all([getCatalog(), getDashboard(crew, env)]);

  const metricDefs = Object.fromEntries(catalog.metrics.map((m) => [m.id, m]));
  const organStatus = Object.fromEntries(d.organs.map((o) => [o.id, o.status])) as Record<string, Status>;
  const organName = Object.fromEntries(catalog.organs.map((o) => [o.id, o.name]));
  const attentionSystems = d.organs.filter((o) => o.status !== 'ok').map((o) => organName[o.id] ?? o.id);
  const [evaSt, evaWord] = EVA[d.eva.status];

  // Overdue and due checks always make the list; the rest fill it up to five. Shown in clock order.
  const pending = d.routine.tasks
    .filter((task) => task.state !== 'done')
    .toSorted((a, b) => ORDER[a.state] - ORDER[b.state] || a.time.localeCompare(b.time))
    .slice(0, 5)
    .toSorted((a, b) => a.time.localeCompare(b.time));
  const doneToday = d.routine.tasks.filter((task) => task.state === 'done').toSorted((a, b) => a.time.localeCompare(b.time));
  // "Now" sits before the first check scheduled after the current time.
  const now = d.clock.time.slice(0, 5);
  const nextIndex = pending.findIndex((task) => task.time > now);
  const nowIndex = nextIndex === -1 ? pending.length : nextIndex;

  // One ring segment per indicator, grouped Act, Watch, Nominal, then no reading, so the proportions read at a glance.
  const orbit: OrbitSegment[] = catalog.metrics
    .filter((m) => d.metrics[m.id])
    .map((m) => ({ id: m.id, label: m.label, status: d.metrics[m.id].status, missing: !d.metrics[m.id].has_data }))
    .toSorted((a, b) => orbitRank(a) - orbitRank(b));
  const orbitCount = {
    ok: orbit.filter((g) => !g.missing && g.status === 'ok').length,
    watch: orbit.filter((g) => !g.missing && g.status === 'watch').length,
    act: orbit.filter((g) => !g.missing && g.status === 'act').length,
    missing: orbit.filter((g) => g.missing).length,
  };

  // One plain sentence about the whole picture, counted the same way as the ring.
  const watchPhrase = `${orbitCount.watch} ${orbitCount.watch === 1 ? 'indicator' : 'indicators'} to keep an eye on`;
  const summarySentence =
    orbitCount.act > 0
      ? `${orbitCount.act} ${orbitCount.act === 1 ? 'indicator needs' : 'indicators need'} action now${orbitCount.watch ? `, and ${watchPhrase}` : ''}.`
      : orbitCount.watch > 0
        ? `Nothing urgent. ${watchPhrase[0].toUpperCase()}${watchPhrase.slice(1)}.`
        : 'All health indicators are nominal.';

  // The latest value and trend of every indicator, for the sparkline in its attention row.
  const trends: Record<string, AttentionTrend> = Object.fromEntries(
    catalog.metrics
      .filter((m) => d.metrics[m.id]?.has_data)
      .map((m) => {
        const st = d.metrics[m.id];
        const trend: AttentionTrend = {
          label: m.label,
          value: st.display,
          unit: unitFor(m),
          spark: st.spark,
          band: st.band?.ok ?? null,
          status: st.status,
        };
        return [m.id, trend];
      }),
  );
  const dueCount = d.routine.tasks.filter((task) => task.state === 'due' || task.state === 'overdue').length;

  // The mission strip already shows the delay; the card only earns its place during a solar conjunction.
  const showEarthCard = Boolean(d.comms?.conjunction);

  return (
    <div className={s.page}>
      {/* 1. Readiness: every indicator on one ring, the summary, and the three numbers that gate the day */}
      <section className={cx(t.hero, `st-${d.overall}`)} aria-label="Crew status overview">
        <HealthOrbit segments={orbit} />

        <div className={t.heroText}>
          <h1 className={t.heroName}>
            {d.crew.title} {d.crew.name}{' '}
            <span>
              <span className={t.heroSep}>· </span>
              {d.crew.role}
            </span>
          </h1>
          <p className={t.heroSummary}>{summarySentence}</p>
          <ul className={t.legend} aria-label="Indicators by status">
            <li className="st-ok">
              <i aria-hidden /> {orbitCount.ok} nominal
            </li>
            {orbitCount.watch ? (
              <li className="st-watch">
                <i aria-hidden /> {orbitCount.watch} watch
              </li>
            ) : null}
            {orbitCount.act ? (
              <li className="st-act">
                <i aria-hidden /> {orbitCount.act} act
              </li>
            ) : null}
            {orbitCount.missing ? (
              <li className={t.legendMissing}>
                <i aria-hidden /> {orbitCount.missing} no reading
              </li>
            ) : null}
          </ul>
        </div>

        <dl className={t.stats}>
          <div className={cx(t.stat, `st-${d.overall}`)}>
            <dt>Overall</dt>
            <dd>{STATUS_WORD[d.overall]}</dd>
            <small>
              {/* "To watch" would undersell an Act day: then the systems simply need attention. */}
              {attentionSystems.length
                ? d.overall === 'act'
                  ? `${attentionSystems.length} ${attentionSystems.length === 1 ? 'system needs' : 'systems need'} attention`
                  : `${attentionSystems.length} ${attentionSystems.length === 1 ? 'system' : 'systems'} to watch`
                : 'All systems nominal'}
            </small>
          </div>
          <div className={cx(t.stat, dueCount ? 'st-watch' : 'st-ok')}>
            <dt>Checks today</dt>
            <dd>
              {d.routine.done}
              <span>/{d.routine.total}</span>
            </dd>
            <div className={t.meter} aria-hidden>
              <i style={{ width: `${d.routine.total ? (100 * d.routine.done) / d.routine.total : 0}%` }} />
            </div>
            {/* The streak link sits inside the caption: the three stats share grid rows, so it must not add one. */}
            <small>
              {dueCount ? `${dueCount} due now` : 'On track'}
              <Link href={`/crew/${d.crew.id}#progress`} className={t.statGame}>
                <Flame size={13} aria-hidden /> {d.game.streak}-day streak · +{d.game.xp_today} XP
              </Link>
            </small>
          </div>
          <div className={cx(t.stat, `st-${evaSt}`)} title={d.eva.reasons.join('. ')}>
            <dt>EVA</dt>
            <dd>{evaWord}</dd>
            <small>{d.eva.reasons[0] ?? 'Cleared for EVA'}</small>
          </div>
        </dl>
      </section>

      {/* 3. To do: what needs a look, and the checks that are due */}
      <div className={s.todoGrid}>
        <AttentionQueue initialData={d.attention} currentUser={crew} className={s.todoQueue} trends={trends} />

        <section className={cx(s.sectionBlock, t.checksCard)} aria-labelledby="checks-heading">
          <div className={s.blockHead}>
            <h2 id="checks-heading" className={s.h2}>
              Next checks
            </h2>
            <Link href="/routine" className={s.link}>
              Full schedule ›
            </Link>
          </div>
          {pending.length ? (
            <ol className={t.timeline}>
              {pending.map((task, i) => (
                <Fragment key={task.id}>
                  {i === nowIndex ? <NowMarker time={now} /> : null}
                  <CheckRow task={task} />
                </Fragment>
              ))}
              {nowIndex === pending.length ? <NowMarker time={now} /> : null}
            </ol>
          ) : (
            <p className="faint" style={{ margin: 0, fontSize: '0.875rem' }}>
              Every check for today is done.
            </p>
          )}
          {doneToday.length ? (
            <div className={t.doneToday}>
              <span className="overline">Done today</span>
              <ul>
                {doneToday.map((task) => (
                  <li key={task.id} title={task.done_at ? `Done at ${task.done_at}` : undefined}>
                    <Check size={13} aria-hidden />
                    <span className={t.doneTime}>{task.time}</span>
                    {task.title}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      </div>

      {/* 4. Body: the six core indicators in one row */}
      <section className={cx(s.sectionBlock, s.band)} aria-labelledby="vitals-heading">
        <div className={s.blockHead}>
          <h2 id="vitals-heading" className={s.h2}>
            Core health indicators
          </h2>
          <Link href="/measure" className={s.link}>
            All measurements ›
          </Link>
        </div>
        <ul className={s.vitalsGrid}>
          {CORE.map((id) => {
            const m = metricDefs[id];
            const st = d.metrics[id];
            return m && st ? <VitalCard key={id} m={m} st={st} /> : null;
          })}
        </ul>
      </section>

      {/* 5. Environment: radiation, cabin air and, during a conjunction, the Earth link */}
      <div className={cx(s.envGrid, s.band)}>
        <RadiationCard radiation={d.radiation} />
        {d.cabin?.available ? <CabinCard cabin={d.cabin} /> : null}
        {showEarthCard ? <EarthSummaryCard comms={d.comms} env={d.env} /> : null}
      </div>

      {/* 6. Collapsible Body Systems */}
      <BodySystemsSection
        title="Body systems"
        note={
          attentionSystems.length
            ? `${attentionSystems.length} ${attentionSystems.length === 1 ? 'system needs' : 'systems need'} attention: ${attentionSystems.join(', ')}`
            : `All ${d.organs.length} systems nominal`
        }
        statusClass={`st-${worst(d.organs.map((o) => o.status))}`}
      >
        <BodyExplorer
          organs={catalog.organs}
          organStatus={organStatus}
          systems={d.organs}
          symptoms={catalog.symptoms}
          metrics={metricDefs}
          states={d.metrics}
          hazards={catalog.hazards}
          heartRate={d.metrics.hr?.value ?? 64}
          breathRate={d.metrics.resp?.value ?? 15}
          crewName={d.crew.name}
        />
      </BodySystemsSection>

      {/* 7. Collapsible The Five Hazards */}
      <details id="five-hazards" className={s.collapsibleBlock}>
        <summary className={s.collapsibleSummary}>
          <div className={s.blockHead}>
            <h2 id="hazards" className={s.h2}>
              The five hazards, today
            </h2>
            <span className={s.blockNote}>Spaceflight hazards & monitored indicators</span>
          </div>
          <ChevronDown size={18} className={s.collapseChevron} aria-hidden />
        </summary>
        <div className={s.collapsibleContent}>
          <div style={{ marginBottom: 14 }}>
            <Link href="/learn#hazards" className={s.link}>
              How each hazard affects health in space &rsaquo;
            </Link>
          </div>
          <ul className={s.hazards}>
            {catalog.hazards.map((h) => (
              <HazardCard key={h.id} h={h} d={d} metrics={metricDefs} />
            ))}
          </ul>
        </div>
      </details>
    </div>
  );
}

/** One core indicator: latest value, status in words and colour, the trend, and a way to measure again. */
function VitalCard({ m, st }: { m: MetricDef; st: MetricState }) {
  const delta = st.delta !== null ? `${signed(st.delta, m.id === 'mood' ? 1 : m.decimals)} vs your usual` : null;
  const accessibleLabel = `${m.label}: ${st.has_data ? `${st.display} ${unitFor(m)}` : 'no data'}, ${STATUS_LABEL[st.status]}${st.stale && st.has_data ? ', stale' : ''}${st.source === 'sim' ? ', live telemetry' : ''}. Open trend`;

  return (
    <li className={cx(s.vital, `st-${st.status}`, st.stale && 'is-stale')}>
      <Link href={`/trends?m=${m.id}`} className={s.vitalMain} aria-label={accessibleLabel}>
        <div className={s.vitalTop}>
          <span className={s.vitalLabel}>
            {m.label}
          </span>
          <span className={s.vitalStatus}>
            {STATUS_LABEL[st.status]}
            {st.stale && st.has_data ? <span className="stale-word"> · stale</span> : null}
          </span>
        </div>

        <div className={s.vitalValue}>
          {st.has_data ? st.display : '–'}
          <small>{unitFor(m)}</small>
        </div>

        <FitSparkline
          className={s.vitalSpark}
          values={st.spark}
          band={st.band?.ok ?? null}
          status={st.status}
          width={132}
          height={26}
        />

        <div className={s.vitalMeta}>
          <span>
            {ageLabel(st.age_days, st.time)} <ReadingSource source={st.source} />
          </span>
          {st.stale && st.has_data ? <span>Measure again</span> : delta ? <span>{delta}</span> : null}
        </div>

        {st.active_reading ? (
          <span className={cx(s.vitalActive, `st-${st.active_reading.status}`)}>
            {st.active_reading.time} · {st.active_reading.display} {unitFor(m)} (recovery range). Re-measure at rest.
          </span>
        ) : null}
      </Link>

      <div className={s.vitalBottom}>
        <Link
          href={`/measure/${m.id}`}
          className={cx('btn btn-sm', st.status === 'ok' && !st.stale ? 'btn-ghost' : 'btn-tonal')}
          aria-label={`Measure ${m.label.toLowerCase()}`}
        >
          Measure
        </Link>
      </div>
    </li>
  );
}

/** Earth link & delay summary card for the right column. */
function EarthSummaryCard({ comms, env }: { comms: Comms; env: Dashboard['env'] }) {
  const isBlackout = comms?.conjunction?.phase === 'blackout';
  const isLive = env.delay_s < 5 && !isBlackout;
  const replyDelay = isLive ? 'Immediate (< 5s)' : `≥ ${duration(2 * env.delay_s + 90)}`;

  return (
    <section aria-labelledby="earth-summary-head" className={s.sectionBlock}>
      <div className={s.blockHead}>
        <h2 id="earth-summary-head" className={s.h2}>
          Earth link & delay
        </h2>
        <span
          className={cx(
            'chip',
            isBlackout ? 'chip-act' : isLive ? 'chip-ok' : 'chip-watch',
          )}
        >
          {isBlackout ? 'Blackout' : isLive ? 'Live link' : 'Delayed link'}
        </span>
      </div>

      <div className={s.earthMain}>
        <div className={s.earthRow}>
          <span className={s.earthLabel}>One-way light time</span>
          <span className={s.earthVal}>{isLive ? 'Live link (< 5s)' : `${duration(env.delay_s)} one way`}</span>
        </div>

        <div className={s.earthRow}>
          <span className={s.earthLabel}>Earliest round-trip reply</span>
          <span className={s.earthVal}>{replyDelay}</span>
        </div>

        {comms?.conjunction ? (
          <div className={s.conjunctionAlert}>
            <b>Solar conjunction: </b>
            {isBlackout
              ? 'Radio link blocked by the Sun. All medical decisions are handled locally on board.'
              : `Warning phase: ${comms.conjunction.days_until ?? 0} days until radio blackout window.`}
          </div>
        ) : null}

        <div style={{ marginTop: 4 }}>
          <Link href="/crew" className={s.link}>
            Crew comms & packets to Earth ›
          </Link>
        </div>
      </div>
    </section>
  );
}

/** Radiation card */
function RadiationCard({ radiation }: { radiation: Radiation }) {
  const solar = radiation.solar;
  const event = solar.status !== 'ok';
  return (
    <section aria-labelledby="radiation" className={cx(s.sectionBlock, `st-${radiation.status}`)}>
      <div className={s.blockHead}>
        <h2 id="radiation" className={s.h2}>
          Radiation
        </h2>
        <StatusChip status={radiation.status} />
      </div>
      <div className={s.rad}>
        <div className={s.radMain}>
          <span className="overline">Mission dose</span>
          <span className={s.radValue}>
            <b className="num">{fmt(radiation.mission_msv)}</b>
            <small>mSv</small>
          </span>
          <p className="faint" style={{ fontSize: 13, margin: '2px 0 6px' }}>
            {fmt(radiation.percent)}% of the {radiation.limit_msv} mSv career limit
            {radiation.margin_days !== null ? ` · about ${radiation.margin_days} days margin` : ''}.
          </p>
          <div className={s.radBar}>
            {/* The bar shows the dose grade only (engine: Watch above 60 %, Act above 85 %); a solar event has its own alert. */}
            <div
              className={cx(
                s.radTrack,
                radiation.percent > 85 ? 'st-act' : radiation.percent > 60 ? 'st-watch' : 'st-ok',
              )}
            >
              <i style={{ width: `${Math.min(100, radiation.percent)}%` }} />
            </div>
            <div className={s.radScale} aria-hidden>
              <span>0</span>
              <span>{radiation.limit_msv} mSv limit</span>
            </div>
          </div>
        </div>
        <div className={s.radFacts}>
          <div>
            <span className="overline">Dose rate</span>
            <b className="num">
              {fmt(radiation.rate_msv_day, 2)} <small>mSv/day</small>
            </b>
          </div>
          <div>
            <span className="overline">Shelter</span>
            <b style={{ fontSize: 14, fontWeight: 600 }}>{radiation.shelter}</b>
          </div>
        </div>
        <div className={s.radFoot}>
          {event ? (
            <div className={s.solarEvent} role="alert">
              <TriangleAlert size={16} />
              <div>
                {/* "… (replay of DONKI <id>)": the event in the headline, the record id underneath. */}
                <b>{solar.label.replace(/\s*\(replay of [^)]*\)\s*$/, '')}</b>
                {/replay of/.test(solar.label) && solar.event_id ? (
                  <small>Replay of DONKI {solar.event_id}</small>
                ) : null}
                {solar.shelter_label ? <span className={s.solarShelter}>{solar.shelter_label}</span> : null}
                {solar.event_remaining_label ? (
                  <span className={s.solarLeft}>Event ends in {solar.event_remaining_label}</span>
                ) : null}
              </div>
            </div>
          ) : (
            <p className={s.solarLine}>{solar.label}</p>
          )}
          {event && solar.actions.length ? (
            <ul className={s.solarActions}>
              {solar.actions.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>
          ) : null}
          <div className="row wrap" style={{ gap: 8, marginTop: 4 }}>
            <SourceTag sourceId="donki-sep" title="NASA DONKI · solar events" />
            {radiation.rate_source === 'simulator' ? (
              <ReadingSource source="sim" />
            ) : radiation.rate_source ? (
              <SourceTag
                sourceId={radiation.rate_source}
                title={radiation.rate_source === 'osdr-eda-iss' ? 'NASA OSDR · ISS dose' : 'MSL/RAD · measured dose rate'}
              />
            ) : null}
            {solar.link ? (
              <a href={solar.link} target="_blank" rel="noreferrer" className="btn btn-text btn-sm">
                Open the NASA event record
              </a>
            ) : null}
          </div>
          {radiation.rate_source === 'simulator' ? (
            <p className="faint" style={{ fontSize: 12.5, marginTop: 6 }}>
              This dose rate comes from ASTRA's live model, not from a NASA measurement.
            </p>
          ) : !radiation.rate_source ? (
            <p className="faint" style={{ fontSize: 12.5, marginTop: 6 }}>
              The dose rate is a planning estimate for this environment, not yet tied to a NASA measurement.
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}

/** Cabin air card */
function CabinCard({ cabin }: { cabin: Cabin }) {
  const status = cabin.status ?? 'ok';
  return (
    <section aria-labelledby="cabin" className={cx(s.sectionBlock, `st-${status}`)}>
      <div className={s.blockHead}>
        <h2 id="cabin" className={s.h2}>
          Cabin air
        </h2>
        <StatusChip status={status} label={cabin.status_label ?? undefined} />
      </div>
      <div className={s.cabin}>
        <div className={s.cabinMain}>
          <span className="overline">CO₂ right now (1-hour average)</span>
          <span className={s.cabinValue}>
            <b className="num">{cabin.co2_1h_mmhg?.toFixed(2) ?? '–'}</b>
            <small>{cabin.unit ?? 'mmHg'}</small>
          </span>
          <Sparkline
            values={cabin.spark ?? []}
            band={[0, cabin.act_1h_mmhg ?? 3]}
            status={status}
            width={200}
            height={32}
          />
          <span className="faint" style={{ fontSize: '0.75rem', marginTop: 4 }}>
            {cabin.spark_label ?? 'Last 7 days'}
          </span>
        </div>
        <div className={s.cabinFacts}>
          <div>
            <span className="overline">7d avg</span>
            <b className="num">
              {cabin.co2_7d_mmhg?.toFixed(2) ?? '–'} <small>{cabin.unit ?? 'mmHg'}</small>
            </b>
          </div>
          <div>
            <span className="overline">Temp</span>
            <b className="num">
              {cabin.temp_c?.toFixed(1) ?? '–'} <small>°C</small>
            </b>
          </div>
          <div>
            <span className="overline">Humidity</span>
            <b className="num">
              {cabin.rh_pct?.toFixed(0) ?? '–'} <small>%</small>
            </b>
          </div>
        </div>
        <div className={s.cabinFoot}>
          {cabin.guide ? <p className={s.cabinGuide}>{cabin.guide}</p> : null}
          <div className="row wrap" style={{ gap: 8 }}>
            {cabin.source === 'simulator' ? (
              <>
                <ReadingSource source="sim" />
                <span className="faint" style={{ fontSize: 12.5 }}>
                  CO₂ from ASTRA's live model, not NASA telemetry.
                </span>
              </>
            ) : (
              <SourceTag sourceId="osdr-eda-iss" title="NASA OSDR · ISS cabin air" />
            )}
          </div>
          <SourceList ids={cabin.sources ?? []} label="Evidence" />
        </div>
      </div>
    </section>
  );
}

/** Hazard card */
function HazardCard({ h, d, metrics }: { h: Hazard; d: Dashboard; metrics: Record<string, MetricDef> }) {
  const watched = h.metrics.filter((id) => metrics[id] && d.metrics[id]);
  const statuses = watched.filter((id) => id !== 'symptoms').map((id) => d.metrics[id].status);
  const status = worst(h.id === 'R' ? [...statuses, d.radiation.status] : statuses);

  return (
    <li className={cx(s.hazard, `st-${status}`)}>
      <div className={s.hazardHead}>
        <b>{h.name}</b>
        <span className={s.hazardStatus}>{STATUS_LABEL[status]}</span>
      </div>
      <p className={s.hazardFact}>{hazardFact(h, d)}</p>
      <p className={s.hazardRisk}>Can lead to: {h.effects.slice(0, 2).map(lower).join('; ')}.</p>
      <ul className={s.chips} aria-label={`Indicators that watch ${h.name.toLowerCase()}`}>
        {watched.map((id) => (
          <li key={id}>
            <Link href={`/trends?m=${id}`} className={cx(s.chip, `st-${d.metrics[id].status}`)}>
              <i aria-hidden />
              {metrics[id].short || metrics[id].label}
              <span className="sr-only">: {STATUS_LABEL[d.metrics[id].status]}</span>
            </Link>
          </li>
        ))}
      </ul>
    </li>
  );
}

function hazardFact(h: Hazard, d: Dashboard): string {
  switch (h.id) {
    case 'R':
      return `${fmt(d.radiation.mission_msv)} mSv this mission, ${fmt(d.radiation.percent)}% career limit.`;
    case 'I':
      return `Day ${d.clock.day} in a sealed cabin. Mood and sleep are the early warning signs.`;
    case 'D':
      return d.env.delay_s < 5
        ? 'Live link: ground medical officer can assist in real time.'
        : `Earth is ${duration(d.env.delay_s)} away one way. Handled on board.`;
    case 'G':
      return `${d.env.gravity}. Bone, muscle and heart decondition without daily exercise.`;
    default:
      return `${d.env.name}: CO₂ and dust build up in closed loops.`;
  }
}

const lower = (text: string) => (/^[A-Z][a-z]/.test(text) ? text[0].toLowerCase() + text.slice(1) : text);

function CheckRow({ task }: { task: Task }) {
  const next = task.metrics.find((m) => !task.logged.includes(m)) ?? task.metrics[0];
  const late = task.state === 'overdue';
  const due = task.state !== 'upcoming';
  return (
    <li className={cx(t.tItem, late ? 'st-act' : due ? 'st-watch' : '', due && t.tDue)}>
      <span className={t.tTime}>{task.time}</span>
      <span className={t.tDot} aria-hidden />
      <span className={t.tBody}>
        {/* "2 h" and "30 min" stay on one line with their number. */}
        <b>{task.title.replace(/(\d) (?=h\b|min\b)/g, '$1 ')}</b>
        {/* What finishing it now pays (Honest Orbit: never what the reading says), next to its state. */}
        {due || task.xp_now ? (
          <small>
            {due ? (late ? 'Overdue' : 'Due now') : null}
            {due && task.xp_now ? ' · ' : null}
            {task.xp_now ? <span className={t.tXp}>+{task.xp_now} XP</span> : null}
          </small>
        ) : null}
        {task.metrics.includes('exercise') ? (
          <small>
            <Link href="/exercise" className={t.planLink}>
              Today&apos;s session plan ›
            </Link>
          </small>
        ) : null}
      </span>
      <Link href={`/measure/${next}?task=${task.id}`} className={cx('btn btn-sm', due ? 'btn-primary' : 'btn-ghost')}>
        Start
      </Link>
    </li>
  );
}

/** Where the current time falls between the checks. */
function NowMarker({ time }: { time: string }) {
  return (
    <li className={t.tNow} aria-label={`Now, ${time}`}>
      <span className={t.tTime}>{time}</span>
      <span className={t.tNowLine} aria-hidden />
      <span className={t.tNowLabel}>Now</span>
    </li>
  );
}
