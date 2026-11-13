import { ENGINE_URL, engineHeaders } from '@/lib/engine-url';
import { getSession } from '@/lib/session';

/**
 * Streams the ASTRA specialist's answer from ASTRA Core (NDJSON events: meta, delta, done).
 * Who is asking and where they are come from the session cookie, never from the browser's request body.
 */
export async function POST(request: Request) {
  const { crew, env } = await getSession();
  let body: { question?: unknown; history?: unknown; page?: unknown };
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: 'Invalid JSON' }, { status: 400 });
  }
  const question = typeof body.question === 'string' ? body.question.trim().slice(0, 2000) : '';
  if (!question) return Response.json({ error: 'Ask a question first' }, { status: 400 });
  // The app path the user is on (e.g. /crew/lucas), so "he" or "this trend" can be resolved. Paths only.
  const page = typeof body.page === 'string' && /^\/[\w\-/?=&.]*$/.test(body.page) ? body.page.slice(0, 200) : null;
  const history = Array.isArray(body.history)
    ? body.history
        .filter((m): m is { role: string; content: string } => typeof m?.role === 'string' && typeof m?.content === 'string')
        .slice(-20)
    : [];

  let res: Response;
  try {
    res = await fetch(`${ENGINE_URL}/assistant/chat`, {
      method: 'POST',
      headers: engineHeaders({ 'content-type': 'application/json' }),
      body: JSON.stringify({ crew_id: crew, env, question, history, page }),
      cache: 'no-store',
      signal: request.signal,
    });
  } catch {
    return Response.json({ error: 'ASTRA Core is unreachable.' }, { status: 502 });
  }
  if (!res.ok || !res.body) return Response.json({ error: `ASTRA Core error ${res.status}` }, { status: 502 });
  return new Response(res.body, {
    headers: { 'content-type': 'application/x-ndjson; charset=utf-8', 'cache-control': 'no-store' },
  });
}
