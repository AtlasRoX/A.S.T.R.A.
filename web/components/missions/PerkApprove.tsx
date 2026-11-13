'use client';

import { useRouter } from 'next/navigation';
import { useTransition } from 'react';
import { approvePerk } from '@/app/actions';
import { LoaderCircle } from '../ui/icons';
import { useToast } from '../ui/Toast';

/** The Commander's "Approve" button for an unlocked crew reward. */
export function PerkApprove({ week, days, name }: { week: number; days: number; name: string }) {
  const [pending, start] = useTransition();
  const router = useRouter();
  const toast = useToast();
  return (
    <button
      type="button"
      className="btn btn-sm btn-primary"
      disabled={pending}
      aria-label={`Approve: ${name}`}
      onClick={() =>
        start(async () => {
          const res = await approvePerk(week, days);
          if (res.ok) {
            toast({ tone: 'success', title: 'Reward approved', body: name });
            router.refresh();
          } else toast({ tone: 'warning', title: 'Could not approve', body: res.error });
        })
      }
    >
      {pending ? <LoaderCircle size={14} className="spin" /> : null} Approve
    </button>
  );
}
