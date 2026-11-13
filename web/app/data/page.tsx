import type { Metadata } from 'next';
import Link from 'next/link';
import { OpenOnHash } from '@/components/ui/OpenOnHash';
import { ReferenceTabs } from '@/components/ui/ReferenceTabs';
import { EngineError, getCatalog, getNasaSources } from '@/lib/engine';
import { ArrowRight, Database, Info, TriangleAlert } from '@/components/ui/icons';
import type { NasaRole } from '@/lib/types';
import s from './data.module.css';

export const metadata: Metadata = { title: 'NASA data' };

const KIND_ORDER = ['standard', 'evidence_report', 'paper', 'web'] as const;
const KIND_LABEL: Record<(typeof KIND_ORDER)[number], string> = {
  standard: 'NASA standards',
  evidence_report: 'Technical briefs and reports',
  paper: 'Peer-reviewed papers',
  web: 'NASA web pages and datasets',
};

const ROLE_LABEL: Record<NasaRole, string> = {
  threshold: 'Threshold',
  context: 'Context',
  replay: 'Replay',
  evidence: 'Evidence',
};

/** One sentence on what each source changes in the app. */
const CHANGES: Record<string, string> = {
  'horizons-mars-lt':
    'Replaces the fixed 760-second comm delay with the real Earth-Mars light time for the mission date, and adds the solar-conjunction warning.',
  'osdr-eda-iss':
    'Adds the Cabin air card on the station: real ISS CO2, temperature and humidity, and the station dose rate.',
  'osdr-i4-labs':
    'Adds the Real astronauts page, where four real Inspiration4 crew members are plotted against their own reference ranges.',
  'donki-sep':
    'Adds the Replay a real solar storm demo, which replays a recorded NASA solar particle event.',
  std3001v1: 'Backs the 600 mSv career dose limit and the vital-sign ranges.',
  std3001v2: 'Backs the 3.0 mmHg one-hour cabin CO2 limit.',
  'ochmo-tb004': 'Backs the 2.5 mmHg 7-day cabin CO2 threshold and the headache link.',
  'msl-rad': 'Sets the transit (1.84) and Mars surface (0.64) mSv/day dose rates to the values Curiosity measured.',
  'hrp-roadmap': 'Backs the five hazards, their effects and their countermeasures.',
  'slot-a':
    'Official challenge resource. Adds the HRP risk map (all 17 risks, each traced to what ASTRA does) and the facts and video on each hazard card.',
  'slot-b':
    'Official challenge resource. Puts each of the 13 ongoing HRP studies next to its on-board counterpart in ASTRA.',
  'slot-c':
    'Official challenge resource. Adds the CSA radiation context (neutrons, bubble detectors, spacewalk doses) and how space affects the body.',
};

/** What a source that is not imported yet will change, for the "Still to come" cards. */
const PENDING_CHANGE = 'Once it is added, its numbers take priority over any value ASTRA had to estimate.';

/**
 * A 404 from /nasa/sources means the engine on the other side is running code from before the
 * NASA data port existed. It looks like missing data, so say what it actually is.
 */
function StaleEngine({ detail }: { detail: string }) {
  return (
    <div className="page">
      <section className={s.hero}>
        <h1 className="h-page">NASA data</h1>
      </section>
      <div className={s.disclaimer}>
        <TriangleAlert size={18} />
        <p>
          ASTRA Core is running an older build: it answered <code>/nasa/sources</code> with{' '}
          <b>{detail}</b>. The NASA data ships with the app, so nothing is missing from your machine — the engine
          just has to be restarted to pick up the routes. Stop it and run <code>npm run dev</code> (or{' '}
          <code>npm start</code>) from the project root.
        </p>
      </div>
    </div>
  );
}

export default async function DataPage() {
  let nasa;
  let catalog;
  try {
    [nasa, catalog] = await Promise.all([getNasaSources(), getCatalog()]);
  } catch (err) {
    if (err instanceof EngineError && err.status === 404) {
      return <StaleEngine detail={err.message} />;
    }
    throw err;
  }
  const ready = nasa.sources.filter((x) => x.status === 'ready');
  const pending = nasa.sources.filter((x) => x.status !== 'ready');

  return (
    <div className="page">
      <ReferenceTabs />
      <section className={s.hero}>
        <h1 className="h-page">NASA data</h1>
        <p>
          Every threshold, dose rate and delay ASTRA shows comes from a NASA source. The data was downloaded ahead of
          time and ships with the app, so nothing here reaches the network while you are in orbit.
        </p>
        <p className={s.totals}>
          <b>{ready.length}</b> sources ready
          {nasa.counts.slots_pending > 0 ? (
            <>
              {' · '}
              <b>{nasa.counts.slots_pending}</b> official slots pending
            </>
          ) : null}
          {' · '}
          <b>{Object.keys(catalog.sources).length}</b> cited documents
        </p>
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Sources in use</h2>
        <div className={s.grid}>
          {ready.map((src) => (
            <article key={src.id} id={src.id} className={`card ${s.card}`}>
              <div className={s.head}>
                <span className={s.role}>{ROLE_LABEL[src.role]}</span>
                {src.files.length > 0 ? <span className={s.files}>{src.files.length} file(s)</span> : null}
              </div>
              <h3>{src.title}</h3>
              <p className={s.agency}>{src.agency}</p>
              <p className={s.change}>{CHANGES[src.id] ?? src.note}</p>
              {src.note && CHANGES[src.id] ? (
                <details className={s.more}>
                  <summary>How it was obtained</summary>
                  <p>{src.note}</p>
                </details>
              ) : null}
              <div className={s.meta}>
                {src.url ? (
                  <a href={src.url} target="_blank" rel="noreferrer" className={s.link}>
                    {src.url.replace(/^https?:\/\//, '').slice(0, 58)}
                  </a>
                ) : null}
                {src.fetched ? <span>Fetched {src.fetched}</span> : null}
                {src.license ? <span>{src.license}</span> : null}
              </div>
            </article>
          ))}
        </div>
      </section>

      {pending.length > 0 ? (
        <section className={s.section}>
          <h2 className={s.h2}>Still to come</h2>
          <div className={s.grid}>
            {pending.map((src) => (
              <article key={src.id} id={src.id} className={`card ${s.card} ${s.pending}`}>
                <div className={s.head}>
                  <span className={s.role}>{ROLE_LABEL[src.role]}</span>
                  {src.slot ? <span className={s.slot}>Slot {src.slot}</span> : null}
                  <span className={s.files}>Not downloaded yet</span>
                </div>
                <h3>{src.title}</h3>
                {/* src.note is the maintainers' import instructions; the crew gets what the source will change. */}
                <p className={s.change}>{CHANGES[src.id] ?? PENDING_CHANGE}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className={s.section}>
        <h2 className={s.h2}>Official challenge resources</h2>
        <div className={`card ${s.linkCard}`}>
          <Database size={20} />
          <div>
            <h3>NASA HRP and CSA resources</h3>
            <p>
              The five resources listed by the challenge, and what ASTRA does with each: a map of all 17 NASA risks, the
              ongoing HRP studies, and the Canadian Space Agency&apos;s radiation measurements.
            </p>
          </div>
          <Link href="/data/resources" className="btn btn-primary btn-sm">
            Open <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Real astronaut data</h2>
        <div className={`card ${s.linkCard}`}>
          <Database size={20} />
          <div>
            <h3>Inspiration4</h3>
            <p>
              Four real civilians flew a 3-day mission in 2021. Their blood panels, as published by NASA, plotted against
              the dataset&apos;s own reference ranges with ASTRA&apos;s rules applied as-is.
            </p>
          </div>
          <Link href="/data/inspiration4" className="btn btn-primary btn-sm">
            Open <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Cited documents</h2>
        <p className={s.sub}>
          The evidence behind each threshold. The same list appears next to every measurement in the Measure flow.
        </p>
        <OpenOnHash />
        {KIND_ORDER.map((kind, i) => {
          const docs = Object.values(catalog.sources).filter((x) => x.kind === kind);
          if (!docs.length) return null;
          return (
            <details key={kind} className={s.kindGroup} open={i === 0}>
              <summary>
                <span>{KIND_LABEL[kind]}</span>
                <span className={s.kindCount}>{docs.length}</span>
              </summary>
              <div className={s.docs}>
                {docs.map((src) => (
                  <article key={src.id} id={`doc-${src.id}`} className={s.doc}>
                    <div className={s.docHead}>
                      <span className={s.kind}>{src.kind.replace('_', ' ')}</span>
                      <span className={s.year}>{src.year}</span>
                    </div>
                    <h3>{src.title}</h3>
                    <p className={s.agency}>{src.org}</p>
                    <p className={s.change}>{src.note}</p>
                    <a href={src.url} target="_blank" rel="noreferrer" className={s.link}>
                      {src.url}
                    </a>
                  </article>
                ))}
              </div>
            </details>
          );
        })}
      </section>

      <div className={s.disclaimer}>
        <Info size={18} />
        <p>
          ASTRA is a hackathon prototype for decision support. It does not diagnose. The sources above are real NASA
          documents and datasets; the rules ASTRA applies on top of them are ours and are not flight rules.
        </p>
      </div>

      <div className={s.disclaimer}>
        <TriangleAlert size={18} />
        <p>
          Some thresholds are simplified for the demo. Where a NASA document gives a different number, the document
          wins and the catalog was changed to match. See the decision log in{' '}
          <code>docs/nasa-data-decisions.md</code> in the repository for what was changed and what is still to be
          verified.
        </p>
      </div>
    </div>
  );
}
