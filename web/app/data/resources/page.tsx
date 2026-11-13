import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { ReferenceTabs } from '@/components/ui/ReferenceTabs';
import { ExternalLink, Info } from '@/components/ui/icons';
import { getOfficial } from '@/lib/engine';
import type { CoverageLevel, OfficialRisk } from '@/lib/types';
import s from './resources.module.css';

export const metadata: Metadata = { title: 'Challenge resources' };

const LEVEL_LABEL: Record<CoverageLevel, string> = {
  monitored: 'Monitored',
  supported: 'Supported',
  partial: 'Partial',
};

/** What each official resource changed in ASTRA, in one line. */
const USED_FOR: Record<string, string> = {
  hrp_hazards: 'The facts and video on each hazard card in the Guide, and the hazard tag on every indicator.',
  hrp_risks: 'The risk map below: all 17 risks, each traced to what ASTRA measures or does about it.',
  hrp_research: 'The research table below: each ongoing study next to its on-board counterpart in ASTRA.',
  csa_radiation: 'The radiation facts below and on the radiation hazard card: neutrons, bubble detectors, spacewalk doses.',
  csa_why_science: 'The body-effects and Earth-benefit notes below, from the CSA infographic it links.',
};

function Ext({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className={s.ext}>
      {children}
      <ExternalLink size={12} aria-hidden />
    </a>
  );
}

function RiskRow({ r }: { r: OfficialRisk }) {
  return (
    <li className={s.risk}>
      <div className={s.riskHead}>
        <Ext href={r.url}>{r.title}</Ext>
        <span className={`${s.level} ${s[r.level]}`}>{LEVEL_LABEL[r.level]}</span>
      </div>
      <p className={s.riskSummary}>{r.summary}</p>
      <p className={s.how}>
        <b>ASTRA:</b> {r.how}
      </p>
      <div className={s.chips}>
        {r.hazards.map((h) => (
          <span key={h} className={s.hz} title="Hazard">
            {h}
          </span>
        ))}
        {r.metrics.map((m) => (
          <Link key={m.id} href={`/trends?m=${m.id}`} className="chip chip-neutral">
            {m.label}
          </Link>
        ))}
        {r.features.map((f) => (
          <Link key={f.label} href={f.href} className={s.feature}>
            {f.label}
          </Link>
        ))}
      </div>
    </li>
  );
}

export default async function ResourcesPage() {
  const d = await getOfficial();

  if (!d.available) {
    return (
      <div className="page">
        <ReferenceTabs />
        <h1 className="h-page">Challenge resources</h1>
        <div className={s.note}>
          <Info size={18} />
          <p>
            The official resources are not in this build (manifest slots A to C are empty), or ASTRA Core is running an
            older version. Restart ASTRA Core and reload.
          </p>
        </div>
      </div>
    );
  }

  const { coverage } = d;
  return (
    <div className="page">
      <ReferenceTabs />
      <section className={s.hero}>
        <h1 className="h-page">Challenge resources</h1>
        <p>
          The Space Apps 2026 challenge lists five resources: three from NASA&apos;s Human Research Program and two
          from the Canadian Space Agency. This page shows what ASTRA took from each one. They were read on{' '}
          {d.retrieved} and ship with the app, so this page works offline.
        </p>
        <p className={s.totals}>
          <b>{d.resources.length}</b> official resources
          {' · '}
          <b>{coverage.total}</b> HRP risks mapped
          {' · '}
          <b>{coverage.monitored}</b> monitored, <b>{coverage.supported}</b> supported, <b>{coverage.partial}</b>{' '}
          partial
          {' · '}
          <b>{d.research.studies.length}</b> ongoing studies
        </p>
        <nav className={s.toc} aria-label="On this page">
          <a href="#resources">The five resources</a>
          <a href="#risks">Risk map</a>
          <a href="#research">Ongoing research</a>
          <a href="#csa">CSA: radiation and the body</a>
        </nav>
      </section>

      <section id="resources" className={s.section}>
        <h2 className={s.h2}>The five resources</h2>
        <div className={s.grid}>
          {d.resources.map((r) => (
            <article key={r.id} className={`card ${s.card}`}>
              <div className={s.cardHead}>
                <span className={s.agency}>{r.agency}</span>
                <span className={s.slot}>Slot {r.slot}</span>
              </div>
              <h3>
                <Ext href={r.url}>{r.title}</Ext>
              </h3>
              <p className={s.muted}>{r.challenge_note}</p>
              <p className={s.used}>
                <b>Used for:</b> {USED_FOR[r.id] ?? 'Cited on this page.'}
              </p>
            </article>
          ))}
        </div>
      </section>

      <section id="risks" className={s.section}>
        <h2 className={s.h2}>HRP risk map</h2>
        <p className={s.sub}>
          Every risk on NASA&apos;s <i>Risks of Human Spaceflight</i> page, and what ASTRA does about it.{' '}
          {(Object.keys(LEVEL_LABEL) as CoverageLevel[]).map((lvl) => (
            <span key={lvl} className={s.legend}>
              <span className={`${s.level} ${s[lvl]}`}>{LEVEL_LABEL[lvl]}</span> {d.levels[lvl]}
            </span>
          ))}
        </p>
        {d.categories.map((cat) => {
          const rows = d.risks.filter((r) => r.category === cat.id);
          return (
            <div key={cat.id} className={s.category}>
              <h3 className={s.h3}>
                {cat.name} <span className={s.count}>{rows.length}</span>
              </h3>
              <ul className={s.risks}>
                {rows.map((r) => (
                  <RiskRow key={r.id} r={r} />
                ))}
              </ul>
            </div>
          );
        })}
        <p className={s.sub}>{d.compound_note}</p>
      </section>

      <section id="research" className={s.section}>
        <h2 className={s.h2}>Ongoing HRP research, and ASTRA&apos;s on-board counterpart</h2>
        <p className={s.sub}>
          The studies NASA is running now measure the same things a crew can check on board. These pages report no
          results yet, so ASTRA cites the studies and does not use any numbers from them.
        </p>
        {d.research.groups.map((g) => (
          <div key={g.id} className={s.category}>
            <h3 className={s.h3}>{g.name}</h3>
            <div className={s.table} role="table" aria-label={g.name}>
              <div className={s.tr} role="row">
                <span role="columnheader">Study</span>
                <span role="columnheader">What NASA is studying</span>
                <span role="columnheader">In ASTRA</span>
              </div>
              {d.research.studies
                .filter((st) => st.group === g.id)
                .map((st) => (
                  <div key={st.id} className={s.tr} role="row">
                    <span role="cell" className={s.study}>
                      <Ext href={st.url}>{st.name}</Ext>
                    </span>
                    <span role="cell" className={s.muted}>
                      {st.summary}
                    </span>
                    <span role="cell">
                      {st.how}
                      <span className={s.chips}>
                        {st.metrics.map((m) => (
                          <Link key={m.id} href={`/trends?m=${m.id}`} className="chip chip-neutral">
                            {m.label}
                          </Link>
                        ))}
                        {st.link ? (
                          <Link href={st.link} className={s.feature}>
                            Open
                          </Link>
                        ) : null}
                      </span>
                    </span>
                  </div>
                ))}
            </div>
          </div>
        ))}
      </section>

      <section id="csa" className={s.section}>
        <h2 className={s.h2}>Canadian Space Agency: radiation and the body</h2>
        <p className={s.sub}>
          Context for ASTRA&apos;s radiation card. These numbers are shown as the CSA states them and are not added to
          ASTRA&apos;s dose total, which already uses measured dose rates.
        </p>
        <div className={s.grid}>
          <article className={`card ${s.card}`}>
            <span className="overline">What the CSA measured</span>
            <ul className={s.list}>
              {d.csa.radiation_facts.map((f) => (
                <li key={f.text}>
                  {f.text} <Ext href={f.url}>source</Ext>
                </li>
              ))}
            </ul>
          </article>
          <article className={`card ${s.card}`}>
            <span className="overline">How Canada measures it</span>
            <ul className={s.list}>
              {d.csa.instruments.map((i) => (
                <li key={i.id}>
                  <b>
                    <Ext href={i.url}>{i.name}</Ext>
                  </b>{' '}
                  <span className={s.years}>{i.years}</span>. {i.what}
                </li>
              ))}
            </ul>
          </article>
          <article className={`card ${s.card}`}>
            <span className="overline">How space affects the body</span>
            <ul className={s.list}>
              {d.csa.body_effects.map((e) => (
                <li key={e.system}>
                  <b>{e.system}:</b> {e.text}
                </li>
              ))}
            </ul>
            <Ext href={d.csa.body_effects_url}>CSA infographic</Ext>
          </article>
          <article className={`card ${s.card}`}>
            <span className="overline">Why it matters on Earth too</span>
            <ul className={s.list}>
              {d.csa.earth_benefits.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </article>
        </div>
      </section>

      <div className={s.note}>
        <Info size={18} />
        <p>
          Listed on the challenge&apos;s{' '}
          <a href={d.listed_on} target="_blank" rel="noreferrer">
            Resources tab
          </a>
          . NASA does not endorse any non-U.S. Government entity; the Canadian Space Agency pages are cited and linked,
          not copied. The coverage levels are ASTRA&apos;s own assessment, not NASA&apos;s.
        </p>
      </div>
    </div>
  );
}
