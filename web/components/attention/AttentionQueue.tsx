'use client';

import Link from 'next/link';
import { useState, useTransition } from 'react';
import { acknowledgeAttention } from '@/app/actions';
import { Check, CheckCircle2, LoaderCircle, ShieldCheck } from '../ui/icons';
import { useToast } from '../ui/Toast';
import { AttentionItem } from './AttentionItem';
import type { AttentionItem as AttentionItemType, AttentionQueueData, Status } from '@/lib/types';
import s from './attention.module.css';

/** An indicator's latest value and recent readings, shown in the row that is about it. */
export interface AttentionTrend {
  label: string;
  value: string;
  unit: string;
  spark: number[];
  band: [number, number] | null;
  status: Status;
}

interface AttentionQueueProps {
  /** Latest value and trend per indicator id; rows about an indicator show its value and a sparkline. */
  trends?: Record<string, AttentionTrend>;
  initialData?: AttentionQueueData | null;
  wholeCrew?: boolean;
  isCmo?: boolean;
  currentUser?: string;
  className?: string;
}

interface Group {
  lead: AttentionItemType;
  related: AttentionItemType[];
}

/** The indicator an alert is about: from a reading's key, or from an insight's trend link. */
function metricOf(i: AttentionItemType): string | null {
  if (i.key.startsWith('metric:')) return i.key.split(':')[2] ?? null;
  return /[?&]m=([^&]+)/.exec(i.action.href)?.[1] ?? null;
}

/**
 * One row per crew member and indicator. "Fluid intake 1.8 L" and "Low fluids: kidney-stone risk" are the same
 * problem: the reading leads and the pattern behind it is shown inside the row.
 */
function groupItems(items: AttentionItemType[]): Group[] {
  const groups: Group[] = [];
  const byMetric = new Map<string, Group>();
  for (const item of items) {
    const metric = metricOf(item);
    const id = metric ? `${item.crew_id}:${metric}` : null;
    const group = id ? byMetric.get(id) : undefined;
    if (!group) {
      const created = { lead: item, related: [] };
      groups.push(created);
      if (id) byMetric.set(id, created);
    } else if (item.key.startsWith('metric:') && !group.lead.key.startsWith('metric:')) {
      group.related.unshift(group.lead);
      group.lead = item;
    } else {
      group.related.push(item);
    }
  }
  return groups;
}

/** Act before Watch; otherwise the engine's order. */
const rank = (g: Group) => ([g.lead, ...g.related].some((i) => i.severity === 'act') ? 0 : 1);

/** How many items the personal queue shows before "Show more". */
const PREVIEW = 4;

const CREW_NAMES: Record<string, string> = {
  ana: 'Ana Ribeiro · Commander',
  kenji: 'Kenji Arai · Crew Medical Officer',
  sara: 'Sara Okafor · Flight Engineer',
  lucas: 'Lucas Moreau · Mission Specialist',
  all: 'Habitat & Mission Environment',
};

/** One crew member's alerts on the crew page: the first few rows, every Act row, then "Show more". */
function CrewGroup({
  id,
  groups,
  isCmo,
  currentUser,
  onResolved,
  onAcknowledged,
}: {
  id: string;
  groups: Group[];
  isCmo: boolean;
  currentUser?: string;
  onResolved: (key: string) => void;
  onAcknowledged: (keys: string[]) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const [pending, start] = useTransition();
  const toast = useToast();
  const openKeys = groups.flatMap((g) => [g.lead, ...g.related]).filter((i) => i.state !== 'acknowledged').map((i) => i.key);
  const name = (CREW_NAMES[id] ?? id).split(' ')[0];
  const ackAll = () =>
    start(async () => {
      const results = await Promise.all(openKeys.map((k) => acknowledgeAttention(k)));
      const done = openKeys.filter((_, i) => results[i].ok);
      onAcknowledged(done);
      // Buddy-check XP is capped per day by ASTRA Core, so a bulk acknowledge pays at most the cap.
      const xp = results.reduce((sum, r) => sum + (r.ok ? (r.data.xp_gained ?? 0) : 0), 0);
      if (done.length < openKeys.length) toast({ tone: 'warning', title: 'Some alerts were not acknowledged', body: 'Try again.' });
      else toast({ tone: 'success', title: `Acknowledged ${done.length} alert${done.length === 1 ? '' : 's'} for ${name}`,
        body: xp ? `Buddy check · +${xp} XP` : undefined });
    });
  const limit = Math.max(PREVIEW, groups.filter((g) => rank(g) === 0).length);
  const visible = showAll ? groups : groups.slice(0, limit);
  const hidden = groups.length - visible.length;
  const listId = `attention-items-${id}`;
  return (
    <div className={s.crewGroup}>
      <div className={s.crewGroupHead}>
        <ShieldCheck size={16} />
        {id in CREW_NAMES && id !== 'all' ? (
          <Link href={`/crew/${id}`} className={s.crewGroupLink}>
            {CREW_NAMES[id]}
          </Link>
        ) : (
          <span>{CREW_NAMES[id] ?? id}</span>
        )}
        {openKeys.length ? (
          <span className={s.crewGroupCount} title="Open alerts for this crew member, not yet acknowledged">
            {openKeys.length}
          </span>
        ) : null}
        {openKeys.length > 1 ? (
          <button type="button" className={`btn btn-ghost btn-sm ${s.ackAll}`} onClick={ackAll} disabled={pending}>
            {pending ? <LoaderCircle size={14} className="spin" /> : <Check size={14} aria-hidden />} Acknowledge all ({openKeys.length})
          </button>
        ) : null}
      </div>
      <ul id={listId} className={s.itemsList}>
        {visible.map(({ lead, related }) => (
          <AttentionItem
            key={`${lead.key}:${lead.state}|${related.map((r) => `${r.key}:${r.state}`).join('|')}`}
            item={lead}
            related={related}
            isCmo={isCmo}
            currentUser={currentUser}
            onResolved={onResolved}
          />
        ))}
      </ul>
      {hidden > 0 || showAll ? (
        <button
          type="button"
          className={`btn btn-text btn-sm ${s.moreBtn}`}
          aria-expanded={showAll}
          aria-controls={listId}
          onClick={() => setShowAll(!showAll)}
        >
          {showAll ? 'Show fewer' : `Show ${hidden} more`}
        </button>
      ) : null}
    </div>
  );
}

export function AttentionQueue({
  initialData,
  wholeCrew = false,
  isCmo = false,
  currentUser,
  className,
  trends,
}: AttentionQueueProps) {
  const [items, setItems] = useState<AttentionItemType[]>(initialData?.items ?? []);

  const handleItemResolved = (key: string) => {
    setItems((prev) => prev.filter((i) => i.key !== key));
  };
  const handleAcknowledged = (keys: string[]) => {
    const set = new Set(keys);
    setItems((prev) =>
      prev.map((i) =>
        set.has(i.key) ? { ...i, state: 'acknowledged', acknowledged_by: currentUser ?? null, acknowledged_at: Date.now() / 1000 } : i,
      ),
    );
  };

  const [showAll, setShowAll] = useState(false);
  const [crewFilter, setCrewFilter] = useState<string>('all-crew');

  const sorted = groupItems(items).toSorted((a, b) => rank(a) - rank(b));
  // The personal queue shows the first few; every Act row stays visible.
  const limit = Math.max(PREVIEW, sorted.filter((g) => rank(g) === 0).length);
  const visible = showAll ? sorted : sorted.slice(0, limit);
  const hiddenCount = sorted.length - visible.length;

  const actCount = items.filter((i) => i.severity === 'act').length;
  const watchCount = items.filter((i) => i.severity === 'watch').length;
  const totalCount = actCount + watchCount;

  // Group items if wholeCrew
  const grouped: Record<string, AttentionItemType[]> = {};
  if (wholeCrew) {
    for (const item of items) {
      const cid = item.crew_id || 'all';
      if (!grouped[cid]) grouped[cid] = [];
      grouped[cid].push(item);
    }
  }

  return (
    <section id="attention-queue" aria-labelledby="attention-heading" className={`${s.queueCard} ${className ?? ''}`}>
      <div className={s.queueHead}>
        <div className={s.queueTitleGroup}>
          <h2 id="attention-heading" className={s.queueHeading}>
            {wholeCrew ? 'Crew attention queue' : 'Needs attention'}
          </h2>
        </div>

        <div className={s.countsRow} aria-label={`${actCount} Act, ${watchCount} Watch`}>
          {actCount > 0 ? (
            <span className={`${s.countPill} ${s.pillAct}`}>
              <span aria-hidden="true">■</span>
              <span>{actCount} Act</span>
            </span>
          ) : null}
          {watchCount > 0 ? (
            <span className={`${s.countPill} ${s.pillWatch}`}>
              <span aria-hidden="true">▲</span>
              <span>{watchCount} Watch</span>
            </span>
          ) : null}
        </div>
      </div>

      {totalCount === 0 ? (
        <div className={s.emptyState}>
          <div className={s.emptyStateNominal}>
            <CheckCircle2 size={18} />
            <span>Nothing needs attention</span>
          </div>
          <p style={{ margin: '4px 0 0 0' }}>All systems and readings are nominal. Keep up the routine checks.</p>
        </div>
      ) : wholeCrew ? (
        <div>
          {Object.keys(grouped).length > 1 ? (
            <div className={s.crewFilter} role="group" aria-label="Show alerts for">
              {[
                ['all-crew', items.length] as const,
                ...Object.entries(grouped).map(([cid, xs]) => [cid, xs.length] as const),
              ].map(([cid, n]) => (
                <button
                  key={cid}
                  type="button"
                  className={s.filterChip}
                  aria-pressed={crewFilter === cid}
                  onClick={() => setCrewFilter(cid)}
                >
                  {cid === 'all-crew' ? 'Everyone' : (CREW_NAMES[cid] ?? cid).split(' ')[0]}
                  {cid === currentUser ? ' (you)' : ''}
                  <span className={s.filterCount}>{n}</span>
                </button>
              ))}
            </div>
          ) : null}
          {Object.entries(grouped)
            .filter(([cid]) => crewFilter === 'all-crew' || crewFilter === cid)
            .map(([cid, crewItems]) => (
              <CrewGroup
                key={cid}
                id={cid}
                groups={groupItems(crewItems).toSorted((a, b) => rank(a) - rank(b))}
                isCmo={isCmo}
                currentUser={currentUser}
                onResolved={handleItemResolved}
                onAcknowledged={handleAcknowledged}
              />
            ))}
        </div>
      ) : (
        <>
          <ul id="attention-items" className={s.itemsList}>
            {visible.map(({ lead, related }) => (
              <AttentionItem
                key={`${lead.key}|${related.map((r) => r.key).join('|')}`}
                item={lead}
                related={related}
                trend={trends?.[metricOf(lead) ?? '']}
                isCmo={isCmo}
                currentUser={currentUser}
                onResolved={handleItemResolved}
              />
            ))}
          </ul>
          {hiddenCount > 0 || showAll ? (
            <button
              type="button"
              className={`btn btn-text btn-sm ${s.moreBtn}`}
              aria-expanded={showAll}
              aria-controls="attention-items"
              onClick={() => setShowAll(!showAll)}
            >
              {showAll ? 'Show fewer' : `Show ${hiddenCount} more`}
            </button>
          ) : null}
        </>
      )}
    </section>
  );
}
