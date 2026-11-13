'use client';

import { PageError } from '@/components/PageError';

/**
 * Errors from a page's own data. The layout (header, navigation, mission strip) is outside this boundary,
 * so it stays on screen. When the engine is down, the layout itself shows the offline page instead.
 */
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  // Next redacts server error messages in production, so this can only be a hint; the wording is safe either way.
  const offline = /offline|fetch|ECONNREFUSED|not responding/i.test(error.message);
  return <PageError offline={offline} onRetry={reset} />;
}
