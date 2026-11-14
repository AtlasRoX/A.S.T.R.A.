// Server-side client for ASTRA Core (the Python engine). Only import from server code.
import { cache } from 'react';
import type {
  AttentionQueueData,
  Cabin,
  Catalog,
  Clock,
  Comms,
  CrewOverview,
  Dashboard,
  Evaluation,
  Inspiration4,
  NasaSources,
  OfficialResources,
  Packet,
  ReadingInput,
  Routine,
  SaveResult,
  Series,
  CrewProfile,
  ExercisePlan,
  GameHub,
  SimLiveStatus,
  CrewWatchRun,
} from './types';

import { ENGINE_URL, engineHeaders } from './engine-url';

export class EngineError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = 'EngineError';
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${ENGINE_URL}${path}`, {
      cache: 'no-store',
      ...init,
      headers: engineHeaders({ 'content-type': 'application/json', ...(init?.headers as Record<string, string>) }),
    });
  } catch {
    throw new EngineError(
      `ASTRA Core is offline. Start the engine (npm run dev from the project root) and retry.`,
      503,
    );
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = 'Please check the values you entered.';
    } catch {
      /* keep default */
    }
    throw new EngineError(detail, res.status);
  }
  return (await res.json()) as T;
}

const q = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined) s.set(k, String(v));
  const str = s.toString();
  return str ? `?${str}` : '';
};

export const getCatalog = cache(() => request<Catalog>('/catalog'));
export const getClock = cache(() => request<Clock>('/clock'));
export const getHealth = () => request<{ ok: boolean; service: string; clock: Clock }>('/health');
export const getDashboard = cache((crew: string, env: string) =>
  request<Dashboard>(`/crew/${crew}/dashboard${q({ env })}`),
);
export const getProfile = cache((crew: string) => request<CrewProfile>(`/crew/${crew}/profile`));
export const getExercise = cache((crew: string, env: string) =>
  request<ExercisePlan>(`/crew/${crew}/exercise${q({ env })}`),
);
export const getGame = cache((crew: string, env: string) => request<GameHub>(`/crew/${crew}/game${q({ env })}`));
export const getRoutine = cache((crew: string, env: string) =>
  request<Routine>(`/crew/${crew}/routine${q({ env })}`),
);
export const getSeries = (crew: string, metric: string, days: number) =>
  request<Series>(`/crew/${crew}/series/${metric}${q({ days })}`);
export const getCrewOverview = (env: string) => request<CrewOverview>(`/crew${q({ env })}`);
export const getComms = (env: string, crew?: string) => request<Comms>(`/comms${q({ env, crew_id: crew })}`);
export const getAttention = (crew?: string, env?: string) =>
  request<AttentionQueueData>(crew ? `/crew/${crew}/attention${q({ env })}` : `/attention${q({ env })}`);
export const postPerkApprove = (crewId: string, week: number, days: number) =>
  request<{ ok: boolean; week: number; days: number; approved_by: string }>(`/crew/${crewId}/perks/approve`, {
    method: 'POST',
    body: JSON.stringify({ week, days }),
  });
export const postAttentionAck = (key: string, crewId: string) =>
  request<{ ok: boolean; key: string; state: string; xp_gained?: number }>(`/attention/${key}/ack`, {
    method: 'POST',
    body: JSON.stringify({ crew_id: crewId }),
  });
export const postAttentionResolve = (key: string, crewId: string, note: string) =>
  request<{ ok: boolean; key: string; state: string }>(`/attention/${key}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ crew_id: crewId, note }),
  });

export const postEvaluate = (crew: string, env: string, input: ReadingInput) =>
  request<Evaluation>(`/crew/${crew}/evaluate`, { method: 'POST', body: JSON.stringify({ ...input, env }) });
export const postReading = (crew: string, env: string, input: ReadingInput) =>
  request<SaveResult>(`/crew/${crew}/readings`, { method: 'POST', body: JSON.stringify({ ...input, env }) });
export const postMessage = (crew: string, env: string, text: string) =>
  request<Packet>('/comms/messages', { method: 'POST', body: JSON.stringify({ crew_id: crew, env, text }) });
export const postEmergencyStart = (crew: string, patient: string, protocol: string, env: string) =>
  request<{ emergency_id: number; packet: Packet }>('/emergencies', {
    method: 'POST',
    body: JSON.stringify({ crew_id: crew, patient_id: patient, protocol_id: protocol, env }),
  });
export const postEmergencyFinish = (
  id: number,
  body: {
    crew_id: string;
    track: string | null;
    completed: boolean;
    duration_s: number;
    steps: unknown[];
    is_drill?: boolean;
    env?: string;
  },
) =>
  request<{ ok: boolean; badges_unlocked: { id: string; name: string }[]; xp_gained: number; packet?: Packet }>(
    `/emergencies/${id}/finish`,
    { method: 'POST', body: JSON.stringify(body) },
  );

// ---------------------------------------------------------------- NASA data
export const getNasaSources = cache(() => request<NasaSources>('/nasa/sources'));
export const getCabin = (env: string) => request<Cabin>(`/nasa/cabin${q({ env })}`);
export const getInspiration4 = cache(() => request<Inspiration4>('/nasa/inspiration4'));
export const getOfficial = cache(() => request<OfficialResources>('/nasa/official'));

// ---------------------------------------------------------------- background telemetry (ASTRA Core runs it)
export const getSimLiveStatus = () => request<SimLiveStatus>('/sim/live/status');

export const getCrewWatch = () => request<{ last: CrewWatchRun | null }>('/agent/crew-watch');
export const postCrewWatchRun = (env: string) =>
  request<CrewWatchRun>(`/agent/crew-watch/run${q({ env })}`, { method: 'POST' });
