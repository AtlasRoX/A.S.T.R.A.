import Link from 'next/link';
import { Database } from '../ui/icons';
import s from './sourcetag.module.css';

/**
 * Short, readable names for the source ids.
 *
 * The ids are stable keys used by the engine; this is what the crew reads. Keep them
 * short enough to sit in a row of pills.
 */
const SHORT: Record<string, string> = {
  std3001v1: 'STD-3001 Vol 1',
  std3001v2: 'STD-3001 Vol 2',
  ochmo_tb004: 'OCHMO-TB-004',
  hrp_roadmap: 'HRP Roadmap',
  hrp_radiation: 'HRP Radiation',
  hrp_bone: 'HRP Bone fracture',
  hrp_sans: 'HRP SANS',
  hrp_cog: 'HRP Cognition',
  hrp_sleep: 'HRP Sleep',
  hrp_immuno: 'HRP Immune',
  hrp_microbe: 'HRP Microorganisms',
  hrp_dust: 'HRP Celestial dust',
  hrp_cardio: 'HRP Cardiovascular',
  hrp_renal: 'HRP Renal stones',
  hrp_eve: 'HRP EVA',
  hrp_team: 'HRP Team',
  hrp_sport: 'HRP Sensorimotor',
  hrp_hypoxia: 'HRP Hypoxia',
  hrp_meds: 'HRP Medications',
  hrp_food: 'HRP Nutrition',
  hrp_illness: 'HRP Medical conditions',
  hrp_eihs: 'HRP Autonomous ops',
  hrp_dynload: 'HRP Dynamic loads',
  hrp_dcs: 'HRP Decompression',
  msl_rad_cruise: 'MSL/RAD transit',
  msl_rad_surface: 'MSL/RAD surface',
  i4_omics: 'Inspiration4 omics',
  donki: 'DONKI',
  horizons: 'JPL Horizons',
  osdr_eda: 'OSDR EDA',
  osdr_i4: 'OSDR Inspiration4',
  msl_mission: 'MSL mission',
  twins: 'Twins Study',
  artemis_iii: 'Artemis III',
  hrp_hazards: 'HRP 5 Hazards',
  hrp_risks: 'HRP Risks',
  hrp_research: 'HRP Ongoing research',
  hrp_hz_radiation: 'HRP Radiation hazard',
  hrp_hz_isolation: 'HRP Isolation hazard',
  hrp_hz_distance: 'HRP Distance hazard',
  hrp_hz_gravity: 'HRP Gravity hazard',
  hrp_hz_environment: 'HRP Environment hazard',
  hrp_archer: 'ARCHeR (Artemis II)',
  hrp_standard_measures: 'HRP Standard Measures',
  csa_radiation: 'CSA Radiation',
  csa_radin2: 'CSA Radi-N2',
  csa_evarm: 'CSA EVARM',
  csa_body: 'CSA Body infographic',
  csa_why_science: 'CSA Science in space',
};

/** The readable name for a source id, falling back to the id itself. */
export function sourceName(id: string) {
  return SHORT[id] ?? id;
}

/**
 * A small link to the NASA source behind a number.
 *
 * Every threshold ASTRA shows has one, so the crew can check where a number came from
 * without leaving the page.
 */
export function SourceTag({
  label = 'NASA source',
  sourceId,
  title,
}: {
  label?: string;
  /** The manifest id, so the link lands on the right card in /data. */
  sourceId?: string;
  /** The document title, shown as the link text. */
  title?: string;
}) {
  const href = sourceId ? `/data#${sourceId}` : '/data';
  return (
    <Link href={href} className={s.tag} title={title ?? 'See the NASA source for this number'}>
      <Database size={12} strokeWidth={2} />
      <span>{title ?? label}</span>
    </Link>
  );
}

/** A row of source links, one per document. */
export function SourceList({ ids, label = 'Evidence' }: { ids: string[]; label?: string }) {
  if (!ids.length) return null;
  return (
    <span className={s.list}>
      <span className={s.listLabel}>{label}</span>
      {ids.map((id) => (
        <Link key={id} href={`/data#doc-${id}`} className={s.link} title={`Open the NASA source: ${sourceName(id)}`}>
          {sourceName(id)}
        </Link>
      ))}
    </span>
  );
}
