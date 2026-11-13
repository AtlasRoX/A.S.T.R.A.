'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useTransition } from 'react';
import { LoaderCircle } from '../ui/icons';
import { Select } from '../ui/Select';

export function CompareSelect({
  options,
  value,
}: {
  options: { id: string; label: string; group?: string }[];
  value: string;
}) {
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  const [pending, start] = useTransition();
  // Grouped by body system, in the catalog's order; "Nothing" sits on its own at the top.
  const grouped = options.toSorted((a, b) => {
    const ga = options.findIndex((o) => o.group === a.group);
    const gb = options.findIndex((o) => o.group === b.group);
    return ga - gb;
  });
  return (
    <div className="row" style={{ gap: 8, fontSize: 13 }}>
      {pending ? (
        <LoaderCircle size={15} className="spin faint" />
      ) : (
        <span className="faint" id="compare-label">
          Compare with
        </span>
      )}
      <Select
        size="sm"
        aria-label="Compare with another indicator"
        menuWidth={260}
        value={value}
        options={[
          { value: '', label: 'Nothing' },
          ...grouped.map((o) => ({ value: o.id, label: o.label, group: o.group })),
        ]}
        onChange={(v) => {
          const q = new URLSearchParams(params.toString());
          if (v) q.set('c', v);
          else q.delete('c');
          start(() => router.replace(`${path}?${q.toString()}`, { scroll: false }));
        }}
      />
    </div>
  );
}
