'use client';

import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import type { ExerciseDef } from '@/lib/types';
import { Pause, Play } from '../ui/icons';
import s from './exercise.module.css';

/*
 * An animated astronaut drawn in SVG, side view, facing right.
 *
 * Each exercise is a function of phase t (0..1, looping) that places the hips, torso, feet and hands; elbows and
 * knees are solved with two-bone inverse kinematics, so feet stay planted and hands stay on the bar whatever the
 * hips do. No external assets: it themes with the app and stops when the user prefers reduced motion.
 */

type P = [number, number];
interface Pose {
  hip: P;
  /** Torso lean from vertical, degrees; positive leans forward (right). */
  torso: number;
  /** Ankle positions, far leg first. */
  feet: [P, P];
  /** How far each heel is lifted, 0..1 (pivots on the toe). */
  heel?: [number, number];
  /** Hand targets, far arm first. */
  hands: [P, P];
  /** Equipment drawn under the figure. */
  bar?: P;
  crank?: { c: P; r: number; a: number };
  cable?: { from: P; to: P };
  belt?: number;
  /** Bar on the upper back (squat, heel raise): draw the plate behind the body, not over the face. */
  barBehind?: boolean;
  /** Lying on a bench: draw the bench and turn the head. */
  lying?: boolean;
  seat?: P;
}

const L = { torso: 50, neck: 7, head: 11, thigh: 40, shin: 40, foot: 15, upper: 29, fore: 27 };
const FLOOR = 178;
const rad = (d: number) => (d * Math.PI) / 180;
const ease = (t: number) => 0.5 - 0.5 * Math.cos(2 * Math.PI * t); // 0 -> 1 -> 0 over one loop
const mix = (a: number, b: number, k: number) => a + (b - a) * k;
const mixP = (a: P, b: P, k: number): P => [mix(a[0], b[0], k), mix(a[1], b[1], k)];

/**
 * Two-bone IK: the middle joint (knee or elbow) for a chain from `a` to target `t`. There are two solutions;
 * `prefer` scores them and the higher score wins (e.g. knees forward, elbows down).
 */
function ik(a: P, t: P, l1: number, l2: number, prefer: (j: P) => number): P {
  const dx = t[0] - a[0];
  const dy = t[1] - a[1];
  const d = Math.min(Math.hypot(dx, dy), l1 + l2 - 0.01);
  const base = Math.atan2(dy, dx);
  const off = Math.acos(Math.max(-1, Math.min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))));
  const at = (ang: number): P => [a[0] + l1 * Math.cos(ang), a[1] + l1 * Math.sin(ang)];
  const j1 = at(base + off);
  const j2 = at(base - off);
  return prefer(j1) >= prefer(j2) ? j1 : j2;
}

const shoulderOf = (p: Pose): P => [p.hip[0] + L.torso * Math.sin(rad(p.torso)), p.hip[1] - L.torso * Math.cos(rad(p.torso))];

/** A bar resting on the upper back: just behind and below the shoulder, along the torso. */
const onBack = (sh: P, torso: number): P => [sh[0] - 5 * Math.cos(rad(torso)) - 3 * Math.sin(rad(torso)), sh[1] - 5 * Math.sin(rad(torso)) + 3 * Math.cos(rad(torso))];

// ------------------------------------------------------------------ exercises
/** Hip position for a torso angle that puts the shoulder at `sh` (the chain is built from the bar outward). */
const hipFor = (sh: P, torso: number): P => [sh[0] - L.torso * Math.sin(rad(torso)), sh[1] + L.torso * Math.cos(rad(torso))];
const ANKLE = 118; // the planted feet; mid-foot is about 6 units in front of the ankle
const MIDFOOT = ANKLE + 6;
const FEET: [P, P] = [[ANKLE - 3, FLOOR - 4], [ANKLE + 3, FLOOR - 4]];
const ARM = L.upper + L.fore - 2; // a straight arm, elbow just unlocked

/*
 * Each pose follows the coaching cues for the lift:
 *  - squat: bar over mid-foot the whole way; at the bottom the thighs are level, shins ~30 deg forward, torso ~32 deg.
 *  - deadlift: arms hang vertical from the shoulders, so the bar rides up the shins over mid-foot; hips hinge back.
 *  - heel raise: knees straight, body rises on the balls of the feet, toes stay planted.
 *  - bench press: bar lowers to the lower chest and presses back up over the shoulders (a J-curve).
 *  - row: reach forward from the hips, finish leaning slightly back with the handle at the lower ribs.
 *  - run (T2): upright, quick steps landing under the hips, arms bent ~90 deg swinging opposite the legs.
 *  - cycle (CEVIS): no seat; the rider stands tall over the cranks, held by the clipped-in shoes.
 */
const POSES: Record<ExerciseDef['anim'], { period: number; pose: (t: number) => Pose }> = {
  squat: {
    period: 3.4,
    pose: (t) => {
      const k = ease(t);
      const torso = mix(6, 32, k);
      // Shoulder (and bar) stay over mid-foot; their height follows the depth.
      const sh: P = [mix(MIDFOOT - 2, MIDFOOT - 1, k), mix(50, 96, k)];
      const hip = hipFor(sh, torso);
      const bar = onBack(sh, torso);
      return { hip, torso, feet: FEET, hands: [[bar[0] + 7, bar[1] + 2], [bar[0] + 10, bar[1] + 3]], bar, barBehind: true };
    },
  },
  deadlift: {
    period: 3.6,
    pose: (t) => {
      const k = ease(t);
      const torso = mix(4, 56, k);
      const sh: P = [mix(MIDFOOT - 3, MIDFOOT + 4, k), mix(48, 96, k)];
      const hip = hipFor(sh, torso);
      const bar: P = [sh[0] - 1, sh[1] + ARM];
      return { hip, torso, feet: FEET, hands: [bar, [bar[0] + 2, bar[1]]], bar };
    },
  },
  heel_raise: {
    period: 2.4,
    pose: (t) => {
      const k = ease(t);
      const lift = 9 * k;
      const torso = 4;
      const sh: P = [MIDFOOT - 3, 50 - lift];
      const hip = hipFor(sh, torso);
      const bar = onBack(sh, torso);
      return {
        hip, torso, feet: [[FEET[0][0], FEET[0][1] - lift], [FEET[1][0], FEET[1][1] - lift]], heel: [k, k],
        hands: [[bar[0] + 7, bar[1] + 2], [bar[0] + 10, bar[1] + 3]], bar, barBehind: true,
      };
    },
  },
  press: {
    period: 3,
    pose: (t) => {
      const k = ease(t);
      // Lying on the back, head to the right; "torso" 90 lays the spine horizontal. Shoulders at x = 136.
      const hip: P = [86, 136];
      const bar: P = mixP([135, 80], [125, 122], k);
      return { hip, torso: 90, feet: [[58, FLOOR - 4], [63, FLOOR - 4]], hands: [bar, [bar[0] + 2, bar[1]]], bar, lying: true };
    },
  },
  row: {
    period: 3,
    pose: (t) => {
      const k = ease(t);
      const hip: P = [92, 158];
      const torso = mix(16, -10, k);
      // The reach stays inside the arm's length (56), so the elbow never snaps straight.
      const hand: P = mixP([150, 140], [116, 130], k);
      return { hip, torso, feet: [[148, 164], [152, 164]], hands: [hand, [hand[0] + 2, hand[1] + 2]], cable: { from: [hand[0] + 4, hand[1]], to: [184, 160] }, seat: [92, 164] };
    },
  },
  run: {
    period: 0.75,
    pose: (t) => {
      const a = 2 * Math.PI * t;
      const foot = (ph: number): P => [118 + 22 * Math.cos(a + ph), FLOOR - 4 - Math.max(0, 15 * Math.sin(a + ph))];
      const hip: P = [114, 100 - 3 * Math.abs(Math.sin(a))];
      const sh = shoulderOf({ hip, torso: 7 } as Pose);
      // Elbows ~90 deg: hands swing on an arc in front of the hip, opposite the same-side leg.
      const hand = (ph: number): P => [sh[0] + 14 * Math.cos(a + ph + Math.PI) + 6, sh[1] + 30 - 8 * Math.sin(a + ph + Math.PI)];
      return { hip, torso: 7, feet: [foot(Math.PI), foot(0)], hands: [hand(Math.PI), hand(0)], belt: t };
    },
  },
  cycle: {
    period: 1.1,
    pose: (t) => {
      const a = 2 * Math.PI * t;
      const c: P = [124, 158];
      const r = 15;
      const pedal = (ph: number): P => [c[0] + r * Math.cos(a + ph), c[1] + r * Math.sin(a + ph)];
      return { hip: [117, 100], torso: 12, feet: [pedal(Math.PI), pedal(0)], hands: [[148, 90], [150, 92]], crank: { c, r, a } };
    },
  },
};

// ------------------------------------------------------------------ drawing
/** A tapered capsule from `a` (radius r1) to `b` (radius r2): one body segment. */
function Capsule({ a, b, r1, r2, cls }: { a: P; b: P; r1: number; r2: number; cls: string }) {
  const d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  const n: P = [-(b[1] - a[1]) / d, (b[0] - a[0]) / d];
  const pts = [
    [a[0] + n[0] * r1, a[1] + n[1] * r1],
    [b[0] + n[0] * r2, b[1] + n[1] * r2],
    [b[0] - n[0] * r2, b[1] - n[1] * r2],
    [a[0] - n[0] * r1, a[1] - n[1] * r1],
  ];
  return (
    <g className={cls}>
      <polygon points={pts.map((q) => q.join(',')).join(' ')} />
      <circle cx={a[0]} cy={a[1]} r={r1} />
      <circle cx={b[0]} cy={b[1]} r={r2} />
    </g>
  );
}

/*
 * The ASTRA crew demonstrator (designed with the character-designer method):
 *  - brief: calm, capable, friendly crew member whose job is to show joint angles clearly at small sizes;
 *  - shape language: rounded rectangles (reliable) + circles (friendly); tapered limbs, thighs widest;
 *  - proportions: head 1 unit, body ~6.5 units, slightly stylised so the head reads at 240 px;
 *  - silhouette hooks: comms headset with mic boom, wrist heart-rate monitor;
 *  - palette: shirt #3159C9, shorts #1C2536, skin #D9A77F (+ shade), accent #F2A93B, white socks.
 * Far-side limbs are drawn a tone darker so the body reads in depth.
 */
function Figure({ p }: { p: Pose }) {
  const t = rad(p.torso);
  const up: P = [Math.sin(t), -Math.cos(t)];
  let fwd: P = [Math.cos(t), Math.sin(t)];
  if (p.lying) fwd = [-fwd[0], -fwd[1]];
  const at = (o: P, d: P, k: number): P => [o[0] + d[0] * k, o[1] + d[1] * k];
  const sh = shoulderOf(p);
  const neck = at(sh, up, L.neck);
  const head = at(neck, up, L.head);

  const leg = (ankle: P, heel = 0) => {
    const knee = ik(p.hip, ankle, L.thigh, L.shin, p.lying ? (j) => -j[1] : (j) => j[0]);
    const toe: P = [ankle[0] + L.foot * Math.cos(rad(-heel * 40)), ankle[1] + 3 + heel * 8];
    return { knee, ankle, toe };
  };
  const arm = (hand: P) => ({ elbow: ik(sh, hand, L.upper, L.fore, (j) => j[1] - 0.3 * j[0]), hand });

  const drawLeg = (l: ReturnType<typeof leg>, far: boolean) => (
    <g className={far ? s.farTone : undefined}>
      <Capsule a={l.knee} b={l.ankle} r1={5.2} r2={3.8} cls={s.skin} />
      <Capsule a={mixP(l.ankle, l.knee, 0.24)} b={l.ankle} r1={4.3} r2={4.3} cls={s.sock} />
      {/* trainer: dark upper, accent sole stripe */}
      <Capsule a={[l.ankle[0] - 2.5, l.ankle[1] + 1.5]} b={l.toe} r1={4.4} r2={3.6} cls={s.shoe} />
      <Capsule a={[l.ankle[0] - 3, l.ankle[1] + 4.6]} b={[l.toe[0] + 1, l.toe[1] + 2.4]} r1={1.2} r2={1.2} cls={s.accent} />
      <Capsule a={p.hip} b={l.knee} r1={7.4} r2={5.4} cls={s.skin} />
      <Capsule a={p.hip} b={mixP(p.hip, l.knee, 0.62)} r1={8.2} r2={7} cls={s.shorts} />
    </g>
  );
  const drawArm = (a: ReturnType<typeof arm>, far: boolean) => (
    <g className={far ? s.farTone : undefined}>
      <Capsule a={a.elbow} b={a.hand} r1={3.9} r2={3.2} cls={s.skin} />
      <Capsule a={sh} b={a.elbow} r1={4.8} r2={4} cls={s.skin} />
      <Capsule a={sh} b={mixP(sh, a.elbow, 0.5)} r1={6.2} r2={5.4} cls={s.shirt} />
      {!far ? <Capsule a={mixP(a.elbow, a.hand, 0.72)} b={mixP(a.elbow, a.hand, 0.86)} r1={3.6} r2={3.6} cls={s.accent} /> : null}
      <circle cx={a.hand[0]} cy={a.hand[1]} r={4.3} className={s.skinFill} />
    </g>
  );

  const [farLeg, nearLeg] = [leg(p.feet[0], p.heel?.[0]), leg(p.feet[1], p.heel?.[1])];
  const [farArm, nearArm] = [arm(p.hands[0]), arm(p.hands[1])];

  // Torso: rounded trapezoid, chest wider than waist; collar and mission patch.
  const pts = [at(p.hip, fwd, 8.5), at(sh, fwd, 10), at(sh, fwd, -10.5), at(p.hip, fwd, -9)];
  const torsoPath = `M${pts.map((q) => q.join(',')).join(' L')} Z`;
  const patch = at(at(sh, up, -11), fwd, 5);
  const collar = at(sh, up, 1.5);

  // Head in profile with a comms headset: hair cap, face, nose, eye, brow, headset band, ear cup, mic boom.
  const hairC = at(at(head, fwd, -1.8), up, 1.6);
  const faceC = at(head, fwd, 0.8);
  const nose = at(at(head, fwd, 10), up, -0.8);
  const eye = at(at(head, fwd, 6.2), up, 1.4);
  const brow1 = at(at(head, fwd, 4.6), up, 4.2);
  const brow2 = at(at(head, fwd, 8.2), up, 3.8);
  const cup = at(at(head, fwd, -4.6), up, -0.6);
  const bandTop = at(at(head, fwd, -2), up, 11.4);
  const mic = at(at(head, fwd, 8), up, -6.8);
  const feetX = (p.feet[0][0] + p.feet[1][0]) / 2;

  return (
    <g>
      {!p.lying && !p.seat ? <ellipse cx={feetX + 6} cy={FLOOR + 1} rx={28} ry={3.4} className={s.shadow} /> : null}
      {drawLeg(farLeg, true)}
      {drawArm(farArm, true)}
      <Capsule a={sh} b={neck} r1={4.2} r2={3.8} cls={s.skin} />
      <circle cx={p.hip[0]} cy={p.hip[1]} r={9} className={s.shortsFill} />
      <path d={torsoPath} className={s.shirtFill} />
      <circle cx={collar[0]} cy={collar[1]} r={4.6} className={s.collar} />
      <circle cx={patch[0]} cy={patch[1]} r={2.7} className={s.accentFill} />
      <circle cx={hairC[0]} cy={hairC[1]} r={10.9} className={s.hair} />
      <circle cx={faceC[0]} cy={faceC[1]} r={9.7} className={s.skinFill} />
      <circle cx={nose[0]} cy={nose[1]} r={2} className={s.skinFill} />
      <circle cx={eye[0]} cy={eye[1]} r={1.2} className={s.eye} />
      <line x1={brow1[0]} y1={brow1[1]} x2={brow2[0]} y2={brow2[1]} className={s.brow} />
      <path d={`M${cup.join(',')} Q${bandTop.join(',')} ${at(cup, up, 1).join(',')}`} className={s.band} />
      <line x1={cup[0]} y1={cup[1]} x2={mic[0]} y2={mic[1]} className={s.mic} />
      <circle cx={mic[0]} cy={mic[1]} r={1.6} className={s.accentFill} />
      <circle cx={cup[0]} cy={cup[1]} r={2.7} className={s.cup} />
      {drawLeg(nearLeg, false)}
      {drawArm(nearArm, false)}
    </g>
  );
}

function Plate({ at }: { at: P }) {
  return (
    <g>
      <circle cx={at[0]} cy={at[1]} r={13} className={s.plate} />
      <circle cx={at[0]} cy={at[1]} r={7.5} className={s.plateRing} />
      <circle cx={at[0]} cy={at[1]} r={2.6} className={s.barEnd} />
    </g>
  );
}

function Equipment({ p, under }: { p: Pose; under: boolean }) {
  if (under) {
    return (
      <g className={s.kit}>
        <line x1={20} y1={FLOOR} x2={220} y2={FLOOR} className={s.floor} />
        {p.bar && p.barBehind ? <Plate at={p.bar} /> : null}
        {p.belt !== undefined ? (
          <g>
            <rect x={60} y={FLOOR - 2} width={130} height={8} rx={4} className={s.machine} />
            {[0, 1, 2, 3, 4, 5].map((i) => {
              // Marks start between x 64 and 182, so each 8-unit mark ends by 190 where the belt does.
              const x = 64 + (((i * 118) / 6 - p.belt! * 118 + 1180) % 118);
              return <line key={i} x1={x} y1={FLOOR + 2} x2={x + 8} y2={FLOOR + 2} className={s.beltMark} />;
            })}
            {/* harness bungees pulling the runner onto the belt */}
            <line x1={p.hip[0]} y1={p.hip[1]} x2={70} y2={FLOOR - 2} className={s.bungee} />
            <line x1={p.hip[0]} y1={p.hip[1]} x2={176} y2={FLOOR - 2} className={s.bungee} />
          </g>
        ) : null}
        {p.lying ? <rect x={52} y={142} width={110} height={10} rx={4} className={s.machine} /> : null}
        {p.lying ? <line x1={70} y1={152} x2={70} y2={FLOOR} className={s.machineLine} /> : null}
        {p.lying ? <line x1={146} y1={152} x2={146} y2={FLOOR} className={s.machineLine} /> : null}
        {p.seat ? <rect x={p.seat[0] - 20} y={p.seat[1]} width={44} height={FLOOR - p.seat[1]} rx={3} className={s.machine} /> : null}
        {p.cable ? (
          <g>
            <rect x={176} y={150} width={30} height={FLOOR - 150} rx={4} className={s.machine} />
            <circle cx={191} cy={163} r={8} className={s.flywheel} />
          </g>
        ) : null}
        {p.crank ? (
          <g>
            <line x1={p.crank.c[0]} y1={p.crank.c[1]} x2={p.crank.c[0] + 8} y2={FLOOR} className={s.machineLine} />
            <line x1={p.crank.c[0]} y1={p.crank.c[1]} x2={150} y2={90} className={s.machineLine} />
            <line x1={143} y1={90} x2={157} y2={90} className={s.machineLine} />
            <circle cx={p.crank.c[0]} cy={p.crank.c[1]} r={p.crank.r + 5} className={s.flywheel} />
          </g>
        ) : null}
      </g>
    );
  }
  return (
    <g className={s.kit}>
      {p.bar && !p.barBehind ? <Plate at={p.bar} /> : null}
      {p.cable ? <line x1={p.cable.from[0]} y1={p.cable.from[1]} x2={p.cable.to[0]} y2={p.cable.to[1]} className={s.cable} /> : null}
      {p.crank ? (
        <g>
          {[0, Math.PI].map((ph) => {
            const x = p.crank!.c[0] + p.crank!.r * Math.cos(p.crank!.a + ph);
            const y = p.crank!.c[1] + p.crank!.r * Math.sin(p.crank!.a + ph);
            return <line key={ph} x1={p.crank!.c[0]} y1={p.crank!.c[1]} x2={x} y2={y} className={s.crankArm} />;
          })}
        </g>
      ) : null}
    </g>
  );
}

// ------------------------------------------------------------------ component
const noop = () => () => {};
const REDUCE_QUERY = '(prefers-reduced-motion: reduce)';
const reducedMotion = () => window.matchMedia(REDUCE_QUERY).matches;
function subscribeReducedMotion(cb: () => void) {
  const mq = window.matchMedia(REDUCE_QUERY);
  mq.addEventListener('change', cb);
  return () => mq.removeEventListener('change', cb);
}

export function AstroFigure({ anim, label }: { anim: ExerciseDef['anim']; label: string }) {
  const def = POSES[anim];
  const [t, setT] = useState(0.5);
  // Plays unless the user prefers less motion; the play button overrides either way.
  const reduce = useSyncExternalStore(subscribeReducedMotion, reducedMotion, () => true);
  const [choice, setChoice] = useState<boolean | null>(null);
  const playing = choice ?? !reduce;
  const [visible, setVisible] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  // Only animate while on screen.
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: '80px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!playing || !visible) return;
    let raf = 0;
    let last = performance.now();
    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      setT((x) => (x + dt / def.period) % 1);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, visible, def.period]);

  // Drawn only in the browser: Node and browsers round trig differently in the last digits, which would make the
  // server HTML and the first client render disagree. The server sends the empty frame at its final size.
  const mounted = useSyncExternalStore(noop, () => true, () => false);
  const pose = def.pose(t);
  return (
    <div ref={box} className={s.figureBox}>
      <svg viewBox="-6 -4 252 192" className={s.figure} role="img" aria-label={`Animation: ${label}`}>
        {mounted ? (
          <>
            <Equipment p={pose} under />
            <Figure p={pose} />
            <Equipment p={pose} under={false} />
          </>
        ) : null}
      </svg>
      <button
        type="button"
        className={s.playBtn}
        onClick={() => setChoice(!playing)}
        aria-label={playing ? `Pause ${label} animation` : `Play ${label} animation`}
        title={playing ? 'Pause' : 'Play'}
      >
        {playing ? <Pause size={14} /> : <Play size={14} />}
      </button>
    </div>
  );
}
