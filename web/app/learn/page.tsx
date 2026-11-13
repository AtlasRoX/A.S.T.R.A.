import type { Metadata } from 'next';
import Link from 'next/link';
import { Icon } from '@/components/ui/Icon';
import { ArrowRight, ChevronDown, ExternalLink, Info } from '@/components/ui/icons';
import { StatusChip } from '@/components/ui/StatusChip';
import { SourceList } from '@/components/ui/SourceTag';
import { ReferenceTabs } from '@/components/ui/ReferenceTabs';
import { getCatalog, getOfficial } from '@/lib/engine';
import { duration, unitFor } from '@/lib/format';
import type { MetricDef, OfficialHazard, SourceKind } from '@/lib/types';
import s from './learn.module.css';

export const metadata: Metadata = { title: 'Health library' };

const SOURCE_KINDS: SourceKind[] = ['standard', 'evidence_report', 'paper', 'web'];

const KIND_LABEL: Record<SourceKind, string> = {
  standard: 'NASA standards',
  evidence_report: 'Technical briefs and reports',
  paper: 'Peer-reviewed papers',
  web: 'NASA web pages and datasets',
};

function rangeText(m: MetricDef) {
  if (m.id === 'bp' && m.ok2) return `${m.ok[0]}–${m.ok[1]} / ${m.ok2[0]}–${m.ok2[1]} mmHg`;
  if (m.rule === 'relative') return `within ±${m.ok[1]}% of your reference`;
  if (m.id === 'vision') return 'no distortion';
  if (m.id === 'symptoms') return 'none';
  return `${m.ok[0]}–${m.ok[1]} ${unitFor(m)}`;
}

export default async function LearnPage() {
  const c = await getCatalog();
  // The official challenge resources (NASA HRP hazard pages). Optional: an older engine has no route for them.
  const official = await getOfficial().catch(() => null);
  const hazardPage = new Map<string, OfficialHazard>(
    official?.available ? official.hazards.map((h) => [h.id, h] as const) : [],
  );
  const metricLabel = (id: string) => c.metrics.find((m) => m.id === id)?.label ?? id;
  return (
    <div className="page">
      <ReferenceTabs />
      <section className={s.hero}>
        <h1 className="h-page">Health library</h1>
        <p>
          Plain-language explanations of what ASTRA measures, why it matters on a long mission, how spaceflight
          changes it, and when to ask for help.
        </p>
        <nav className={s.toc} aria-label="On this page">
          <a href="#questions">Five key questions</a>
          <a href="#hazards">Five hazards</a>
          <a href="#systems">Body systems</a>
          <a href="#indicators">Indicators</a>
          <a href="#escalation">When to escalate</a>
          <a href="#environments">Environments</a>
          <a href="#sources">Sources</a>
        </nav>
      </section>

      <section id="questions" className={s.section}>
        <h2 className={s.h2}>Five key questions</h2>
        <div className={s.faq}>
          {c.faq.map((f, i) => (
            <details key={f.id} className={s.qa} open={i === 0}>
              <summary>
                <span className={s.qn}>{i + 1}</span>
                {f.q}
                <ChevronDown size={18} className={s.chev} />
              </summary>
              <ul>
                {f.a.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      </section>

      <section id="hazards" className={s.section}>
        <h2 className={s.h2}>The five hazards of human spaceflight</h2>
        <p className={s.sub}>
          NASA&apos;s Human Research Program groups spaceflight risks into five hazards, often remembered as{' '}
          <b>RIDGE</b>. Every indicator in ASTRA is tagged with the hazards that affect it.
        </p>
        <div className={s.hazards}>
          {c.hazards.map((h) => (
            <article key={h.id} className="card">
              <div className={s.hazardHead}>
                <span className={s.letter}>{h.id}</span>
                <h3>{h.name}</h3>
              </div>
              <p className="muted" style={{ fontSize: 14 }}>{h.summary}</p>
              <span className="overline" style={{ display: 'block', margin: '14px 0 6px' }}>What it can do</span>
              <ul className={s.list}>
                {h.effects.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
              <span className="overline" style={{ display: 'block', margin: '14px 0 6px' }}>How ASTRA helps</span>
              <ul className={s.list}>
                {h.countermeasures.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
              {hazardPage.has(h.id) ? (
                <>
                  <span className="overline" style={{ display: 'block', margin: '14px 0 6px' }}>
                    From NASA&apos;s official hazard page
                  </span>
                  <ul className={s.list}>
                    {hazardPage.get(h.id)!.facts.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                  <p className={s.hazardLinks}>
                    <a href={hazardPage.get(h.id)!.url} target="_blank" rel="noreferrer">
                      Read the page <ExternalLink size={12} aria-hidden />
                    </a>
                    <a href={hazardPage.get(h.id)!.video} target="_blank" rel="noreferrer">
                      Watch NASA&apos;s video <ExternalLink size={12} aria-hidden />
                    </a>
                  </p>
                </>
              ) : null}
              <div className={s.chips}>
                {h.metrics.map((m) => (
                  <Link key={m} href={`/trends?m=${m}`} className="chip chip-neutral">
                    {metricLabel(m)}
                  </Link>
                ))}
              </div>
              <div className={s.sources}>
                <SourceList ids={h.sources} label="Evidence" />
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="systems" className={s.section}>
        <h2 className={s.h2}>Body systems</h2>
        <div className={s.systems}>
          {c.organs.map((o) => (
            <article key={o.id} id={`organ-${o.id}`} className="card">
              <div className={s.hazardHead}>
                <span className={s.organIcon}>
                  <Icon name={o.id} size={20} />
                </span>
                <h3>{o.name}</h3>
              </div>
              <p style={{ fontSize: 14.5 }}>{o.function}</p>
              <p className={s.space}>{o.space}</p>
              <div className={s.chips}>
                {o.hazards.map((h) => {
                  const name = c.hazards.find((x) => x.id === h)?.name ?? h;
                  return (
                    <span key={h} className="hz" role="img" aria-label={`Hazard: ${name}`} title={name}>
                      {h}
                    </span>
                  );
                })}
                {o.metrics.map((m) => (
                  <Link key={m} href={`/trends?m=${m}`} className="chip chip-neutral">
                    {metricLabel(m)}
                  </Link>
                ))}
              </div>
              <div className={s.sources}>
                <SourceList ids={o.sources} label="Evidence" />
              </div>
            </article>
          ))}
        </div>
      </section>

      <section id="indicators" className={s.section}>
        <h2 className={s.h2}>Indicators</h2>
        <p className={s.sub}>Open an indicator for how to measure it, what the colours mean and when to escalate.</p>
        <div className={s.indicators}>
          {c.metrics.map((m) => (
            <details key={m.id} id={`metric-${m.id}`} className={s.ind}>
              <summary>
                <span className={s.organIcon}>
                  <Icon name={m.id} size={18} />
                </span>
                <span className={s.indTitle}>
                  <b>{m.label}</b>
                  <small>
                    Normal: {rangeText(m)} · {m.device}
                  </small>
                </span>
                <ChevronDown size={18} className={s.chev} />
              </summary>
              <div className={s.indBody}>
                <div>
                  <span className="overline">How to measure</span>
                  <ol>
                    {m.how.map((h) => (
                      <li key={h}>{h}</li>
                    ))}
                  </ol>
                  <span className="overline">Why it matters</span>
                  <p>{m.why}</p>
                  <span className="overline">In space</span>
                  <p>{m.space}</p>
                </div>
                <div>
                  <span className="overline">What the colours mean</span>
                  <div className={s.guides}>
                    {(['ok', 'watch', 'act'] as const).map((k) => (
                      <div key={k}>
                        <StatusChip status={k} />
                        <p>{m.guide[k]}</p>
                      </div>
                    ))}
                  </div>
                  <span className="overline">When to escalate</span>
                  <p>{m.escalate}</p>
                  <span className="overline">Prevention</span>
                  <div className={s.chips}>
                    {m.prevent.map((p) => (
                      <span key={p} className="chip chip-ok">{p}</span>
                    ))}
                  </div>
                  <div className={s.sources}>
                    <SourceList ids={m.sources} label="Evidence" />
                  </div>
                  <Link href={`/measure/${m.id}`} className="btn btn-primary btn-sm" style={{ marginTop: 14 }}>
                    Measure {m.label.toLowerCase()} <ArrowRight size={14} />
                  </Link>
                </div>
              </div>
            </details>
          ))}
        </div>
      </section>

      <section id="escalation" className={s.section}>
        <h2 className={s.h2}>When does a result need help?</h2>
        <div className={s.ladder}>
          {c.escalation.map((t) => (
            <article key={t.tier} className={`card st-${['ok', 'watch', 'act'][t.tier]}`}>
              <span className={s.tier}>Tier {t.tier}</span>
              <h3>{t.name}</h3>
              <small className="faint">{t.who}</small>
              <p><b>When:</b> {t.when}</p>
              <p><b>What happens:</b> {t.action}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="environments" className={s.section}>
        <h2 className={s.h2}>Environments compared</h2>
        <div className={`card ${s.tableCard}`}>
          <table className={s.table}>
            <thead>
              <tr>
                <th>Environment</th>
                <th>Gravity</th>
                <th>Signal delay</th>
                <th>Radiation</th>
                <th>Evacuation</th>
                <th>Main risks</th>
              </tr>
            </thead>
            <tbody>
              {c.environments.map((e) => (
                <tr key={e.id}>
                  <td>
                    <b>{e.name}</b>
                    <small>{e.kind} · {e.location}</small>
                  </td>
                  <td data-label="Gravity" className="num">{e.gravity.split(' ·')[0]}</td>
                  <td data-label="Signal delay" className="num">{e.delay_s < 5 ? 'Live' : duration(e.delay_s)}</td>
                  <td data-label="Radiation" className="num">{e.radiation_msv_day} mSv/day{e.radiation_source ? '' : ' (est.)'}</td>
                  <td data-label="Evacuation">{e.evacuation}</td>
                  <td data-label="Main risks">{e.risks.join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section id="sources" className={s.section}>
        <h2 className={s.h2}>Where the evidence comes from</h2>
        <p className={s.sub}>
          Every threshold, range and countermeasure above is traceable to a NASA document. Open any one to read it.
        </p>
        {SOURCE_KINDS.map((kind) => {
          const docs = Object.values(c.sources).filter((d) => d.kind === kind);
          if (!docs.length) return null;
          return (
            <div key={kind} className={s.srcGroup}>
              <span className="overline">{KIND_LABEL[kind]}</span>
              <ul className={s.srcList}>
                {docs.map((d) => (
                  <li key={d.id}>
                    <a href={d.url} target="_blank" rel="noreferrer">
                      {/* The last word and the new-tab icon share one unbreakable span, so the icon never wraps alone. */}
                      {d.title.slice(0, d.title.lastIndexOf(' ') + 1)}
                      <span className={s.extLast}>
                        {d.title.slice(d.title.lastIndexOf(' ') + 1)}{' '}
                        <ExternalLink size={13} className={s.extIcon} aria-hidden="true" />
                      </span>
                      <span className="sr-only">(opens in new tab)</span>
                    </a>
                    <small>
                      {d.org} · {d.year}
                    </small>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
        <Link href="/data" className="btn btn-primary btn-sm" style={{ marginTop: 16 }}>
          All NASA data <ArrowRight size={14} />
        </Link>
      </section>

      <div className={s.disclaimer}>
        <Info size={18} />
        <p>
          ASTRA is a hackathon prototype for decision support. It does not diagnose. Ranges are simplified adult values
          for illustration. Real crews follow agency-approved medical checklists and flight-surgeon guidance.
        </p>
      </div>
    </div>
  );
}
