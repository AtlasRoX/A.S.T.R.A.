'use server';

import { revalidatePath } from 'next/cache';
import { cookies } from 'next/headers';
import {
  EngineError,
  postEmergencyFinish,
  postEmergencyStart,
  postEvaluate,
  postMessage,
  postReading,
  getSimLiveStatus,
  postAttentionAck,
  postAttentionResolve,
  postPerkApprove,
  postCrewWatchRun,
} from '@/lib/engine';
import { CREW_COOKIE, ENV_COOKIE, getSession, isCrewId, isEnvId } from '@/lib/session';
import type { CrewWatchRun, ActionResult, Evaluation, Packet, ReadingInput, SaveResult, SimLiveStatus } from '@/lib/types';

const YEAR = 60 * 60 * 24 * 365;

async function run<T>(fn: () => Promise<T>): Promise<ActionResult<T>> {
  try {
    return { ok: true, data: await fn() };
  } catch (e) {
    const message = e instanceof EngineError ? e.message : 'Something went wrong. Please try again.';
    return { ok: false, error: message };
  }
}

export async function setCrew(id: string) {
  if (!isCrewId(id)) return;
  (await cookies()).set(CREW_COOKIE, id, { path: '/', maxAge: YEAR, sameSite: 'lax' });
  revalidatePath('/', 'layout');
}

export async function setEnvironment(id: string) {
  if (!isEnvId(id)) return;
  (await cookies()).set(ENV_COOKIE, id, { path: '/', maxAge: YEAR, sameSite: 'lax' });
  revalidatePath('/', 'layout');
}

export async function evaluateReading(input: ReadingInput): Promise<ActionResult<Evaluation>> {
  const { crew, env } = await getSession();
  return run(() => postEvaluate(crew, env, input));
}

export async function saveReading(input: ReadingInput): Promise<ActionResult<SaveResult>> {
  const { crew, env } = await getSession();
  const res = await run(() => postReading(crew, env, input));
  if (res.ok) revalidatePath('/', 'layout');
  return res;
}

export async function sendGroundMessage(text: string): Promise<ActionResult<Packet>> {
  const { crew, env } = await getSession();
  const res = await run(() => postMessage(crew, env, text));
  if (res.ok) revalidatePath('/crew');
  return res;
}

export async function startEmergency(protocolId: string, patientId: string) {
  const { crew, env } = await getSession();
  return run(() => postEmergencyStart(crew, patientId, protocolId, env));
}

export async function finishEmergency(
  id: number,
  body: {
    track: string | null;
    completed: boolean;
    duration_s: number;
    steps: { id: string; t: number }[];
    is_drill?: boolean;
  },
) {
  const { crew, env } = await getSession();
  const res = await run(() => postEmergencyFinish(id, { crew_id: crew, env, ...body }));
  if (res.ok) revalidatePath('/', 'layout');
  return res;
}

/** Whether ASTRA Core's background telemetry is running and when its next reading lands (read-only). */
export async function getLiveSimulationStatus(): Promise<ActionResult<SimLiveStatus>> {
  return run(() => getSimLiveStatus());
}

export async function approvePerk(
  week: number,
  days: number,
): Promise<ActionResult<{ ok: boolean; week: number; days: number; approved_by: string }>> {
  const { crew } = await getSession();
  const res = await run(() => postPerkApprove(crew, week, days));
  // Crew rewards show on the Crew page (and approvals on profiles' Progress), so refresh the crew pages.
  if (res.ok) revalidatePath('/crew', 'layout');
  return res;
}

export async function acknowledgeAttention(
  key: string,
): Promise<ActionResult<{ ok: boolean; key: string; state: string; xp_gained?: number }>> {
  const { crew } = await getSession();
  const res = await run(() => postAttentionAck(key, crew));
  if (res.ok) revalidatePath('/', 'layout');
  return res;
}

export async function resolveAttention(
  key: string,
  note: string,
): Promise<ActionResult<{ ok: boolean; key: string; state: string }>> {
  const { crew } = await getSession();
  const res = await run(() => postAttentionResolve(key, crew, note));
  if (res.ok) revalidatePath('/', 'layout');
  return res;
}

/** Run ASTRA's on-board Crew Watch agent once. */
export async function runCrewWatch(): Promise<ActionResult<CrewWatchRun>> {
  const { env } = await getSession();
  const res = await run(() => postCrewWatchRun(env));
  if (res.ok) revalidatePath('/crew');
  return res;
}
