import type { Metadata } from 'next';
import Link from 'next/link';
import { ReferenceTabs } from '@/components/ui/ReferenceTabs';
import { SourceList } from '@/components/ui/SourceTag';
import { ChevronLeft, Info } from '@/components/ui/icons';
import { getInspiration4 } from '@/lib/engine';
import { LabChart } from './LabChart';
import { SUBJECT_COLOR, SUBJECT_LABEL } from './subjects';
import s from './i4.module.css';

export const metadata: Metadata = { title: 'Inspiration4 · real astronaut data' };

export default async function Inspiration4Page() {
  const i4 = await getInspiration4();

  if (!i4.available) {
    return (
      <div className="page">
        <Link href="/data" className="btn btn-text btn-sm">
          <ChevronLeft size={16} /> NASA data
        </Link>
        <h1 className="h-page">Inspiration4</h1>
        <div className={s.unavailable}>
          <Info size={18} />
          <p>
            The Inspiration4 dataset is not available in this build. The NASA OSDR fixture has not been downloaded,
            so there is nothing to plot. Nothing is shown here rather than a chart of invented numbers.
          </p>
        </div>
      </div>
    );
  }

  const flight = i4.flight_window;
  const pointCount = i4.series.reduce((n, series) => n + series.points.length, 0);

  return (
    <div className={`page ${s.root}`}>
      <ReferenceTabs />
      <section className={s.hero}>
        <h1 className="h-page">Inspiration4</h1>
        <p>
          Four real civilians flew a three-day orbital mission in September 2021 (Inspiration4 flew on its own and did not dock with the International Space Station). These are their
          actual blood panels, published by NASA, plotted against the reference ranges the dataset itself carries. The
          only thing ASTRA adds is the status label on each point.
        </p>
        <p className={s.meta}>
          <b>{i4.series.length}</b> analytes
          {' · '}
          <b>{i4.subjects.length}</b> crew members
          {' · '}
          <b>{pointCount}</b> measurements
          {' · '}
          <b>{i4.days.length}</b> sampling days
        </p>
        <div className={s.legend}>
          {i4.subjects.map((sub) => (
            <span key={sub} className={s.legendItem}>
              <i style={{ background: SUBJECT_COLOR[sub] }} aria-hidden />
              {SUBJECT_LABEL[sub] ?? sub}
            </span>
          ))}
          {flight.from !== null && flight.to !== null ? (
            <span className={s.legendItem}>
              <i className={s.legendFlight} aria-hidden />
              Flight ({flight.from} to {flight.to} days)
            </span>
          ) : null}
          <span className={s.legendItem}>
            <i className={`${s.legendRing} st-watch`} aria-hidden />
            Watch
          </span>
          <span className={s.legendItem}>
            <i className={`${s.legendRing} st-act`} aria-hidden />
            Act
          </span>
        </div>
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>Every analyte</h2>
        <p className={s.sub}>
          One chart per test. The shaded band is the reference range from the dataset (where men and women have different ranges, the band shows the widest). A point outside its own range is marked
          Watch or Act by ASTRA&apos;s own rule: within 10% of a range edge is Watch, further out is Act.
        </p>
        <div className={s.grid}>
          {i4.series.map((series) => (
            <LabChart key={series.id} series={series} subjects={i4.subjects} flight={flight} />
          ))}
        </div>
      </section>

      <section className={s.section}>
        <h2 className={s.h2}>What this shows</h2>
        <div className={s.notes}>
          {i4.analytes.map((a) => (
            <div key={a.id} className={s.note}>
              <b>{a.label}</b>
              <p>{a.why}</p>
            </div>
          ))}
        </div>
      </section>

      <div className={s.disclaimer}>
        <Info size={18} />
        <p>
          The values and the reference ranges are NASA&apos;s, published in the Open Science Data Repository. The status
          labels and the 10% tolerance band are ASTRA&apos;s, added for this demo. Real crews follow agency-approved
          medical checklists and flight-surgeon guidance.
        </p>
      </div>

      <div className={s.sources}>
        <SourceList ids={i4.sources} label="Sources" />
      </div>
    </div>
  );
}
