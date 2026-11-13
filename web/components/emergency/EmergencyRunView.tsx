'use client';

import { radioGroupKeys } from '@/lib/a11y';
import { useEffect, useMemo, useRef, useState } from 'react';
import { clockTime, cx } from '@/lib/format';
import { play, setSoundFocus } from '@/lib/sound';
import type { CrewMember, Environment, Protocol, ProtocolStep } from '@/lib/types';
import { MetronomeCue } from './MetronomeCue';
import { Check, ChevronDown, ChevronUp, LoaderCircle, RotateCcw } from '../ui/icons';
import s from './emergency.module.css';

interface EmergencyRunViewProps {
  protocol: Protocol;
  patient: CrewMember;
  env: Environment;
  isDrill: boolean;
  elapsed: number;
  track: string | null;
  onTrackChange: (trackId: string) => void;
  checked: Record<string, number>;
  onStepDone: (step: ProtocolStep) => void;
  onStepReopen: (step: ProtocolStep) => void;
  currentStepIndex: number;
  onNavigateStep: (index: number) => void;
  onEnd: () => void;
  pending: boolean;
}

export function EmergencyRunView({
  protocol,
  patient,
  env,
  isDrill,
  elapsed,
  track,
  onTrackChange,
  checked,
  onStepDone,
  onStepReopen,
  currentStepIndex,
  onNavigateStep,
  onEnd,
  pending,
}: EmergencyRunViewProps) {
  const [holding, setHolding] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showDoneList, setShowDoneList] = useState(false);
  const stepHeadingRef = useRef<HTMLHeadingElement>(null);
  const holdStartRef = useRef<number | null>(null);
  const holdTimerRef = useRef<number | null>(null);
  // A completed hold already ended the protocol, so the click that follows the release is ignored.
  const holdCompletedRef = useRef(false);
  // When the confirm opened and which button opened it (focus returns there on close).
  const confirmOpenedAtRef = useRef(0);
  const confirmOpenerRef = useRef<HTMLElement | null>(null);
  const keepRunningRef = useRef<HTMLButtonElement>(null);

  // Derive active track and sequence of steps
  const activeTrack = useMemo(() => {
    return protocol.tracks.find((t) => t.id === track) ?? protocol.tracks[0];
  }, [protocol.tracks, track]);

  const allSteps: ProtocolStep[] = useMemo(() => {
    return [...protocol.pre, ...(activeTrack ? activeTrack.steps : []), ...protocol.post];
  }, [protocol.pre, activeTrack, protocol.post]);

  const clampedIndex = Math.min(Math.max(0, currentStepIndex), Math.max(0, allSteps.length - 1));
  const currentStep = allSteps[clampedIndex] ?? allSteps[0];
  const isCurrentDone = currentStep ? checked[currentStep.id] !== undefined : false;

  const doneCount = allSteps.filter((st) => checked[st.id] !== undefined).length;
  const complete = allSteps.length > 0 && doneCount >= allSteps.length;

  const arrive = Math.max(0, env.delay_s - elapsed);
  const reply = Math.max(0, env.delay_s * 2 + 90 - elapsed);
  const live = env.delay_s < 5;

  // Mark document body while emergency is running so shell header is hidden
  useEffect(() => {
    document.body.setAttribute('data-emergency-running', 'true');
    // Sound focus: only emergency and timer sounds while the protocol runs.
    setSoundFocus(true);
    return () => {
      document.body.removeAttribute('data-emergency-running');
      setSoundFocus(false);
    };
  }, []);

  // Two beeps when the alert reaches Earth: the crew hears the moment help knows, without looking at the bar.
  const arrived = !live && arrive === 0;
  const wasArrived = useRef(arrived);
  useEffect(() => {
    if (arrived && !wasArrived.current) play('step');
    wasArrived.current = arrived;
  }, [arrived]);

  // Focus step heading on index change without jarring scroll jumps
  useEffect(() => {
    if (currentStep?.id) {
      stepHeadingRef.current?.focus({ preventScroll: true });
    }
  }, [currentStep?.id]);

  // Confirm sheet: focus "Keep running" when it opens; Escape closes it and returns focus to the opener.
  useEffect(() => {
    if (!showConfirm) return;
    keepRunningRef.current?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      setShowConfirm(false);
      confirmOpenerRef.current?.focus({ preventScroll: true });
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [showConfirm]);

  const openConfirm = (opener: HTMLElement) => {
    if (pending || showConfirm) return;
    confirmOpenerRef.current = opener;
    confirmOpenedAtRef.current = Date.now();
    setShowConfirm(true);
  };

  const closeConfirm = () => {
    setShowConfirm(false);
    confirmOpenerRef.current?.focus({ preventScroll: true });
  };

  // Hold-to-end mechanism
  const cancelHold = () => {
    setHolding(false);
    setHoldProgress(0);
    if (holdTimerRef.current) {
      cancelAnimationFrame(holdTimerRef.current);
      holdTimerRef.current = null;
    }
    holdStartRef.current = null;
  };

  const startHold = () => {
    if (pending || showConfirm) return;
    holdCompletedRef.current = false;
    setHolding(true);
    setHoldProgress(0);
    const startT = Date.now();
    holdStartRef.current = startT;

    const tick = () => {
      const diff = Date.now() - startT;
      const pct = Math.min(100, (diff / 1000) * 100);
      setHoldProgress(pct);
      if (pct >= 100) {
        holdCompletedRef.current = true;
        cancelHold();
        onEnd();
      } else {
        holdTimerRef.current = requestAnimationFrame(tick);
      }
    };
    holdTimerRef.current = requestAnimationFrame(tick);
  };

  // Releasing early only cancels the hold. The confirm opens from the click that follows, so that
  // click cannot land on a "Yes" button drawn under the finger.
  const handleHoldClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (holdCompletedRef.current) return;
    openConfirm(e.currentTarget);
  };

  const handleDone = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (currentStep) {
      onStepDone(currentStep);
    }
    if (clampedIndex < allSteps.length - 1) {
      onNavigateStep(clampedIndex + 1);
    } else {
      // Last step: Done also finishes, through the same confirm as the hold button.
      openConfirm(e.currentTarget);
    }
  };

  const handleBack = () => {
    if (clampedIndex > 0) {
      onNavigateStep(clampedIndex - 1);
    }
  };

  const isLastStep = clampedIndex === allSteps.length - 1;

  // The situation is decided after the last "pre" step (e.g. checking breathing), so it is asked on the
  // first track step. Later steps show the chosen track with a way back to change it.
  const hasTracks = protocol.tracks.length > 1;
  const branchIndex = protocol.pre.length;
  const atBranch = hasTracks && clampedIndex === branchIndex;
  const pastBranch = hasTracks && clampedIndex > branchIndex;

  // Done steps for collapsible review
  const doneStepsList = useMemo(() => {
    return allSteps
      .map((st, idx) => ({ step: st, index: idx, timestamp: checked[st.id] }))
      .filter((item) => item.timestamp !== undefined);
  }, [allSteps, checked]);

  return (
    <div
      role="region"
      aria-label="Emergency protocol runner"
      className={s.runContainer}
    >
      {/* Polite live announcement */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        Step {clampedIndex + 1} of {allSteps.length}: {currentStep.title}. {currentStep.detail}
        {!live && reply <= 0 ? ' Earliest Earth reply window reached.' : ''}
      </div>

      {/* Red header band */}
      <header className={s.redBand}>
        <div className={s.redBandMain}>
          <div className={s.redBandPillRow}>
            <span
              className={cx(s.redBandPill, isDrill ? s.drillPill : s.emergencyPill)}
              aria-label={isDrill ? 'Training drill in progress' : 'Emergency protocol in progress'}
            >
              {isDrill ? 'TRAINING DRILL' : '■ EMERGENCY · ACT'}
            </span>
            <span className={s.redBandPatient}>
              Patient: <b>{patient.title} {patient.name}</b>
            </span>
          </div>
          <h1 className={s.redBandTitle}>{protocol.name}</h1>
        </div>

        <div className={s.redBandTimer} aria-live="off" title="Elapsed time since protocol start">
          <span className={s.timerOverline}>Elapsed</span>
          <b className={cx('num', s.timerValue)}>T+ {clockTime(elapsed)}</b>
        </div>
      </header>

      {/* Main step container */}
      <main className={s.stepContentArea}>
        {/* Current single step */}
        <section className={s.activeStepCard} aria-labelledby="current-step-heading">
          <div className={s.stepMetaRow}>
            <span className={s.stepCounter}>
              STEP {clampedIndex + 1} of {allSteps.length}
            </span>
            {isCurrentDone ? (
              <span className={s.stepDoneBadge}>
                <Check size={14} /> Completed T+{clockTime(checked[currentStep.id])}
              </span>
            ) : null}
          </div>

          {/* Track switch segmented control, asked only at the branch step */}
          {atBranch ? (
            <div className={s.trackChoiceWrap} role="radiogroup" aria-label="Protocol track" onKeyDown={radioGroupKeys} tabIndex={-1}>
              <span className={s.trackChoiceLabel}>Situation:</span>
              <div className={s.trackSegmented}>
                {protocol.tracks.map((t) => {
                  const isActive = t.id === activeTrack.id;
                  return (
                    <button
                      key={t.id}
                      type="button"
                      role="radio"
                      aria-checked={isActive}
                      className={cx(s.trackSegmentBtn, isActive && s.trackSegmentActive)}
                      onClick={() => onTrackChange(t.id)}
                    >
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          <h2
            id="current-step-heading"
            ref={stepHeadingRef}
            tabIndex={-1}
            className={s.currentStepHeading}
          >
            {currentStep.title}
          </h2>

          <p className={s.currentStepDetail}>{currentStep.detail}</p>

          {/* Optional metronome if step carries cue */}
          <MetronomeCue cue={currentStep.cue} />

          {/* CPR diagram if cardiac protocol and in CPR step */}
          {protocol.id === 'cardiac' && currentStep.id === 'a1' ? (
            <div className={s.stepDiagramWrap}>
              <CprInlineCard />
            </div>
          ) : null}

          {/* After the branch: the chosen situation as a chip that jumps back to the choice */}
          {pastBranch ? (
            <div className={s.reopenRow}>
              <button
                type="button"
                className={s.trackChip}
                onClick={() => onNavigateStep(branchIndex)}
                aria-label={`Situation: ${activeTrack.label}. Change situation`}
              >
                <span className={s.trackChipLabel}>Situation:</span> <b>{activeTrack.label}</b>
                <span className={s.trackChipChange}>Change</span>
              </button>
            </div>
          ) : null}

          {/* If step is done, allow reopening / redo */}
          {isCurrentDone && !currentStep.auto ? (
            <div className={s.reopenRow}>
              <button
                type="button"
                className={cx('btn btn-ghost btn-sm', s.reopenBtn)}
                onClick={() => onStepReopen(currentStep)}
                aria-label={`Mark step ${clampedIndex + 1} incomplete to redo it`}
              >
                <RotateCcw size={14} /> Reopen this step
              </button>
            </div>
          ) : null}
        </section>

        {/* Collapsible Steps so far */}
        {doneStepsList.length > 0 ? (
          <div className={s.doneCollapsibleCard}>
            <button
              type="button"
              className={s.doneCollapsibleHeader}
              onClick={() => setShowDoneList((v) => !v)}
              aria-expanded={showDoneList}
              aria-controls="done-steps-list"
            >
              <span>Steps so far ({doneStepsList.length})</span>
              {showDoneList ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>
            {showDoneList ? (
              <ol id="done-steps-list" className={s.doneStepsList}>
                {doneStepsList.map((item) => (
                  <li key={item.step.id}>
                    <button
                      type="button"
                      className={cx(s.doneStepItem, item.index === clampedIndex && s.doneStepActive)}
                      onClick={() => onNavigateStep(item.index)}
                      aria-label={`Go to step ${item.index + 1}: ${item.step.title}`}
                    >
                      <span className={s.doneStepTime}>T+{clockTime(item.timestamp)}</span>
                      <span className={s.doneStepTitle}>{item.step.title}</span>
                      <span className={s.doneStepReopen}>View ›</span>
                    </button>
                  </li>
                ))}
              </ol>
            ) : null}
          </div>
        ) : null}
      </main>

      {/* Docked bottom zone (64px actions + Earth bar) */}
      <div className={s.bottomDock}>
        {/* End/complete confirm: a sheet above the dock, so Back, Done and the hold button do not move.
            "Keep running" sits on the thumb side; "Yes" ignores clicks for 400ms after opening. */}
        {showConfirm ? (
          <div className={s.confirmBox} role="dialog" aria-modal="true" aria-labelledby="confirm-prompt-title">
            <div className={s.confirmInner}>
              <span id="confirm-prompt-title" className={s.confirmPromptText}>
                <b>{complete ? 'Complete protocol?' : 'End protocol early?'}</b>
                {!complete ? (
                  <span className={s.confirmSub}>
                    {allSteps.length - doneCount} of {allSteps.length} steps not done
                  </span>
                ) : null}
              </span>
              <div className={s.confirmBtnGroup}>
                <button
                  type="button"
                  className={cx('btn', complete ? 'btn-primary' : 'btn-danger')}
                  onClick={() => {
                    if (Date.now() - confirmOpenedAtRef.current < 400) return;
                    setShowConfirm(false);
                    onEnd();
                  }}
                  disabled={pending}
                >
                  {pending ? <LoaderCircle size={16} className="spin" /> : null} Yes, {complete ? 'complete' : 'end'}
                </button>
                <button
                  ref={keepRunningRef}
                  type="button"
                  className="btn btn-ghost"
                  onClick={closeConfirm}
                  disabled={pending}
                >
                  Keep running
                </button>
              </div>
            </div>
          </div>
        ) : null}

        <nav className={s.actionRow} aria-label="Step navigation">
          <button
            type="button"
            className={cx('btn btn-ghost', s.navBackBtn)}
            onClick={handleBack}
            disabled={clampedIndex === 0}
            aria-label="Go to previous step"
          >
            ◀ Back
          </button>
          <button
            type="button"
            className={cx('btn', isLastStep ? 'btn-primary' : 'btn-danger', s.navDoneBtn)}
            onClick={handleDone}
            aria-label={
              isLastStep ? (complete ? undefined : 'Done with final step, then finish') : 'Done with step, advance to next'
            }
          >
            {isLastStep && complete ? 'Finish protocol' : 'Done ✓'}
          </button>
        </nav>

        {/* Persistent Earth Bar at bottom */}
        <footer className={s.earthBar}>
          <div className={s.earthInfoCol}>
            <div className={s.earthTimersRow}>
              <span>
                {live ? (
                  <>Earth link: <b>Live</b></>
                ) : (
                  <>Alert arrives: <b>{arrive > 0 ? clockTime(arrive) : 'Arrived'}</b></>
                )}
              </span>
              <span className={s.dotSep} aria-hidden="true">·</span>
              <span>
                {live ? (
                  <>Reply: <b>Live on console</b></>
                ) : (
                  <>Earliest reply: <b>{reply > 0 ? clockTime(reply) : 'Any moment'}</b></>
                )}
              </span>
            </div>
            <div className={s.earthTransmissionStatus}>
              Alert sent T+00:00 ✓ · Completion: not sent yet
            </div>
          </div>

          <div className={s.earthActionArea}>
            {/* Secondary on purpose: Done is the one primary action. Enter/Space click it, which opens the confirm. */}
            <button
              type="button"
              className={cx('btn btn-ghost', s.holdBtn)}
              onPointerDown={startHold}
              onPointerUp={cancelHold}
              onPointerCancel={cancelHold}
              onPointerLeave={cancelHold}
              onClick={handleHoldClick}
              disabled={pending}
              aria-label={complete ? 'Hold 1 second to complete protocol' : 'Hold 1 second to end protocol early'}
            >
              <svg className={s.ringSvg} width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
                <circle className={s.ringBg} cx="14" cy="14" r="11" />
                <circle
                  className={s.ringFill}
                  cx="14"
                  cy="14"
                  r="11"
                  strokeDasharray={2 * Math.PI * 11}
                  strokeDashoffset={2 * Math.PI * 11 * (1 - holdProgress / 100)}
                />
              </svg>
              <span className={s.holdText}>
                {pending ? <LoaderCircle size={15} className="spin" /> : null}
                {holding
                  ? `Hold to ${complete ? 'complete' : 'end'}...`
                  : complete
                    ? 'Hold to complete'
                    : 'Hold to end protocol'}
              </span>
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

function CprInlineCard() {
  return (
    <div className={s.cprCard}>
      <span className="overline">CPR in weightlessness (Evetts–Russomano)</span>
      <svg viewBox="0 0 240 140" className={s.cprSvg} role="img" aria-label="Evetts-Russomano handstand CPR position">
        <line x1="10" y1="14" x2="230" y2="14" className={s.cprWall} />
        <line x1="10" y1="128" x2="230" y2="128" className={s.cprWall} />
        <text x="12" y="10">WALL</text>
        <text x="12" y="138">PATIENT ON RESTRAINT</text>
        <circle cx="42" cy="116" r="8" className={s.cprHeadRed} />
        <path d="M51 116 L182 116 M162 116 L194 111" className={s.cprPatientLine} />
        <path d="M124 16 L124 60 M110 16 L124 34" className={s.cprFigure} />
        <path d="M124 60 L124 94" className={s.cprFigure} />
        <circle cx="134" cy="92" r="7" className={s.cprHeadFig} />
        <path d="M124 78 L112 112 M124 78 L118 112" className={s.cprFigure} />
        <path d="M142 26 L142 54 M137 48 L142 54 L147 48" className={s.cprArrow} />
        <text x="150" y="40">push with legs</text>
        <text x="150" y="72">hands on chest</text>
      </svg>
      <p className={s.cprCaption}>
        <b>Evetts–Russomano method:</b> feet braced on the wall, push with the legs. Co-developed by Brazilian
        researcher Thais Russomano.
      </p>
    </div>
  );
}
