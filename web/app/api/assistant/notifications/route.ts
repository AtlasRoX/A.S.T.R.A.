import { ENGINE_URL, engineHeaders } from '@/lib/engine-url';
import { getSession, isCrewId } from '@/lib/session';

/** The notification log for one crew member (their alerts, everyone's Act alerts, ground replies): the one in
 *  `?crew=` (the viewer the assistant panel shows), else whoever is signed in. */
export async function GET(req: Request) {
  const session = await getSession();
  const asked = new URL(req.url).searchParams.get('crew');
  const crew = asked && isCrewId(asked) ? asked : session.crew;
  const { env } = session;
  try {
    const res = await fetch(
      `${ENGINE_URL}/assistant/notifications?crew_id=${encodeURIComponent(crew)}&env=${encodeURIComponent(env)}`,
      { cache: 'no-store', headers: engineHeaders() },
    );
    if (!res.ok) return Response.json({ error: `ASTRA Core error ${res.status}` }, { status: 502 });
    return Response.json(await res.json(), { headers: { 'cache-control': 'no-store' } });
  } catch {
    return Response.json({ error: 'ASTRA Core is unreachable.' }, { status: 502 });
  }
}
