'use client';

import { CrewAvatar } from '../ui/CrewAvatar';
import { radioGroupKeys } from '@/lib/a11y';
import { useState, useSyncExternalStore, useTransition } from 'react';
import { setCrew, setEnvironment } from '@/app/actions';
import { cx, duration } from '@/lib/format';
import type { CrewMember, Environment } from '@/lib/types';
import { getSoundSettings, onSoundSettings, play, serverSoundSettings, setSoundSettings, type SoundName } from '@/lib/sound';
import { Check, LoaderCircle, Moon, Sun, Volume1, Volume2, VolumeX } from '../ui/icons';
import { useTheme } from '../ui/theme';
import s from './settings.module.css';

export function CrewPicker({ crew, current }: { crew: CrewMember[]; current: string }) {
  const [pending, start] = useTransition();
  const [target, setTarget] = useState<string | null>(null);
  return (
    <div className={s.options}>
      {crew.map((c) => (
        <button key={c.id} type="button" className={cx(s.option, c.id === current && s.on)} aria-pressed={c.id === current}
          onClick={() => {
            setTarget(c.id);
            start(() => setCrew(c.id));
          }}>
          <CrewAvatar member={c} />
          <span className={s.optText}>
            <b>
              {c.title} {c.name}
            </b>
            <small>
              {c.role}
              {c.is_cmo ? ' · medical lead' : ''}
            </small>
          </span>
          {pending && target === c.id ? <LoaderCircle size={16} className="spin" /> : c.id === current ? <Check size={17} /> : null}
        </button>
      ))}
    </div>
  );
}

export function EnvPicker({ envs, current }: { envs: Environment[]; current: string }) {
  const [pending, start] = useTransition();
  const [target, setTarget] = useState<string | null>(null);
  return (
    <div className={s.envs}>
      {envs.map((e) => (
        <button key={e.id} type="button" className={cx(s.env, e.id === current && s.on)} aria-pressed={e.id === current}
          onClick={() => {
            setTarget(e.id);
            start(() => setEnvironment(e.id));
          }}>
          <div className="row" style={{ justifyContent: 'space-between', width: '100%' }}>
            <span className="overline">{e.kind} · {e.location}</span>
            {pending && target === e.id ? <LoaderCircle size={16} className="spin" /> : e.id === current ? <Check size={17} /> : null}
          </div>
          <b>{e.name}</b>
          <div className={s.envStats}>
            <span>{e.gravity.split(' ·')[0]}</span>
            <span>{e.delay_s < 5 ? 'live link' : duration(e.delay_s)}</span>
            <span title={e.radiation_source ? undefined : 'Planning estimate, not yet sourced'}>
              {e.radiation_msv_day} mSv/d{e.radiation_source ? '' : ' (est.)'}
            </span>
          </div>
          <small>{e.tip}</small>
        </button>
      ))}
    </div>
  );
}

export function ThemeSetting() {
  const [theme, apply] = useTheme();
  return (
    <div className="seg" role="radiogroup" aria-label="Theme" onKeyDown={radioGroupKeys} tabIndex={-1}>
      <button type="button" className={cx(theme === 'dark' && 'on')} onClick={() => apply('dark')} role="radio"
        aria-checked={theme === 'dark'}>
        <Moon size={15} style={{ marginRight: 6 }} /> Dark
      </button>
      <button type="button" className={cx(theme === 'light' && 'on')} onClick={() => apply('light')} role="radio"
        aria-checked={theme === 'light'}>
        <Sun size={15} style={{ marginRight: 6 }} /> Light
      </button>
    </div>
  );
}

const SOUND_MODES = [
  { id: 'all', label: 'All sounds' },
  { id: 'alerts', label: 'Alerts only' },
  { id: 'off', label: 'Off' },
] as const;
const SOUND_TESTS: { id: SoundName; label: string }[] = [
  { id: 'act', label: 'Act alert' },
  { id: 'watch', label: 'Watch' },
  { id: 'emergency', label: 'Emergency' },
  { id: 'success', label: 'Saved' },
];

/** Sound: all, alerts only (no feedback sounds) or off; a volume; and a way to hear each kind. Stored per browser. */
export function SoundSetting() {
  const cfg = useSyncExternalStore(onSoundSettings, getSoundSettings, serverSoundSettings);
  const mode = !cfg.on ? 'off' : cfg.mode;
  return (
    <div className="stack" style={{ gap: 14 }}>
      <div className="seg" role="radiogroup" aria-label="Sound" onKeyDown={radioGroupKeys} tabIndex={-1}>
        {SOUND_MODES.map((m) => (
          <button key={m.id} type="button" role="radio" aria-checked={mode === m.id} className={cx(mode === m.id && 'on')}
            onClick={() => setSoundSettings(m.id === 'off' ? { on: false } : { on: true, mode: m.id })}>
            {m.label}
          </button>
        ))}
      </div>
      <div className={cx(s.volume, !cfg.on && s.volumeOff)}>
        {/* The speaker mutes and unmutes (same as Off / All sounds); its icon follows the level. */}
        <button type="button" className={s.mute} aria-pressed={!cfg.on} aria-label={cfg.on ? 'Mute sounds' : 'Turn sounds on'}
          onClick={() => setSoundSettings({ on: !cfg.on })}>
          {!cfg.on || cfg.volume === 0 ? <VolumeX size={18} /> : cfg.volume < 0.5 ? <Volume1 size={18} /> : <Volume2 size={18} />}
        </button>
        <label htmlFor="sound-volume" className={s.volumeLabel}>Volume</label>
        <input id="sound-volume" className={s.range} type="range" min={0} max={1} step={0.05} value={cfg.volume}
          disabled={!cfg.on} style={{ '--fill': `${cfg.volume * 100}%` } as React.CSSProperties}
          aria-valuetext={`${Math.round(cfg.volume * 100)}%`}
          onChange={(e) => setSoundSettings({ volume: Number(e.target.value) })}
          onPointerUp={() => play('confirm')} onKeyUp={() => play('confirm')} />
        <output htmlFor="sound-volume" className={cx('num', s.volumeValue)}>{cfg.on ? `${Math.round(cfg.volume * 100)}%` : 'Off'}</output>
      </div>
      <div className={s.soundTests}>
        <span className="faint">Hear:</span>
        {SOUND_TESTS.map((t) => (
          <button key={t.id} type="button" className="btn btn-tonal btn-sm" disabled={!cfg.on || (cfg.mode === 'alerts' && t.id === 'success')}
            onClick={() => play(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <p className="faint" style={{ fontSize: 13 }}>
        Each alert sounds once. An Act alert still open after 5 minutes reminds you, twice at most. During an emergency
        protocol only the alarm and timer sounds play.
      </p>
    </div>
  );
}
