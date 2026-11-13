'use client';

import { radioGroupKeys } from '@/lib/a11y';
import { motion } from 'motion/react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, useTransition } from 'react';
import { finishEmergency, startEmergency } from '@/app/actions';
import { clockTime, cx, duration } from '@/lib/format';
import { play } from '@/lib/sound';
import type { CrewMember, Environment, Protocol, ProtocolStep } from '@/lib/types';
import { Icon } from '../ui/Icon';
import { Check, CircleCheck, Info, LoaderCircle, RadioTower, Siren, Target, X } from '../ui/icons';
import { useToast } from '../ui/Toast';
import { EmergencyRunView } from './EmergencyRunView';
import { CrewAvatar } from '../ui/CrewAvatar';
import { Select } from '../ui/Select';
import s from './emergency.module.css';

type Stage = 'pick' | 'run' | 'done';

const STORAGE_KEY = 'astra_emergency_active';

interface SavedSession {
  emergencyId: number;
  protocolId: string;
  patientId: string;
  isDrill: boolean;
  t0: number;
  track: string | null;
  checked: Record<string, number>;
  currentStepIndex: number;
}

export function EmergencyRunner({
  protocols,
  crew,
  me,
  env,
}: {
  protocols: Protocol[];
  crew: CrewMember[];
  me: CrewMember;
  env: Environment;
}) {
  const router = useRouter();
  const toast = useToast();
  const [stage, setStage] = useState<Stage>('pick');
  const [protocolId, setProtocolId] = useState(protocols[0].id);
  const [patientId, setPatientId] = useState(crew.find((c) => c.id !== me.id)?.id ?? me.id);
  const [isDrill, setIsDrill] = useState(false);
  const [emergencyId, setEmergencyId] = useState<number | null>(null);
  const [t0, setT0] = useState(0);
  const [now, setNow] = useState(0);
  const [track, setTrack] = useState<string | null>(protocols[0].tracks[0]?.id ?? null);
  const [checked, setChecked] = useState<Record<string, number>>({});
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [result, setResult] = useState<{
    duration: number;
    completed: boolean;
    badge: boolean;
    isDrill: boolean;
    sent: boolean;
  } | null>(null);
  const [pending, start] = useTransition();

  // Resume state initialized from sessionStorage
  const [resumeState, setResumeState] = useState<SavedSession | null>(() => {
    if (typeof window === 'undefined') return null;
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as SavedSession;
        if (parsed.emergencyId && parsed.protocolId && parsed.patientId && parsed.t0) {
          return parsed;
        }
      }
    } catch {
      // sessionStorage unavailable
    }
    return null;
  });
  const [confirmDiscardModal, setConfirmDiscardModal] = useState(false);

  const protocol = protocols.find((p) => p.id === protocolId) ?? protocols[0];
  const patient = crew.find((c) => c.id === patientId) ?? me;

  // Save session to sessionStorage while running
  useEffect(() => {
    if (stage !== 'run' || emergencyId === null) return;
    try {
      const state: SavedSession = {
        emergencyId,
        protocolId,
        patientId,
        isDrill,
        t0,
        track,
        checked,
        currentStepIndex,
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // sessionStorage unavailable
    }
  }, [stage, emergencyId, protocolId, patientId, isDrill, t0, track, checked, currentStepIndex]);

  // Timer loop while running
  useEffect(() => {
    if (stage !== 'run') return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [stage]);

  // Window beforeunload guard while running
  useEffect(() => {
    if (stage !== 'run') return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [stage]);

  const elapsed = stage === 'run' ? Math.max(0, (now - t0) / 1000) : 0;

  const currentTrack = protocol.tracks.find((t) => t.id === track) ?? protocol.tracks[0];
  const required = [...protocol.pre, ...(currentTrack ? currentTrack.steps : []), ...protocol.post];
  const doneCount = required.filter((st) => checked[st.id] !== undefined).length;
  const complete = required.length > 0 && doneCount >= required.length;

  const handleResume = () => {
    if (!resumeState) return;
    setProtocolId(resumeState.protocolId);
    setPatientId(resumeState.patientId);
    setIsDrill(resumeState.isDrill);
    setEmergencyId(resumeState.emergencyId);
    setT0(resumeState.t0);
    setNow(Date.now());
    setTrack(resumeState.track);
    setChecked(resumeState.checked);
    setCurrentStepIndex(resumeState.currentStepIndex ?? 0);
    setStage('run');
    setResumeState(null);
    // No toast here: the run view covers toasts, so one would only surface later on the result screen.
  };

  const handleDiscardResume = () => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {}
    setResumeState(null);
    setConfirmDiscardModal(false);
    toast({
      tone: 'info',
      title: 'Previous protocol discarded',
      body: 'You can now select and start a fresh protocol.',
    });
  };

  const initiateBegin = () => {
    if (resumeState) {
      setConfirmDiscardModal(true);
      return;
    }
    executeBegin();
  };

  const executeBegin = () => {
    setConfirmDiscardModal(false);
    start(async () => {
      const res = await startEmergency(protocol.id, patient.id);
      if (!res.ok) {
        toast({ tone: 'warning', title: 'Could not log the emergency', body: res.error });
        return;
      }
      const auto = Object.fromEntries(protocol.post.filter((p) => p.auto).map((p) => [p.id, 0]));
      setEmergencyId(res.data.emergency_id);
      setChecked(auto);
      const defaultTrack = protocol.tracks[0]?.id ?? null;
      setTrack(defaultTrack);
      setCurrentStepIndex(0);
      const t = Date.now();
      setT0(t);
      setNow(t);
      setStage('run');
      // A real emergency gets the high-priority alarm burst (once); a drill the calmer Act pattern.
      play(isDrill ? 'act' : 'emergency');
      // No toast while the protocol runs: the run view covers toasts, and its Earth bar already shows
      // "Alert sent" with the arrival countdown.
    });
  };

  const end = () =>
    start(async () => {
      const dur = elapsed;
      const steps = Object.entries(checked).map(([id, t]) => ({ id, t: Math.round(t) }));
      let badge = false;
      // Whether Mission Control actually got the record: the result note must not claim it when it did not.
      let sent = false;
      if (emergencyId !== null) {
        const res = await finishEmergency(emergencyId, {
          track,
          completed: complete,
          duration_s: Math.round(dur),
          steps,
          is_drill: isDrill,
        });
        sent = res.ok;
        if (res.ok && res.data.badges_unlocked.length) {
          badge = true;
          toast({ tone: 'reward', title: 'Badge unlocked: Drill Ready', body: '+50 XP for completing the drill' });
        } else if (res.ok) {
          toast({
            tone: 'info',
            title: `${isDrill ? 'Drill' : 'Emergency'} ${complete ? 'completed' : 'ended early'}`,
            // Only duration and step count are sent (see the result note), not the step timeline.
            body: 'Completion record sent to Mission Control.',
          });
        }
      }
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {}
      setResumeState(null);
      setResult({ duration: dur, completed: complete, badge, isDrill, sent });
      setStage('done');
      router.refresh();
    });

  const handleStepDone = (st: ProtocolStep) => {
    setChecked((c) => ({
      ...c,
      [st.id]: c[st.id] !== undefined ? c[st.id] : elapsed,
    }));
  };

  const handleStepReopen = (st: ProtocolStep) => {
    if (st.auto) return;
    setChecked((c) => {
      const next = { ...c };
      delete next[st.id];
      return next;
    });
  };

  const handleTrackChange = (newTrackId: string) => {
    setTrack(newTrackId);
  };

  /* ------------------------------------------------------------------ PICK STAGE */
  if (stage === 'pick') {
    const resumeProto = resumeState ? protocols.find((p) => p.id === resumeState.protocolId) : null;
    const resumePat = resumeState ? crew.find((c) => c.id === resumeState.patientId) : null;

    return (
      <div className={s.pick}>
        {/* Resume card if unfinished protocol exists in sessionStorage */}
        {resumeState && resumeProto ? (
          <aside className={s.resumeBanner} role="region" aria-label="Unfinished protocol available to resume">
            <div className={s.resumeInfo}>
              <span className={cx(s.resumePill, resumeState.isDrill ? s.drillPill : s.emergencyPill)}>
                {resumeState.isDrill ? 'TRAINING DRILL IN PROGRESS' : 'EMERGENCY IN PROGRESS'}
              </span>
              <h2 className={s.resumeTitle}>{resumeProto.name}</h2>
              <p className={s.resumeMeta}>
                Patient: <b>{resumePat?.name ?? 'Crew member'}</b> ·{' '}
                {Object.keys(resumeState.checked).length} steps logged so far
              </p>
            </div>
            <div className={s.resumeActionGroup}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleResume}
                aria-label={`Resume active ${resumeState.isDrill ? 'drill' : 'emergency'} protocol`}
              >
                Resume protocol
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={handleDiscardResume}
                aria-label="Discard unfinished protocol"
              >
                Discard
              </button>
            </div>
          </aside>
        ) : null}

        {/* Modal if user tries to start new protocol while one is already active */}
        {confirmDiscardModal ? (
          <div className={s.discardOverlay} role="dialog" aria-modal="true" aria-labelledby="discard-title">
            <div className={s.discardCard}>
              <h3 id="discard-title">Unfinished protocol is active</h3>
              <p>
                An unfinished emergency protocol is stored from an earlier session. Starting a new protocol will
                discard it. Do you want to continue?
              </p>
              <div className={s.discardBtns}>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={executeBegin}
                  disabled={pending}
                >
                  Discard & Start New
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setConfirmDiscardModal(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        ) : null}

        <div className={s.banner}>
          <Siren size={22} />
          <div>
            <h1 className={s.bannerTitle}>Emergency protocols</h1>
            <span>Step-by-step guidance that works without Earth. Choose what is happening and who is affected.</span>
          </div>
        </div>

        <div className={s.protocols} role="radiogroup" aria-label="Emergency type" onKeyDown={radioGroupKeys} tabIndex={-1}>
          {protocols.map((p) => (
            <button
              key={p.id}
              type="button"
              role="radio"
              aria-checked={p.id === protocolId}
              className={cx(s.protocol, p.id === protocolId && s.on)}
              onClick={() => {
                setProtocolId(p.id);
                setTrack(p.tracks[0]?.id ?? null);
              }}
            >
              <span className={s.pIcon}>
                <Icon name={p.icon} size={26} />
              </span>
              <b>{p.name}</b>
              <small>{p.summary}</small>
              {p.id === protocolId ? (
                <span className={s.tick}>
                  <Check size={14} />
                </span>
              ) : null}
            </button>
          ))}
        </div>

        <div className={s.startRow}>
          <div className={cx(s.field, s.patient)}>
            <span className="overline" id="patient-label">
              Patient
            </span>
            <Select
              aria-labelledby="patient-label"
              showDescription
              value={patientId}
              onChange={setPatientId}
              options={crew.map((c) => ({
                value: c.id,
                label: `${c.title} ${c.name}`,
                description: c.role,
                tag: c.id === me.id ? 'You' : undefined,
                leading: <CrewAvatar member={c} size={30} />,
              }))}
            />
          </div>

          <div className={s.field}>
            <span className="overline" id="mode-label">
              Mode
            </span>
            {/* Real or drill: a two-way switch, so the mode is visible before Start, not a lone checkbox. */}
            <div
              className={s.modeSwitch}
              role="radiogroup"
              aria-labelledby="mode-label"
              onKeyDown={radioGroupKeys}
              tabIndex={-1}
            >
              {(
                [
                  { drill: false, icon: Siren, title: 'Real', hint: 'Alerts crew + Earth' },
                  { drill: true, icon: Target, title: 'Drill', hint: 'Practice · +50 XP' },
                ] as const
              ).map((m) => {
                const on = isDrill === m.drill;
                return (
                  <button
                    key={m.title}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    aria-label={`${m.title}. ${m.hint}`}
                    tabIndex={on ? 0 : -1}
                    className={cx(s.modeOpt, on && (m.drill ? s.modeDrill : s.modeReal))}
                    onClick={() => setIsDrill(m.drill)}
                  >
                    <m.icon size={18} aria-hidden />
                    <span>
                      <b>{m.title}</b>
                      <small>{m.hint}</small>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className={cx(s.field, s.goField)}>
            <span className="overline" aria-hidden="true">
              &nbsp;
            </span>
            <button
              type="button"
              className={cx('btn btn-lg', isDrill ? 'btn-primary' : 'btn-danger', s.go)}
              onClick={initiateBegin}
              disabled={pending}
            >
              {pending ? <LoaderCircle size={18} className="spin" /> : <Siren size={18} />}{' '}
              {isDrill ? 'Start drill' : 'Start protocol'}
            </button>
          </div>

          <p className={s.linkInfo}>
            <RadioTower size={16} aria-hidden />
            <span>
              {env.delay_s < 5 ? (
                <>Live link to Mission Control from the {env.name}.</>
              ) : (
                <>
                  Earth is <b>{duration(env.delay_s)}</b> away. A reply takes at least{' '}
                  <b>{duration(env.delay_s * 2 + 90)}</b>, so this protocol runs on board.
                </>
              )}
            </span>
          </p>
        </div>

        <p className={s.note}>
          <Info size={15} /> Demo protocols in generic first-aid style for the hackathon. Not medical advice. Real crews
          follow agency-approved checklists.
        </p>
      </div>
    );
  }

  /* ------------------------------------------------------------------ RUN STAGE */
  if (stage === 'run') {
    return (
      <EmergencyRunView
        protocol={protocol}
        patient={patient}
        env={env}
        isDrill={isDrill}
        elapsed={elapsed}
        track={track}
        onTrackChange={handleTrackChange}
        checked={checked}
        onStepDone={handleStepDone}
        onStepReopen={handleStepReopen}
        currentStepIndex={currentStepIndex}
        onNavigateStep={setCurrentStepIndex}
        onEnd={end}
        pending={pending}
      />
    );
  }

  /* ------------------------------------------------------------------ DONE STAGE */
  if (stage === 'done' && result) {
    return (
      <motion.div className={cx('card', s.done, 'print-area')} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <span className={s.doneIcon}>{result.completed ? <CircleCheck size={34} /> : <X size={34} />}</span>
        <h2>
          {result.isDrill
            ? result.completed
              ? 'Drill completed'
              : 'Drill ended early'
            : result.completed
              ? 'Protocol completed'
              : 'Protocol ended early'}
        </h2>
        <p className="muted">
          {protocol.name} for {patient.title} {patient.name} · {clockTime(result.duration)} elapsed ·{' '}
          {Object.keys(checked).length} steps logged
        </p>
        <ol className={s.timeline}>
          {[...protocol.pre, ...(protocol.tracks.find((t) => t.id === track)?.steps ?? []), ...protocol.post]
            .filter((st) => checked[st.id] !== undefined)
            .toSorted((a, b) => checked[a.id] - checked[b.id])
            .map((st) => (
              <li key={st.id}>
                <span className="num">T+{clockTime(checked[st.id])}</span>
                {st.title}
              </li>
            ))}
        </ol>
        <p className={s.doneNote}>
          {!result.sent
            ? result.isDrill
              ? `Drill ${result.completed ? 'completed' : 'ended early'}. The practice record could not be sent to Mission Control.`
              : 'The record could NOT be sent to Mission Control. Read the timeline above to the flight surgeon as soon as you can, keep caring for the patient and follow ground guidance when it arrives.'
            : result.isDrill
            ? result.completed
              ? 'Drill completed. A practice record (duration and number of steps) was sent to Mission Control. Keep skills fresh with regular drills.'
              : 'Drill ended early. A practice record (duration and number of steps) was sent to Mission Control.'
            : result.completed
              ? 'A completion record (duration and number of steps) was sent to Mission Control with priority. The full step-by-step timeline above has not been sent: print it or read it out to the flight surgeon. Keep caring for the patient and follow ground guidance when it arrives.'
              : 'An early-termination record (duration and number of steps) was sent to Mission Control. The full timeline above has not been sent: print it or read it out to the flight surgeon.'}
        </p>
        {result.badge ? (
          <div style={{ marginTop: 8 }}>
            <span className="chip chip-ok">Drill Ready badge unlocked (+50 XP)</span>
          </div>
        ) : null}
        <div className="row wrap no-print" style={{ justifyContent: 'center', marginTop: 8 }}>
          <button type="button" className="btn btn-primary" onClick={() => window.print()}>
            Print timeline
          </button>
          <Link href="/crew" className="btn btn-ghost">
            Open comms
          </Link>
          <button type="button" className="btn btn-ghost" onClick={() => setStage('pick')}>
            New protocol
          </button>
        </div>
      </motion.div>
    );
  }

  return null;
}
