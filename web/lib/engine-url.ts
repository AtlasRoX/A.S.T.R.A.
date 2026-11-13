/**
 * Where ASTRA Core lives and how the web server proves it is the web server.
 *
 * Server-only: every engine call happens on the server. When `ENGINE_TOKEN` is set (a deployed engine on a
 * public host), each request carries it, and ASTRA Core refuses requests without it. Locally both are unset.
 */
export const ENGINE_URL = process.env.ENGINE_URL ?? 'http://127.0.0.1:8000';

export function engineHeaders(extra?: HeadersInit): Record<string, string> {
  const headers: Record<string, string> = { ...(extra as Record<string, string> | undefined) };
  const token = process.env.ENGINE_TOKEN;
  if (token) headers['x-astra-token'] = token;
  return headers;
}
