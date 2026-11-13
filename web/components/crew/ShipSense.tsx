import { CrewAvatar } from '@/components/ui/CrewAvatar';
import { SoundCue } from '@/components/ui/SoundCue';
import { SourceList } from '@/components/ui/SourceTag';
import { cx } from '@/lib/format';
import type { CrewMember, ShipSenseData } from '@/lib/types';
import s from './crew.module.css';

/** A thin gauge of a value against its limit (the limit sits at 80% of the track). */
function Gauge({ value, limit, label }: { value: number; limit: number; label: string }) {
  const pct = Math.min(100, (value / limit) * 80);
  return (
    <span className={s.shipGauge} role="img" aria-label={`${label}: ${value.toFixed(2)} mmHg, limit ${limit} mmHg`}>
      <i style={{ width: `${pct}%` }} />
      <b style={{ left: '80%' }} aria-hidden />
    </span>
  );
}

/**
 * Ship Sense: when two or more crew members report the same symptom, ASTRA checks the habitat before treating them as
 * separate patients. Here: headaches and the cabin CO2 (real ISS telemetry at the station). Before it fires, the card
 * shows what it is watching; when it fires, it says "it's the air, not you" and what to fix.
 */
export function ShipSense({ sense, crew }: { sense: ShipSenseData; crew: CrewMember[] }) {
  if (!sense.available || !sense.cabin) return null;
  const cab = sense.cabin;
  const fired = sense.insight;
  const aching = crew.filter((c) => sense.symptom_crew.includes(c.id));

  return (
    <section className={cx('card', s.shipSense, fired && `st-${fired.severity}`, fired && s.shipFired)} aria-labelledby="ship-h">
      {fired ? <SoundCue id={`ship:${fired.id}`} sound="insight" /> : null}
      <div className="card-head">
        <h2 id="ship-h" className="h-card">
          {fired ? fired.title : 'Ship Sense'}
        </h2>
        <span className={s.shipTag}>{fired ? 'Ship Sense · shared cause found' : 'Watching for shared causes'}</span>
      </div>

      <div className={s.shipFlow}>
        <div className={s.shipSide}>
          <span className={s.shipLabel}>Crew with a headache · last 24 h</span>
          {aching.length ? (
            <ul className={s.shipCrew}>
              {aching.map((c) => (
                <li key={c.id}>
                  <CrewAvatar member={c} size={30} />
                  <span>{c.name.split(' ')[0]}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className={s.shipNone}>None right now</p>
          )}
        </div>

        <span className={s.shipArrow} aria-hidden>
          →
        </span>

        <div className={cx(s.shipSide, `st-${cab.status}`)}>
          <span className={s.shipLabel}>
            Cabin CO₂ · <span className={s.shipStatus}>{cab.status_label}</span>
          </span>
          <div className={s.shipRow}>
            <span>1 hour</span>
            <Gauge value={cab.co2_1h_mmhg} limit={cab.act_1h_mmhg} label="One-hour average" />
            <b>{cab.co2_1h_mmhg.toFixed(2)}</b>
            <small>limit {cab.act_1h_mmhg}</small>
          </div>
          <div className={s.shipRow}>
            <span>7 days</span>
            <Gauge value={cab.co2_7d_mmhg} limit={cab.watch_7d_mmhg} label="Seven-day average" />
            <b>{cab.co2_7d_mmhg.toFixed(2)}</b>
            <small>limit {cab.watch_7d_mmhg}</small>
          </div>
        </div>
      </div>

      {fired ? (
        <>
          <p className={s.shipBody}>{fired.body}</p>
          <ul className={s.shipActions} aria-label="What to do">
            {fired.actions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </>
      ) : (
        <p className={s.shipBody}>
          When two or more crew members report the same symptom, ASTRA checks the habitat before treating them as separate
          patients. {aching.length === 1 ? 'One crew member has a headache; one more and ASTRA looks at the air.' : null}
        </p>
      )}
      <div className={s.shipFoot}>
        <span>
          {cab.source === 'osdr-eda-iss'
            ? 'Cabin data: real ISS telemetry (NASA OSDR, Rodent Research 7), replayed on the mission clock. mmHg.'
            : "Cabin data: ASTRA's live model, not NASA telemetry. mmHg."}
        </span>
        <SourceList ids={fired ? fired.sources : []} />
      </div>
    </section>
  );
}
