'use client';

import { useEffect, useState, useTransition } from 'react';
import { runCrewWatch } from '@/app/actions';
import { cx } from '@/lib/format';
import type { AgentPhase, CrewWatchRun } from '@/lib/types';
import { Brain, LoaderCircle, Play, ScanEye, Send, ShieldCheck } from '../ui/icons';
import { SoundCue } from '../ui/SoundCue';
import { useToast } from '../ui/Toast';
import s from './crew.module.css';

const PHASE: Record<AgentPhase, { label: string; Icon: typeof Brain }> = {
  sense: { label: 'Sense', Icon: ScanEye },
  check: { label: 'Check', Icon: ShieldCheck },
  decide: { label: 'Decide', Icon: Brain },
  act: { label: 'Act', Icon: Send },
};
/** Steps appear one after another so the crew can follow the agent's reasoning. */
const STEP_MS = 420;

/**
 * Crew Watch: ASTRA's on-board agent. It acts without being asked: it senses a shared symptom, calls tools for the
 * crew's vitals and the cabin air, decides between a shared cause and separate patients, then tells the crew what to
 * fix and writes the flight-surgeon handover stamped with the signal delay. No network and no language model: the
 * planner is ASTRA's own rules, so it keeps working through a blackout and every step is explainable.
 */
export function CrewWatch({ initial }: { initial: CrewWatchRun | null }) {
  const [runData, setRun] = useState(initial);
  const [shown, setShown] = useState(initial ? initial.steps.length : 0);
  const [pending, start] = useTransition();
  const toast = useToast();

  useEffect(() => {
    if (!runData || shown >= runData.steps.length) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const t = setTimeout(() => setShown(reduce ? runData.steps.length : shown + 1), reduce ? 0 : STEP_MS);
    return () => clearTimeout(t);
  }, [runData, shown]);

  const go = () =>
    start(async () => {
      const res = await runCrewWatch();
      if (!res.ok) return toast({ tone: 'warning', title: 'Crew Watch could not run', body: res.error });
      setShown(0);
      setRun(res.data);
    });

  const done = runData && shown >= runData.steps.length;
  const d = runData?.decision;

  return (
    <section className={cx('card', s.agent, done && d && `st-${d.severity}`)} aria-labelledby="agent-h" aria-busy={pending}>
      {done && d?.cause === 'habitat' ? <SoundCue id={`agent:${runData.met_s}`} sound="insight" /> : null}
      <div className="card-head">
        <h2 id="agent-h" className="h-card">
          Crew Watch <span className={s.agentKind}>on-board agent</span>
        </h2>
        <button type="button" className="btn btn-primary" onClick={go} disabled={pending}>
          {pending ? <LoaderCircle size={15} className="spin" aria-hidden /> : <Play size={15} aria-hidden />}
          {pending ? 'Running' : runData ? 'Run again' : 'Run Crew Watch'}
        </button>
      </div>
      <p className={s.agentLead}>
        Acts without being asked: sense, check, decide, act. Runs on board with no network, so it keeps working
        through a blackout or a 44-minute round trip to Earth.
      </p>

      {runData ? (
        <ol className={s.agentSteps} aria-live="polite">
          {runData.steps.slice(0, shown).map((st) => {
            const { label, Icon } = PHASE[st.phase];
            return (
              <li key={st.n} className={cx(s.agentStep, `st-${st.status}`)}>
                <span className={s.agentPhase}>
                  <Icon size={14} aria-hidden />
                  {label}
                </span>
                <span className={s.agentTool}>{st.tool}</span>
                <span className={s.agentSum}>{st.summary}</span>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className={s.shipNone}>Not run yet on this mission day.</p>
      )}

      {done && runData.handover ? (
        <div className={s.agentHand}>
          <b>Handover to Earth</b>
          <span>
            {runData.handover.live
              ? 'Live link: flight surgeons see it now.'
              : `Arrives in ${runData.handover.one_way_label} · reply in about ${runData.handover.round_trip_label}. The crew is not waiting for it.`}
          </span>
        </div>
      ) : null}
      {done ? (
        <div className={s.shipFoot}>
          <span>
            {runData.steps.length} steps in {runData.elapsed_ms} ms · on board · network used: no
          </span>
        </div>
      ) : null}
    </section>
  );
}
