import type { Metadata } from 'next';
import { CrewPicker, EnvPicker, SoundSetting, ThemeSetting } from '@/components/settings/SettingsControls';
import s from '@/components/settings/settings.module.css';
import { CircleCheck, Info, TriangleAlert } from '@/components/ui/icons';
import { getCatalog, getHealth } from '@/lib/engine';
import { getSession } from '@/lib/session';

export const metadata: Metadata = { title: 'Settings' };

export default async function SettingsPage() {
  const { crew, env } = await getSession();
  const catalog = await getCatalog();
  // A real check of the engine, not a fixed label; a failure here must not blank the page.
  const health = await getHealth().catch(() => null);
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1 className="h-page">Settings</h1>
          <p>Choose who is using this tablet and where the crew is. ASTRA adapts its numbers, routine and advice.</p>
        </div>
      </div>

      <section className="card" style={{ marginBottom: 16 }}>
        <div className="card-head">
          <h2 className="h-card">Mission environment</h2>
          <span className="faint" style={{ fontSize: 13 }}>Changes gravity, signal delay, radiation and routine</span>
        </div>
        <EnvPicker envs={catalog.environments} current={env} />
      </section>

      <div className={s.grid}>
        <section className="card">
          <div className="card-head">
            <h2 className="h-card">Crew member</h2>
          </div>
          <CrewPicker crew={catalog.crew} current={crew} />
        </section>

        <div className="stack">
          <section className="card">
            <div className="card-head">
              <h2 className="h-card">Appearance</h2>
            </div>
            <ThemeSetting />
          </section>
          <section className="card">
            <div className="card-head">
              <h2 className="h-card">Sound</h2>
              <span className="faint" style={{ fontSize: 13 }}>Saved on this device</span>
            </div>
            <SoundSetting />
          </section>
          <section className="card">
            <div className="card-head">
              <h2 className="h-card">About ASTRA</h2>
              {health?.ok ? (
                <span className="chip chip-ok">
                  <CircleCheck size={13} /> Core online
                </span>
              ) : (
                <span className="chip chip-watch">
                  <TriangleAlert size={13} /> Core not responding
                </span>
              )}
            </div>
            <p className="muted" style={{ fontSize: 14 }}>
              <b style={{ color: 'var(--text)' }}>ASTRA</b> (Astronaut Self-Triage &amp; Readiness Assistant) is a
              prototype for the NASA Space Apps Challenge 2026: <i>Create Health Monitoring Software for Astronauts on
              Space Missions</i>. Its Python core runs the health rules on board; this interface works without Earth.
            </p>
            <p className="faint" style={{ fontSize: 13, marginTop: 10, display: 'flex', gap: 8 }}>
              <Info size={15} style={{ flex: 'none', marginTop: 2 }} />
              The crew and the mission ({catalog.mission.name}) are fictional. The environment data (signal delay, cabin air, radiation, solar storms) is real NASA data. Ranges are simplified, not medical advice.
            </p>
            <p className="faint" style={{ fontSize: 13, marginTop: 8 }}>
              Sound effects generated with ElevenLabs. 3D anatomy: BodyParts3D, © The Database Center for Life Science, licensed under{' '}
              <a href="https://dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html" target="_blank" rel="noopener noreferrer"
                style={{ textDecoration: 'underline' }}>
                CC Attribution 4.0 International
              </a>
              .
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
