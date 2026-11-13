// Types mirroring the ASTRA Core (Python) API.

export type Status = 'ok' | 'watch' | 'act';
export type HazardId = 'R' | 'I' | 'D' | 'G' | 'E';
export type InputKind = 'number' | 'bp' | 'mood' | 'reaction' | 'amsler' | 'symptoms';

export interface Hazard {
  id: HazardId;
  name: string;
  short: string;
  summary: string;
  effects: string[];
  metrics: string[];
  countermeasures: string[];
  sources: string[];
}

export interface MetricDef {
  id: string;
  label: string;
  short: string;
  unit: string;
  decimals: number;
  category: string;
  organ: string;
  hazards: HazardId[];
  rule?: 'relative';
  input: { kind: InputKind; min: number; max: number; step: number; placeholder: string; labels?: string[] };
  ok: [number, number];
  watch: [number, number];
  ok2?: [number, number];
  watch2?: [number, number];
  axis: [number, number] | null;
  min_sd: number;
  device: string;
  duration: string;
  how: string[];
  why: string;
  space: string;
  guide: Record<Status, string>;
  escalate: string;
  prevent: string[];
  sources: string[];
  /** The reading depends on what the crew member was doing just before (rest vs exercise). */
  context_sensitive?: boolean;
  /** Recovery ranges used after exercise or an EVA. */
  active?: { ok: [number, number]; watch: [number, number]; ok2?: [number, number]; watch2?: [number, number] };
}

/** What the crew member was doing just before a measurement. */
export interface MeasureContext {
  id: 'rest' | 'just_woke' | 'after_exercise' | 'after_eva';
  label: string;
  detail: string;
  active: boolean;
}

/** A post-exertion reading shown next to the resting status. */
export interface ActiveReading {
  display: string;
  context: MeasureContext['id'];
  context_label: string;
  time: string;
  status: Status;
  source?: string;
}

export interface OrganDef {
  id: string;
  name: string;
  metrics: string[];
  hazards: HazardId[];
  function: string;
  space: string;
  actions: string[];
  sources: string[];
}

export interface TaskDef {
  id: string;
  time: string;
  title: string;
  metrics: string[];
  xp: number;
}

export interface Environment {
  id: string;
  name: string;
  kind: string;
  location: string;
  gravity_g: number;
  gravity: string;
  delay_s: number;
  delay_note: string;
  radiation_msv_day: number;
  evacuation: string;
  med_kit: string;
  risks: string[];
  tip: string;
  extra_tasks: TaskDef[];
  sources: string[];
  /** Where the dose rate comes from (a manifest id), or null for a planning estimate. */
  radiation_source?: string | null;
  /** The real UTC date of the current mission day, and the day number. */
  utc?: string;
  mission_day?: number;
  /** 'horizons' when the delay came from the real JPL Horizons table. */
  light_time_source?: string | null;
}

export interface CrewMember {
  id: string;
  name: string;
  title: string;
  role: string;
  initials: string;
  hue: number;
  prior_dose_msv: number;
  base_xp: number;
  mass_ref: number;
  is_cmo: boolean;
}

/** Honest Orbit: the Missions page. Every number here comes from stored readings, acknowledgements and the XP ledger. */
export interface GameHub {
  crew_id: string;
  day: number;
  /** Today, worked out by ASTRA Core with the same rules that pay XP. */
  today: {
    done: number;
    total: number;
    /** XP earned so far today (from the ledger). */
    xp: number;
    orbit_done: boolean;
    orbit_xp: number;
    /** The next check to do and what it pays if done now: the first line is its base XP, then the bonuses. */
    next: {
      id: string;
      title: string;
      time: string;
      overdue: boolean;
      worth: number;
      lines: { amount: number; reason: string }[];
      href: string;
    } | null;
  };
  level: { xp: number; level: number; title: string; level_xp: number; xp_per_level: number };
  streak: {
    current: number;
    best: number;
    shields: number;
    shield_max: number;
    shield_every: number;
    calendar: {
      day: number;
      status: 'done' | 'eased' | 'shielded' | 'missed' | 'today' | 'none';
      done: number;
      total: number;
    }[];
  };
  momentum: {
    last7: number | null;
    prev7: number | null;
    trend: 'up' | 'steady' | 'down';
    support: boolean;
    message: string;
    core_tasks: string[];
  };
  chapter: {
    id: string;
    name: string;
    focus: string;
    detail: string;
    index: number;
    count: number;
    day: number;
    transit_days: number;
    start: number;
    end: number;
    progress: number;
    guard: boolean;
    /** 2 in the third quarter: crew operations count double. */
    boost: number;
    chapters: { id: string; name: string; start: number; end: number }[];
  };
  quests: {
    id: string;
    title: string;
    metric: string;
    reason: string;
    progress: number;
    target: number;
    xp: number;
    done: boolean;
    claimed: boolean;
    href: string;
  }[];
  badges: (BadgeDef & { group: string; value: number; target: number; earned: boolean })[];
  badge_groups: Record<string, string>;
  earned_count: number;
  crew: {
    week: number;
    start_day: number;
    end_day: number;
    operation: {
      id: string;
      name: string;
      detail: string;
      unit: string;
      target: number;
      value: number;
      raw: number;
      boost: number;
      done: boolean;
      per_crew: { crew_id: string; name: string; value: number | null }[];
    };
    versus: { this_week: number | null; last_week: number | null; days: number; ahead: boolean };
    goal_days: number;
    perks: { days: number; name: string; icon: string; unlocked: boolean; approved_by: string | null }[];
  };
  ledger: { id: number; amount: number; reason: string; at: number; at_label: string }[];
  rules: { what: string; xp: string; note: string }[];
  seed_xp: number;
  /** Only the Commander approves unlocked crew rewards. */
  can_approve: boolean;
}

export type SessionKind = 'resistance' | 'intervals' | 'continuous' | 'rest' | 'light';

export interface ExerciseVideo {
  /** One of the two is set: an agency YouTube video, or a public-domain NASA file. */
  youtube: string | null;
  mp4: string | null;
  /** The clip: seconds into the video where this exercise is on screen. */
  start: number;
  end: number;
  /** What the clip shows, e.g. "Squats on ARED". */
  shows: string;
  who: string;
  where: string;
  title: string;
  channel: string;
  /** ISO date the video was published. */
  published: string;
  /** Watch link that starts at the clip. */
  url: string;
  license: string;
  license_url: string;
  /** Set when the footage is not exactly this device or place (e.g. ISS footage for a Mars base). */
  note?: string;
}

export interface ExerciseDef {
  id: string;
  name: string;
  kind: 'resistance' | 'aerobic';
  /** Which figure animation to play. */
  anim: 'squat' | 'deadlift' | 'heel_raise' | 'press' | 'row' | 'run' | 'cycle';
  targets: string[];
  why: string;
  cues: string[];
  video: ExerciseVideo | null;
}

export interface SessionItem {
  id: string;
  device: string;
  sets: number | null;
  reps: number | null;
  intensity: string;
  minutes: number;
  role: 'warm-up' | 'main' | 'second';
}

export interface PlanAdjustment {
  title: string;
  reason: string;
  source: string;
  severity: Status;
  metric: string | null;
}

export interface ExercisePlan {
  crew_id: string;
  env: string;
  day: number;
  time: string;
  today: { kind: SessionKind; title: string; minutes: number; block_min: number; items: SessionItem[] };
  exercises: Record<string, ExerciseDef>;
  devices: Record<string, { name: string; full: string; note: string }>;
  adjustments: PlanAdjustment[];
  week: {
    day: number;
    weekday: string;
    kind: SessionKind;
    title: string;
    planned_min: number;
    done_min: number | null;
    today: boolean;
    past: boolean;
    adjusted?: boolean;
  }[];
  source: string;
}

/** A past condition and the indicators it makes more likely to drift. */
export interface HistoryItem {
  year: number;
  condition: string;
  status: 'resolved' | 'managed' | 'monitoring';
  /** Indicator ids to keep an eye on because of this history. */
  watch: string[];
  /** How this history can show up in flight. */
  influence: string;
}

/** A crew member's static profile (fictional). */
export interface CrewProfile {
  crew: CrewMember;
  age: number;
  nationality: string;
  height_cm: number;
  blood_type: string;
  background: string;
  career: { days_in_space: number; evas: number; eva_hours: number };
  missions: { name: string; year: number; days: number }[];
  allergies: string[];
  medications: string[];
  history: HistoryItem[];
}

export interface Symptom {
  id: string;
  label: string;
  organ: string;
  red_flag: boolean;
}

export interface BadgeDef {
  id: string;
  name: string;
  icon: string;
  description: string;
}

export interface EscalationTier {
  tier: 0 | 1 | 2;
  name: string;
  who: string;
  when: string;
  action: string;
}

export interface Faq {
  id: string;
  q: string;
  a: string[];
}

export interface ProtocolStepCue {
  rate_per_min: number;
  source: string;
}

export interface ProtocolStep {
  id: string;
  title: string;
  detail: string;
  auto?: boolean;
  cue?: ProtocolStepCue | null;
}

export interface Protocol {
  id: string;
  name: string;
  icon: string;
  summary: string;
  pre: ProtocolStep[];
  tracks: { id: string; label: string; steps: ProtocolStep[] }[];
  post: ProtocolStep[];
  note: string;
}

export interface Catalog {
  mission: { name: string; summary: string; launch_utc: string };
  hazards: Hazard[];
  metrics: MetricDef[];
  organs: OrganDef[];
  environments: Environment[];
  crew: CrewMember[];
  symptoms: Symptom[];
  badges: BadgeDef[];
  levels: string[];
  xp_per_level: number;
  escalation: EscalationTier[];
  faq: Faq[];
  protocols: Protocol[];
  career_limit_msv: number;
  status_label: Record<Status, string>;
  sources: Record<string, SourceRef>;
  contexts: MeasureContext[];
}

export interface Clock {
  met_s: number;
  day: number;
  time: string;
  label: string;
}

export interface Band {
  ok: [number, number];
  watch: [number, number];
  ok2: [number, number] | null;
  watch2: [number, number] | null;
}

export interface Trend {
  direction: 'rising' | 'falling' | 'stable';
  quality: 'worsening' | 'improving' | 'neutral';
}

/** A body system's state on the dashboard. */
export interface SystemState {
  id: string;
  status: Status;
  metrics: string[];
  /** Symptoms reported in the latest symptom check that belong to this system (they raise its status). */
  symptoms?: string[];
  /** Every reading of the system is missing or too old. */
  stale?: boolean;
}

export interface MetricState {
  metric: string;
  has_data: boolean;
  status: Status;
  personal: boolean;
  value: number | null;
  value2: number | null;
  display: string;
  meta?: { items?: string[] } | null;
  day?: number;
  time?: string;
  age_days: number | null;
  source?: string;
  baseline: number | null;
  baseline2?: number | null;
  delta: number | null;
  z?: number | null;
  slope?: number;
  trend: Trend;
  persistence?: { watch_days: number; act_days: number };
  spark: number[];
  band?: Band;
  change_pct?: number;
  /** True when there is no reading, or the last one is too old to describe the crew member now (dashboard only). */
  stale?: boolean;
  /** Graded on a rolling average rather than the last reading (exercise, fluids). */
  basis?: { days: number; average: number } | null;
  /** Today's newest post-exercise / post-EVA reading, when newer than the resting one. */
  active_reading?: ActiveReading | null;
}

export interface Insight {
  id: string;
  severity: Status;
  title: string;
  body: string;
  metrics: string[];
  organ: string | null;
  actions: string[];
  /** The ids of the NASA documents behind this insight. */
  sources: string[];
}

export type TaskState = 'done' | 'due' | 'overdue' | 'upcoming';

export interface Task extends TaskDef {
  state: TaskState;
  logged: string[];
  weekly: boolean;
  done_at: string | null;
  on_time: boolean;
  /** For a check not done yet: the XP finishing it now pays (base, timing, streak, Full orbit when last). */
  xp_now?: number;
}

export interface Routine {
  day: number;
  tasks: Task[];
  done: number;
  total: number;
  overdue: number;
  next: Task | null;
}

export interface Game {
  xp: number;
  level: number;
  title: string;
  level_xp: number;
  xp_per_level: number;
  streak: number;
  /** The streak a check finished today extends. */
  streak_before_today: number;
  /** XP earned so far today. */
  xp_today: number;
  badges: (BadgeDef & { earned: boolean })[];
  earned_count: number;
  crew_goal: {
    done: number;
    total: number;
    target: number;
    reward: string;
    per_crew: { crew_id: string; initials: string; hue: number; done: number; total: number }[];
    reached_days: number[];
  };
  challenge: { title: string; detail: string; value: number; target: number };
}

/** The active solar particle event, as shown on the radiation card. */
export interface SolarEvent {
  status: Status;
  label: string;
  source: string;
  actions: string[];
  event_id: string | null;
  event_time?: string | null;
  instruments?: string | null;
  link?: string | null;
  /** True when the dose shown is ASTRA's illustrative figure, not a DONKI measurement. */
  illustrative?: boolean;
  illustrative_note?: string | null;
  in_shelter?: boolean;
  shelter_until_s?: number;
  shelter_label?: string;
  event_remaining_label?: string;
}

export interface Radiation {
  mission_msv: number;
  career_msv: number;
  limit_msv: number;
  percent: number;
  status: Status;
  rate_msv_day: number;
  /** Set when the dose rate came from a real NASA measurement rather than the catalog. */
  rate_source?: string | null;
  /** The cited document ids behind the dose rate (empty when it is a planning estimate). */
  rate_docs?: string[];
  margin_days: number | null;
  solar: SolarEvent;
  shelter: string;
}

export type PacketStatus = 'in_transit' | 'delivered' | 'replied';

export interface Packet {
  id: number;
  crew_id: string;
  crew_name: string;
  initials: string;
  hue: number;
  kind: 'alert' | 'message' | 'emergency' | 'cmo';
  priority: number;
  title: string;
  body: string;
  delay_s: number;
  env_id: string;
  created: string;
  elapsed_s: number;
  status: PacketStatus;
  progress: number;
  eta_s: number;
  reply: string | null;
  reply_eta_s: number | null;
}

export interface Conjunction {
  /** "warning": the blackout is coming (Watch). "blackout": the Sun blocks the link (Act). */
  phase?: 'warning' | 'blackout';
  status?: Status;
  days_until?: number;
  days_left?: number;
  blackout_days?: number;
  starts?: string;
  ends?: string;
  sot_deg: number;
  threshold_deg: number;
  date: string;
  label: string;
  detail: string;
  warning_days: number;
  source: string;
}

export interface Comms {
  env_id: string;
  env_name: string;
  delay_s: number;
  delay_label: string;
  round_trip_label: string;
  live: boolean;
  delay_note: string;
  next_window: { time: string; in_s: number };
  light_time_source?: string | null;
  utc?: string;
  conjunction?: Conjunction | null;
  ground: Packet[];
  cmo: Packet[];
}

/** The cabin air picture, from the real ISS telemetry in the NASA EDA. */
export interface Cabin {
  available: boolean;
  spark_label?: string;
  status?: Status;
  status_label?: string;
  co2_1h_mmhg?: number;
  co2_7d_mmhg?: number;
  unit?: string;
  act_1h_mmhg?: number;
  watch_7d_mmhg?: number;
  temp_c?: number;
  rh_pct?: number;
  spark?: number[];
  series_start?: string;
  series_end?: string;
  mission_day?: number;
  source?: string;
  sources?: string[];
  guide?: string;
}

export interface Eva {
  status: 'go' | 'caution' | 'nogo';
  reasons: string[];
}

export interface AttentionAction {
  label: string;
  href: string;
}

export interface AttentionCounts {
  act: number;
  watch: number;
  stale: number;
  open: number;
  acknowledged: number;
}

export interface AttentionItem {
  key: string;
  crew_id: string;
  severity: 'act' | 'watch';
  title: string;
  reason: string;
  action: AttentionAction;
  source: string;
  age: number;
  stale: boolean;
  state: 'open' | 'acknowledged' | 'resolved';
  acknowledged_by?: string | null;
  acknowledged_at?: number | null;
  resolved_by?: string | null;
  resolved_at?: number | null;
  note?: string | null;
  escalation_tier?: number | null;
}

export interface AttentionQueueData {
  crew_id?: string | null;
  counts: AttentionCounts;
  items: AttentionItem[];
  history: AttentionItem[];
}

export interface Dashboard {
  crew: CrewMember;
  env: Environment;
  clock: Clock;
  readiness: number;
  overall: Status;
  overall_label: string;
  eva: Eva;
  metrics: Record<string, MetricState>;
  organs: SystemState[];
  insights: Insight[];
  routine: Routine;
  game: Game;
  radiation: Radiation;
  comms: Comms;
  cabin: Cabin;
  attention: AttentionQueueData;
}

export interface SeriesPoint {
  day: number;
  value: number;
  value2: number | null;
  status: Status;
  display: string;
  time: string;
  items?: string[] | null;
}

export interface Series {
  metric: string;
  unit: string;
  days: number;
  today: number;
  points: SeriesPoint[];
  baseline: number | null;
  baseline2: number | null;
  band: Band;
  axis: [number, number];
  state: MetricState;
  log: { id: number; day: number; time: string; display: string; status: Status; task_id: string | null; source: string;
    items?: string[] | null }[];
  stats: { min: number | null; max: number | null; mean: number | null; days_ok: number; days_watch: number;
    days_act: number };
}

export interface Evaluation {
  metric: string;
  label: string;
  unit: string;
  value: number;
  value2: number | null;
  meta: { items?: string[]; context?: string } | null;
  display: string;
  status: Status;
  status_label: string;
  personal: boolean;
  z: number | null;
  baseline: number | null;
  baseline2: number | null;
  delta_text: string;
  band: Band;
  persistence: { watch_days: number; act_days: number };
  tier: 0 | 1 | 2;
  tier_name: string;
  tier_reasons: string[];
  escalation: string;
  guidance: string;
  red_flags: string[];
  suggest_emergency: boolean;
  /** The measurement context ASTRA graded the reading in (null for metrics that don't depend on it). */
  context?: MeasureContext['id'] | null;
  context_label?: string | null;
  context_inferred?: boolean;
  context_note?: string | null;
  /** True when the reading was taken after exertion: recovery ranges, no baseline comparison. */
  active?: boolean;
  recheck_after_min?: number | null;
}

export interface SaveResult {
  evaluation: Evaluation;
  task: { id: string; title: string; completed: boolean; remaining: string[] } | null;
  xp_gained: number;
  badges_unlocked: BadgeDef[];
  /** Re-measured after a Watch or Act result (value-neutral +10 XP). */
  loop_closed?: boolean;
  /** Personal quests finished by this reading. */
  quests_completed?: string[];
  /** Every XP line this save earned (base, on time, streak, full orbit, welcome back, loop, quests), in order. */
  xp_breakdown?: { amount: number; reason: string }[];
  /** Set when this save took the person to a new level. */
  level_up?: { level: number; title: string } | null;
  packet: Packet | null;
}

export interface CrewRow {
  crew: CrewMember;
  readiness: number;
  overall: Status;
  eva: Eva;
  flags: { metric: string; status: Status; display: string }[];
  top_insight: Insight | null;
  done: number;
  total: number;
  level: number;
  streak: number;
  organs: SystemState[];
}

export interface CrewOverview {
  clock: Clock;
  crew: CrewRow[];
  comms: Comms;
  ship_sense: ShipSenseData;
}

/** Ship Sense: the crew-wide check for a shared cause (the cabin air) behind symptoms several crew report. */
export interface ShipSenseData {
  /** Cabin telemetry exists here (the real ISS series is used at the station). */
  available: boolean;
  cabin: {
    status: Status;
    status_label: string;
    co2_1h_mmhg: number;
    co2_7d_mmhg: number;
    act_1h_mmhg: number;
    watch_7d_mmhg: number;
    source: string;
    spark: number[];
  } | null;
  /** Crew ids with a headache logged in the last 24 hours. */
  symptom_crew: string[];
  /** "It's the air, not you", when two or more crew share the symptom and the cabin is out of range. */
  insight: Insight | null;
}

export interface ReadingInput {
  metric: string;
  value?: number | null;
  value2?: number | null;
  meta?: { items?: string[]; context?: string } | null;
  task_id?: string | null;
}

export type ActionResult<T> = { ok: true; data: T } | { ok: false; error: string };

// ---------------------------------------------------------------- NASA data

export type NasaRole = 'threshold' | 'context' | 'replay' | 'evidence';
export type NasaStatus = 'ready' | 'pending' | 'error';
export type NasaSlot = 'A' | 'B' | 'C' | null;

/** One entry of the NASA source manifest. */
export interface NasaSource {
  id: string;
  agency: string;
  title: string;
  url: string;
  role: NasaRole;
  hazards: string[];
  targets: string[];
  files: string[];
  fetched: string | null;
  license: string;
  status: NasaStatus;
  slot: NasaSlot;
  note: string;
  /** False when a file listed in the manifest is missing from disk. */
  files_ok: boolean;
}

export interface NasaSources {
  sources: NasaSource[];
  counts: { total: number; ready: number; pending: number; slots_pending: number };
  data_dir: string;
}

export type SourceKind = 'evidence_report' | 'standard' | 'paper' | 'web';

/** One citable NASA document, from the catalog. */
export interface SourceRef {
  id: string;
  title: string;
  org: string;
  url: string;
  kind: SourceKind;
  year: number;
  note: string;
}

/** One Inspiration4 analyte series. */
export interface LabSeries {
  id: string;
  label: string;
  unit: string;
  why: string;
  ref_low: number | null;
  ref_high: number | null;
  /** True when crew members are held to different reference ranges (they differ by sex). */
  ranges_differ?: boolean;
  points: {
    subject: string;
    day: number;
    timepoint: string;
    value: number;
    status: Status;
    ref_low?: number | null;
    ref_high?: number | null;
  }[];
}

/** The catalogue entry for one analyte, with the reference range the dataset carries. */
export interface LabAnalyte {
  id: string;
  label: string;
  unit: string;
  metric: string;
  sources: string[];
  why: string;
  ref_low: number | null;
  ref_high: number | null;
}

export interface Inspiration4 {
  available: boolean;
  analytes: LabAnalyte[];
  subjects: string[];
  series: LabSeries[];
  days: number[];
  flight_window: { from: number | null; to: number | null };
  source: string;
  sources: string[];
}

// ---------------------------------------------------------------- mission simulator
export interface SimGauge {
  id: string;
  label: string;
  value: number | string;
  unit: string;
  status: Status | null;
  note: string | null;
}

export interface SimFrame {
  t: number;
  label: string;
  sublabel: string;
  status: Status;
  gauges: SimGauge[];
  guidance: { title: string; actions: string[] } | null;
  hold_ms?: number;
}

export type SimTone = 'accent' | 'muted' | 'ok' | 'watch' | 'act';

export interface SimChart {
  id: string;
  label: string;
  unit: string;
  y_min: number;
  y_max: number;
  series: { id: string; label: string; tone: SimTone; dashed: boolean; points: [number, number | null][] }[];
  thresholds: { value: number; label: string; status: Status }[];
  markers: { t: number; label: string; status: Status }[];
}

export interface SimEvent {
  t: number;
  frame: number;
  status: Status;
  kind: 'data' | 'astra' | 'comms' | 'crew';
  title: string;
  detail: string;
  source?: string;
  link?: string | null;
  major?: boolean;
}

export type SimStatus = 'ready' | 'pending' | 'unavailable' | 'ready-unwired';

export interface SimSummary {
  id: string;
  title: string;
  kicker: string;
  summary: string;
  status: SimStatus;
  env_id: string | null;
  sources: string[];
  datasets: string[];
  frames: number;
  events: number;
}

export interface SimScenario extends Omit<SimSummary, 'frames' | 'events'> {
  frame_ms: number;
  frames: SimFrame[];
  charts: SimChart[];
  events: SimEvent[];
  x_ticks: { t: number; label: string }[];
  x_label?: string;
  x_scale?: 'linear' | 'ordinal';
  real: string[];
  illustrative: string[];
}

export interface SimLiveScenarioInfo {
  id: string;
  name: string;
  kicker: string;
  description: string;
}

export interface SimLiveStatus {
  active: boolean;
  scenario: string;
  scenario_info: SimLiveScenarioInfo;
  scenarios: SimLiveScenarioInfo[];
  interval_s: number;
  step: number;
  crew_id: string;
  countdown_s: number;
  last_event: string;
  updated_metrics: string[];
}

// ---------------------------------------------------------------- official challenge resources (slots A-C)
export type CoverageLevel = 'monitored' | 'supported' | 'partial';

export interface OfficialRisk {
  id: string;
  category: string;
  title: string;
  url: string;
  summary: string;
  hazards: HazardId[];
  roadmap_source: string;
  level: CoverageLevel;
  how: string;
  metrics: { id: string; label: string }[];
  organs: { id: string; label: string }[];
  features: { label: string; href: string }[];
}

export interface OfficialStudy {
  id: string;
  group: string;
  name: string;
  url: string;
  summary: string;
  risks: { id: string; title: string }[];
  metrics: { id: string; label: string }[];
  link: string | null;
  how: string;
}

export interface OfficialHazard {
  id: HazardId;
  name: string;
  url: string;
  video: string;
  facts: string[];
}

/** The five official Space Apps resources and ASTRA's coverage of them (`GET /nasa/official`). */
export type OfficialResources =
  | { available: false }
  | {
      available: true;
      listed_on: string;
      retrieved: string;
      resources: { id: string; title: string; url: string; challenge_note: string; agency: string; slot: string; date?: string }[];
      hazards: OfficialHazard[];
      compound_note: string;
      levels: Record<CoverageLevel, string>;
      categories: { id: string; name: string }[];
      risks: OfficialRisk[];
      coverage: { total: number } & Record<CoverageLevel, number>;
      research: { groups: { id: string; name: string }[]; studies: OfficialStudy[] };
      csa: {
        radiation_facts: { text: string; url: string }[];
        instruments: { id: string; name: string; years: string; url: string; what: string }[];
        body_effects: { system: string; organs: string[]; text: string }[];
        body_effects_url: string;
        earth_benefits: string[];
      };
      sources: NasaSource[];
    };
