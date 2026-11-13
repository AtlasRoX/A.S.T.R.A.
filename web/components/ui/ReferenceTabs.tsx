'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cx } from '@/lib/format';
import s from './reference-tabs.module.css';

const TABS = [
  { href: '/learn', label: 'Guide', hint: 'Hazards, body systems, indicators' },
  { href: '/data', label: 'NASA data', hint: 'Datasets and cited documents' },
  { href: '/data/inspiration4', label: 'Real astronauts', hint: 'Inspiration4 blood panels' },
  { href: '/data/resources', label: 'Challenge resources', hint: 'The official NASA and CSA resources, mapped to ASTRA' },
] as const;

/** The Reference sections, so Library and Data read as one area instead of two competing tabs. */
export function ReferenceTabs() {
  const path = usePathname();
  const active = (href: string) => (href === '/data' ? path === '/data' : path === href);
  return (
    <nav className={s.tabs} aria-label="Reference sections">
      {TABS.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          className={cx(s.tab, active(t.href) && s.on)}
          aria-current={active(t.href) ? 'page' : undefined}
          title={t.hint}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
