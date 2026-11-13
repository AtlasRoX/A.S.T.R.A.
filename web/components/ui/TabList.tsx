'use client';

import type { ReactNode } from 'react';
import { tabListKeys } from '@/lib/a11y';

/**
 * A `role="tablist"` with arrow-key / Home / End navigation between its `role="tab"` children.
 * A client component so server pages (Trends) can use it too.
 */
export function TabList({ label, className, children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <div role="tablist" aria-label={label} className={className} onKeyDown={tabListKeys} tabIndex={-1}>
      {children}
    </div>
  );
}
