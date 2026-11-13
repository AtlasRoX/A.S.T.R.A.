'use client';

import { useEffect, useRef } from 'react';

/**
 * The indicator list on Trends. On narrow screens it is a sideways-scrolling chip row, so the selected
 * indicator can start off-screen: scroll the list itself (never the page) to bring it into view.
 */
export function IndicatorNav({
  active,
  className,
  children,
}: {
  /** The selected indicator's id; the list re-centres when it changes. */
  active: string;
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const nav = ref.current;
    const item = active ? nav?.querySelector<HTMLElement>('[aria-current="page"]') : null;
    if (!nav || !item) return;
    const n = nav.getBoundingClientRect();
    const r = item.getBoundingClientRect();
    // Sideways chip row: centre the chip. Vertical list: only scroll when the item is out of view.
    if (nav.scrollWidth > nav.clientWidth) nav.scrollLeft += r.left - n.left - (nav.clientWidth - r.width) / 2;
    if (r.top < n.top || r.bottom > n.bottom) nav.scrollTop += r.top - n.top - (nav.clientHeight - r.height) / 2;
  }, [active]);
  return (
    <nav ref={ref} className={className} aria-label="Indicators">
      {children}
    </nav>
  );
}
