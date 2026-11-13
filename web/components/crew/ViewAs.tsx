'use client';

import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import { setCrew } from '@/app/actions';
import { cx } from '@/lib/format';
import { Eye, LoaderCircle } from '../ui/icons';

/**
 * Switch the app to this crew member's view.
 * `compact` (crew cards): small "View as" button. `block` (profile): full-width button that names the person.
 */
export function ViewAs({
  id,
  name,
  current,
  variant = 'compact',
  className,
}: {
  id: string;
  name: string;
  current: boolean;
  variant?: 'compact' | 'block';
  className?: string;
}) {
  const [pending, start] = useTransition();
  const router = useRouter();
  const block = variant === 'block';
  // "Dr. Kenji Arai" -> "Kenji"
  const first = name.split(' ').find((w) => !w.endsWith('.')) ?? name;

  if (current) {
    return block ? (
      <span className={cx('btn btn-tonal', className)} style={{ cursor: 'default' }}>
        <Eye size={16} aria-hidden /> Viewing as {first}
      </span>
    ) : (
      <span className="chip chip-accent">Viewing</span>
    );
  }
  return (
    <button
      type="button"
      className={cx('btn', block ? 'btn-ghost' : 'btn-ghost btn-sm', className)}
      aria-label={`View as ${name}`}
      onClick={() =>
        start(async () => {
          await setCrew(id);
          // Stay on this page; the header, Today and Measure now follow this person. The header's crew button
          // confirms the switch with a short note.
          router.refresh();
        })
      }
      disabled={pending}
    >
      {pending ? <LoaderCircle size={16} className="spin" /> : block ? <Eye size={16} aria-hidden /> : null}
      {block ? `View as ${first}` : 'View as'}
    </button>
  );
}
