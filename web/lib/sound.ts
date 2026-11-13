/**
 * ASTRA's sound engine. One place decides whether, when and how loud a sound plays, so components only say what
 * happened ("an Act alert arrived", "a reading was saved").
 *
 * Rules (alarm design after IEC 60601-1-8 and NASA caution-and-warning practice):
 * - Priority: emergency > act > insight/watch > timer cues > warnings > feedback > rewards. A higher sound cuts a
 *   lower one; a lower one never interrupts a higher one.
 * - Alarm patterns: Act = 3 rising pulses (medium priority), Emergency = 3+2, 3+2 burst (high priority), Watch = 1.
 * - No alarm fatigue: each alert sounds once (remembered across reloads and tabs). An Act alert still open after
 *   5 minutes reminds again, at most twice. Sounds that land together are merged into the most important one.
 *   Alerts already open when ASTRA is first used are not announced.
 * - Focus: while an emergency protocol runs, only emergency and timer sounds play.
 * - Feedback sounds stay silent in a hidden tab; alerts do not.
 * - Browsers only allow audio after the first tap or key press: an alert that arrives before that plays then.
 * - Settings (on/off, volume, alerts only) are stored in this browser.
 */

export type SoundName =
  | 'emergency' | 'act' | 'insight' | 'watch' | 'step' | 'tick' | 'receive' | 'warning'
  | 'success' | 'send' | 'confirm' | 'reward';

type Category = 'alert' | 'cue' | 'feedback';
type Hit = { file: string; at: number; rate?: number; gain?: number };

const CUES: Record<SoundName, { priority: number; category: Category; gap: number; hits: Hit[] }> = {
  emergency: {
    priority: 6, category: 'alert', gap: 4000,
    hits: [0, 0.13, 0.26, 0.52, 0.65, 1.15, 1.28, 1.41, 1.67, 1.8].map((at) => ({ file: 'alarm', at })),
  },
  act: {
    priority: 5, category: 'alert', gap: 6000,
    hits: [1, 1.1225, 1.26].map((rate, i) => ({ file: 'pulse', at: i * 0.2, rate })),
  },
  insight: { priority: 4, category: 'alert', gap: 6000, hits: [{ file: 'insight', at: 0 }] },
  watch: { priority: 4, category: 'alert', gap: 20000, hits: [{ file: 'watch', at: 0 }] },
  step: { priority: 3, category: 'cue', gap: 300, hits: [{ file: 'step', at: 0 }] },
  tick: { priority: 3, category: 'cue', gap: 150, hits: [{ file: 'tick', at: 0 }] },
  receive: { priority: 3, category: 'alert', gap: 1500, hits: [{ file: 'receive', at: 0 }] },
  warning: { priority: 2, category: 'feedback', gap: 1500, hits: [{ file: 'warning', at: 0 }] },
  success: { priority: 1, category: 'feedback', gap: 500, hits: [{ file: 'success', at: 0 }] },
  send: { priority: 1, category: 'feedback', gap: 500, hits: [{ file: 'send', at: 0 }] },
  confirm: { priority: 1, category: 'feedback', gap: 120, hits: [{ file: 'confirm', at: 0 }] },
  reward: { priority: 0, category: 'feedback', gap: 1500, hits: [{ file: 'reward', at: 0, gain: 0.8 }] },
};
const CATEGORY_GAIN: Record<Category, number> = { alert: 1, cue: 0.9, feedback: 0.7 };
const FILES = [...new Set(Object.values(CUES).flatMap((c) => c.hits.map((h) => h.file)))];

/* ------------------------------------------------------------ settings */
export interface SoundSettings {
  on: boolean;
  volume: number;
  /** 'alerts': only alerts and timer cues, no feedback sounds. */
  mode: 'all' | 'alerts';
}
const SETTINGS_KEY = 'astra.sound';
const DEFAULTS: SoundSettings = { on: true, volume: 0.7, mode: 'all' };
let settings: SoundSettings = DEFAULTS;
let settingsLoaded = false;
const listeners = new Set<() => void>();

export function getSoundSettings(): SoundSettings {
  if (!settingsLoaded && typeof window !== 'undefined') {
    settingsLoaded = true;
    try {
      settings = { ...DEFAULTS, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? '{}') };
    } catch {}
  }
  return settings;
}
export const serverSoundSettings = () => DEFAULTS;
export function setSoundSettings(patch: Partial<SoundSettings>) {
  settings = { ...getSoundSettings(), ...patch };
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {}
  if (master) master.gain.value = settings.volume;
  listeners.forEach((l) => l());
}
export function onSoundSettings(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

/* ------------------------------------------------------------ audio */
let ctx: AudioContext | null = null;
let master: GainNode | null = null;
let unlocked = false;
const buffers = new Map<string, AudioBuffer | null>();
let current: { priority: number; until: number; sources: AudioScheduledSourceNode[] } | null = null;
const lastPlayed = new Map<SoundName, number>();
let focus = false;

function audio(): AudioContext | null {
  if (ctx) return ctx;
  try {
    const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = getSoundSettings().volume;
    master.connect(ctx.destination);
  } catch {
    ctx = null;
  }
  return ctx;
}

/** The files are fetched early (no audio needed for that) and decoded once audio is allowed. */
const bytes = new Map<string, Promise<ArrayBuffer>>();
const fetchFile = (file: string) => {
  if (!bytes.has(file)) bytes.set(file, fetch(`/sounds/${file}.mp3`).then((r) => r.arrayBuffer()));
  return bytes.get(file)!;
};
async function load(file: string) {
  if (buffers.has(file) || !ctx) return;
  buffers.set(file, null);
  try {
    buffers.set(file, await ctx.decodeAudioData((await fetchFile(file)).slice(0)));
  } catch {
    buffers.delete(file); // try again next time; a soft beep plays meanwhile
    bytes.delete(file);
  }
}

/** A plain beep, used when a sound file is not loaded (yet). */
function beep(c: AudioContext, out: AudioNode, at: number, rate: number): AudioScheduledSourceNode {
  const o = c.createOscillator();
  const g = c.createGain();
  o.frequency.value = 880 * rate;
  g.gain.setValueAtTime(0.0001, at);
  g.gain.exponentialRampToValueAtTime(0.25, at + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, at + 0.18);
  o.connect(g).connect(out);
  o.start(at);
  o.stop(at + 0.2);
  return o;
}

function render(name: SoundName) {
  const c = audio();
  if (!c || !master) return;
  const cue = CUES[name];
  const now = c.currentTime + 0.01;
  const out = c.createGain();
  out.gain.value = CATEGORY_GAIN[cue.category];
  out.connect(master);
  let end = now;
  const sources = cue.hits.map((h) => {
    const buf = buffers.get(h.file);
    const at = now + h.at;
    if (!buf) {
      end = Math.max(end, at + 0.2);
      return beep(c, out, at, h.rate ?? 1);
    }
    const src = c.createBufferSource();
    src.buffer = buf;
    src.playbackRate.value = h.rate ?? 1;
    let node: AudioNode = src;
    if (h.gain !== undefined) {
      const g = c.createGain();
      g.gain.value = h.gain;
      node = src.connect(g);
    }
    node.connect(out);
    src.start(at);
    end = Math.max(end, at + buf.duration / (h.rate ?? 1));
    return src;
  });
  current = { priority: cue.priority, until: performance.now() + (end - c.currentTime) * 1000, sources };
}

/* ------------------------------------------------------------ scheduling */
let pending: SoundName | null = null;
let pendingTimer: ReturnType<typeof setTimeout> | undefined;
/** An alert that arrived before audio was allowed; played on the first tap if still recent. */
let waiting: { name: SoundName; at: number } | null = null;

function allowed(name: SoundName) {
  const s = getSoundSettings();
  const cue = CUES[name];
  if (!s.on || s.volume <= 0) return false;
  if (s.mode === 'alerts' && cue.category === 'feedback') return false;
  if (focus && name !== 'emergency' && cue.category !== 'cue') return false;
  if (cue.category === 'feedback' && document.visibilityState === 'hidden') return false;
  return true;
}

function flush() {
  const name = pending;
  pending = null;
  if (!name) return;
  const cue = CUES[name];
  const t = performance.now();
  if (t - (lastPlayed.get(name) ?? -Infinity) < cue.gap) return;
  if (current && t < current.until) {
    if (current.priority > cue.priority) return; // never talk over a more important sound
    if (current.priority < cue.priority) current.sources.forEach((s) => {
      try {
        s.stop();
      } catch {}
    });
  }
  lastPlayed.set(name, t);
  render(name);
}

/** Play a sound now (merged with anything else asked for in the same moment). */
export function play(name: SoundName) {
  if (typeof window === 'undefined' || !allowed(name)) return;
  if (!unlocked) {
    if (CUES[name].category === 'alert' && (!waiting || CUES[name].priority >= CUES[waiting.name].priority))
      waiting = { name, at: Date.now() };
    return;
  }
  if (!pending || CUES[name].priority > CUES[pending].priority) pending = name;
  clearTimeout(pendingTimer);
  pendingTimer = setTimeout(flush, 90);
}

/** While an emergency protocol runs, everything except emergency and timer sounds is held back. */
export function setSoundFocus(on: boolean) {
  focus = on;
}

/* ------------------------------------------------------------ alerts: once each, Act reminders */
const HEARD_KEY = 'astra.sound.heard';
const REMIND_MS = 5 * 60_000;
const MAX_REMINDERS = 2;
type Heard = Record<string, [first: number, last: number, count: number]>;
/** First run in this browser: alerts already open are recorded silently instead of announced. */
let seedUntil = 0;

function readHeard(): Heard | null {
  try {
    const raw = localStorage.getItem(HEARD_KEY);
    return raw ? (JSON.parse(raw) as Heard) : null;
  } catch {
    return {};
  }
}
function writeHeard(h: Heard) {
  const keys = Object.keys(h);
  if (keys.length > 400) keys.toSorted((a, b) => h[a][1] - h[b][1]).slice(0, keys.length - 400).forEach((k) => delete h[k]);
  try {
    localStorage.setItem(HEARD_KEY, JSON.stringify(h));
  } catch {}
}

/**
 * An alert is open. Sounds the first time this key is seen (in any tab), then, for Act alerts that stay open,
 * reminds every 5 minutes, twice at most. Call it every time the alert is seen; repeats are free.
 */
export function alertSound(key: string, name: Extract<SoundName, 'emergency' | 'act' | 'insight' | 'watch' | 'receive'>) {
  if (typeof window === 'undefined') return;
  const now = Date.now();
  const heard = readHeard() ?? ((seedUntil = now + 4000), {});
  const seen = heard[key];
  if (!seen) {
    heard[key] = [now, now, 0];
    writeHeard(heard);
    if (now >= seedUntil) play(name);
    return;
  }
  if (name === 'act' && seen[2] < MAX_REMINDERS && now - seen[1] >= REMIND_MS) {
    heard[key] = [seen[0], now, seen[2] + 1];
    writeHeard(heard);
    play(name);
  }
}

/* ------------------------------------------------------------ setup */
let installed = false;
/** Call once on the client: unlocks audio on the first tap or key press and preloads the sounds. */
export function installSound() {
  if (installed || typeof window === 'undefined') return;
  installed = true;
  const unlock = () => {
    const c = audio();
    if (!c) return;
    void c.resume().then(() => {
      unlocked = true;
      FILES.forEach((f) => void load(f));
      if (waiting && Date.now() - waiting.at < 120_000) play(waiting.name);
      waiting = null;
    });
    window.removeEventListener('pointerdown', unlock, true);
    window.removeEventListener('keydown', unlock, true);
  };
  window.addEventListener('pointerdown', unlock, true);
  window.addEventListener('keydown', unlock, true);
  setTimeout(() => FILES.forEach((f) => void fetchFile(f).catch(() => bytes.delete(f))), 1500);
  // Volume may change in another tab.
  window.addEventListener('storage', (e) => {
    if (e.key !== SETTINGS_KEY) return;
    settingsLoaded = false;
    getSoundSettings();
    if (master) master.gain.value = settings.volume;
    listeners.forEach((l) => l());
  });
}

/** Master volume for sounds made outside this engine (the CPR metronome), or 0 when sound is off. */
export const soundVolume = () => (getSoundSettings().on ? getSoundSettings().volume : 0);
