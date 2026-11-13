import type { Metadata } from 'next';
import Link from 'next/link';
import { TrendChart } from '@/components/charts/TrendChart';
import { CompareSelect } from '@/components/trends/CompareSelect';
import { IndicatorNav } from '@/components/trends/IndicatorNav';
import { ReadingSource } from '@/components/ui/ReadingSource';
import { getCatalog, getDashboard, getSeries } from '@/lib/engine';
import { ageLabel, cx, fmt, signed, unitFor } from '@/lib/format';
import { getSession } from '@/lib/session';
import type { MetricDef, Series } from '@/lib/types';
import s from './trends.module.css';
import { TabList } from '@/components/ui/TabList';

export const metadata: Metadata = { title: 'Trends' };

const RANGES = [7, 14, 30] as const;
const STATUS_WORD = { ok: 'Nominal', watch: 'Watch', act: 'Act' } as const;

export default async function TrendsPage({
  searchParams,
}: {
  searchParams: Promise<{ m?: string; r?: string; c?: string }>;
}) {
  const sp = await searchParams;
  const { crew, env } = await getSession();
  const [catalog, d] = await Promise.all([getCatalog(), getDashboard(crew, env)]);
  const metric = catalog.metrics.find((m) => m.id === sp.m) ?? catalog.metrics.find((m) => m.id === 'sleep')!;
  const range = RANGES.includes(Number(sp.r) as 7) ? Number(sp.r) : 14;
  const compareDef = sp.c && sp.c !== metric.id ? catalog.metrics.find((m) => m.id === sp.c) : undefined;
  const [series, compare] = await Promise.all([
    getSeries(crew, metric.id, range),
    compareDef ? getSeries(crew, compareDef.id, range) : Promise.resolve(null),
  ]);
  const st = series.state;
  const groups = Object.entries(
    catalog.metrics.reduce<Record<string, MetricDef[]>>((acc, m) => {
      (acc[m.category] ??= []).push(m);
      return acc;
    }, {}),
  );
  const href = (p: { m?: string; r?: number; c?: string | null }) => {
    const q = new URLSearchParams();
    q.set('m', p.m ?? metric.id);
    q.set('r', String(p.r ?? range));
    const c = p.c === undefined ? compareDef?.id : p.c;
    if (c) q.set('c', c);
    return `/trends?${q.toString()}`;
  };
    const dec = metric.id === 'mood' ? 1 : metric.decimals;
  const total = series.stats.days_ok + series.stats.days_watch + series.stats.days_act || 1;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h-page">Trends</h1>
          <p>How each indicator changes over time, against the normal range and your own personal baseline.</p>
        </div>
        <TabList label="Time range" className="seg">
          {RANGES.map((r) => (
            <Link key={r} href={href({ r })} className={cx(r === range && 'on')} role="tab" aria-selected={r === range}
              scroll={false}>
              {r} days
            </Link>
          ))}
        </TabList>
      </div>

      <div className={s.layout}>
        <IndicatorNav className={s.list} active={metric.id}>
          {groups.map(([cat, ms]) => (
            <div key={cat} className={s.group}>
              <span className={s.cat}>{cat}</span>
              {ms.map((m) => {
                const ms2 = d.metrics[m.id];
                return (
                  <Link key={m.id} href={href({ m: m.id, c: null })} scroll={false}
                    className={cx(s.item, m.id === metric.id && s.active, `st-${ms2.status}`, ms2.stale && 'is-stale')}
                    aria-current={m.id === metric.id ? 'page' : undefined}>
                    <span className={s.dot} />
                    <span className={s.itemLabel}>{m.label}</span>
                    <span className={s.itemValue}>{ms2.has_data ? (m.id === 'vision' ? m.input.labels?.[ms2.value ?? 0] : m.id === 'symptoms' ? (ms2.meta?.items?.length ? `${ms2.meta.items.length} reported` : 'None') : ms2.display) : '–'}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </IndicatorNav>

        <div className={s.main}>
          <section className={cx(s.head, `st-${st.status}`)}>
            <div className={s.headText}>
              <h2>{metric.label}</h2>
              <p>
                <b className={s.stWord}>{st.personal ? 'Unusual for you' : STATUS_WORD[st.status]}</b>
                {st.delta !== null && metric.id !== 'symptoms' && metric.id !== 'vision'
                  ? metric.id === 'mass' && st.change_pct !== undefined
                    ? `, ${signed(st.change_pct, 1)}% vs reference mass`
                    : `, ${signed(st.delta, dec)} ${unitFor(metric)} vs your baseline`
                  : ''}
                . Last reading {ageLabel(st.age_days, st.time).toLowerCase()}.
              </p>
            </div>
            <div className={s.headValue}>
              <span className="num">
                {st.has_data ? (metric.id === 'vision' ? metric.input.labels?.[st.value ?? 0] : st.display) : '–'}
              </span>
              <small>{metric.id === 'vision' ? '' : unitFor(metric)}</small>
            </div>
            <Link href={`/measure/${metric.id}`} className="btn btn-primary btn-sm">
              Measure now
            </Link>
          </section>

          <section className={s.chartBox}>
            <div className="card-head">
              <h3 className="h-card">Last {range} days</h3>
              <CompareSelect
                options={catalog.metrics.filter((m) => m.id !== metric.id).map((m) => ({ id: m.id, label: m.label, group: m.category }))}
                value={compareDef?.id ?? ''}
              />
            </div>
            {series.points.length ? (
              <TrendChart
                points={series.points}
                band={series.band}
                axis={series.axis}
                baseline={series.baseline}
                unit={unitFor(metric)}
                decimals={metric.decimals}
                today={series.today}
                days={range}
                label={metric.label}
                compare={
                  compare && compareDef
                    ? {
                        label: compareDef.label,
                        unit: unitFor(compareDef),
                        decimals: compareDef.decimals,
                        axis: compare.axis,
                        points: compare.points.map((p) => ({ day: p.day, value: p.value })),
                      }
                    : null
                }
              />
            ) : (
              <p className="empty">No readings in this period yet.</p>
            )}
            <div className={s.legend}>
              <span><i className={s.lgOk} /> Normal range</span>
              <span><i className={s.lgWatch} /> Watch zone</span>
              <span><i className={s.lgAct} /> Act zone</span>
              <span><i className={s.lgBase} /> Your baseline</span>
              {compareDef ? <span><i className={s.lgCmp} /> {compareDef.label} (right axis)</span> : null}
              {metric.id === 'bp' ? <span className="faint">Upper line systolic, lower line diastolic</span> : null}
            </div>
          </section>

          <dl className={s.stats}>
            <Stat label="Average" value={fmt(series.stats.mean, dec)} unit={unitFor(metric)} />
            <Stat label="Lowest" value={fmt(series.stats.min, metric.decimals)} unit={unitFor(metric)} />
            <Stat label="Highest" value={fmt(series.stats.max, metric.decimals)} unit={unitFor(metric)} />
            <Stat label="Days in normal range" value={`${Math.round((series.stats.days_ok / total) * 100)}`} unit="%" />
          </dl>

          {/* Size container: the docked specialist panel narrows this column while the viewport stays wide. */}
          <div className={s.twoWrap}>
            <div className={s.two}>
              <Explain metric={metric} />
              <ReadingLog series={series} metric={metric} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, unit }: { label: string; value: string; unit: string }) {
  return (
    <div className={s.stat}>
      <dt>{label}</dt>
      <dd>
        {value} <small>{unit}</small>
      </dd>
    </div>
  );
}

function Explain({ metric }: { metric: MetricDef }) {
  return (
    <section className={s.box}>
      <div className="card-head">
        <h3 className="h-card">Understand this indicator</h3>
      </div>
      <p style={{ marginBottom: 12 }}>{metric.why}</p>
      <div className={s.space}>
        <h4 className={s.cat}>In space</h4>
        <p>{metric.space}</p>
      </div>
      <div className={s.guides}>
        {(['ok', 'watch', 'act'] as const).map((k) => (
          <div key={k} className={cx(s.guide, `st-${k}`)}>
            <b className={s.stWord}>{STATUS_WORD[k]}</b>
            <p>{metric.guide[k]}</p>
          </div>
        ))}
      </div>
      <p className="faint" style={{ fontSize: 13, marginTop: 12 }}>
        <b style={{ color: 'var(--text-2)' }}>When to escalate:</b> {metric.escalate}
      </p>
    </section>
  );
}

function ReadingLog({ series, metric }: { series: Series; metric: MetricDef }) {
  return (
    <section className={s.box}>
      <div className="card-head">
        <h3 className="h-card">Recent readings</h3>
        <span className="faint" style={{ fontSize: 12.5 }}>Newest first</span>
      </div>
      {series.log.length ? (
        <ul className={s.log}>
          {series.log.map((r) => (
            <li key={r.id}>
              <span className="num faint">
                Day {r.day}, {r.time}
              </span>
              <span className={s.logValue}>
                {metric.id === 'vision' ? metric.input.labels?.[Number(r.display)] : r.display}{' '}
                <small className="faint">{metric.id === 'vision' ? '' : unitFor(metric)}</small>
                {r.items && r.items.length ? (
                  <small className="faint">, {r.items.join(', ').replaceAll('_', ' ')}</small>
                ) : null}
                {' '}
                <ReadingSource source={r.source} />
              </span>
              <span className={cx(s.stWord, `st-${r.status}`)}>{STATUS_WORD[r.status]}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="empty">No readings yet.</p>
      )}
    </section>
  );
}
