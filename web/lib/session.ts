// Mission context (selected crew member + environment), stored in cookies so server pages can read it.
import { cookies } from 'next/headers';

export const CREW_COOKIE = 'astra_crew';
export const ENV_COOKIE = 'astra_env';
export const DEFAULT_CREW = 'ana';
export const DEFAULT_ENV = 'transit';

const CREW_IDS = new Set(['ana', 'kenji', 'sara', 'lucas']);
const ENV_IDS = new Set(['transit', 'station', 'rover', 'lunar', 'mars']);

export async function getSession(): Promise<{ crew: string; env: string }> {
  const jar = await cookies();
  const crew = jar.get(CREW_COOKIE)?.value;
  const env = jar.get(ENV_COOKIE)?.value;
  return {
    crew: crew && CREW_IDS.has(crew) ? crew : DEFAULT_CREW,
    env: env && ENV_IDS.has(env) ? env : DEFAULT_ENV,
  };
}

export const isCrewId = (id: string) => CREW_IDS.has(id);
export const isEnvId = (id: string) => ENV_IDS.has(id);
