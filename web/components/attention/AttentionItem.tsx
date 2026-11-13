'use client';

import { useState, useTransition } from 'react';
import Link from 'next/link';
import { ReadingSource } from '../ui/ReadingSource';
import { Check, Link2, ShieldAlert, Siren, TriangleAlert } from '../ui/icons';
import { Sparkline } from '../charts/Sparkline';
import { acknowledgeAttention, resolveAttention } from '@/app/actions';
import { useToast } from '../ui/Toast';
import { play } from '@/lib/sound';
import type { AttentionItem as AttentionItemType } from '@/lib/types';
import type { AttentionTrend } from './AttentionQueue';
import s from './attention.module.css';

interface AttentionItemProps {
  item: AttentionItemType;
  isCmo?: boolean;
  currentUser?: string;
  onResolved?: (key: string) => void;
  /** Other alerts about the same indicator (for example a pattern behind this reading), shown inside this row. */
  related?: AttentionItemType[];
  /** The indicator's latest value and recent trend, when this row is about one. */
  trend?: AttentionTrend;
}

const NO_RELATED: AttentionItemType[] = [];

/** Crew ids are first names in lower case ("ana"); show them as names ("Ana"). */
const displayName = (id: string) => (id ? id.charAt(0).toUpperCase() + id.slice(1) : id);

/** Keep a number on the same line as its unit or noun ("7.5 h", "37.9 °C", "3 days"). */
const keepUnits = (text: string) => text.replace(/(\d) (?=[A-Za-z%°µ])/g, '$1\u00a0');

function formatAge(ageSeconds: number): string {
  if (ageSeconds < 60) return 'just now';
  if (ageSeconds < 3600) return `${Math.floor(ageSeconds / 60)} min ago`;
  if (ageSeconds < 86400) return `${Math.floor(ageSeconds / 3600)} h ago`;
  const days = Math.floor(ageSeconds / 86400);
  return `${days} ${days === 1 ? 'day' : 'days'} ago`;
}

export function AttentionItem({ item, isCmo = false, currentUser, onResolved, related = NO_RELATED, trend }: AttentionItemProps) {
  const [resolving, setResolving] = useState(false);
  const [resolveNote, setResolveNote] = useState('');
  const [localItem, setLocalItem] = useState(item);
  const [relatedAcked, setRelatedAcked] = useState(() => related.every((r) => r.state === 'acknowledged'));
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const toast = useToast();

  const isAct = localItem.severity === 'act' || related.some((r) => r.severity === 'act');
  const isAcked = localItem.state === 'acknowledged' && relatedAcked;
  const isResolved = localItem.state === 'resolved';
  // A reading row shows the indicator name with its value as a chip; insight rows keep their own title.
  const reading = trend && localItem.key.startsWith('metric:') ? trend : null;
  // Measure and Trends always follow the person viewing, so on a crewmate's row their links would measure or show
  // the viewer instead ("Measure again" would save the reading under the wrong name). Those rows open the
  // crewmate's profile; links to the shared Crew page stay.
  const crewmate =
    currentUser && localItem.crew_id && localItem.crew_id !== 'all' && localItem.crew_id !== currentUser
      ? localItem.crew_id
      : null;
  const followsViewer = (href: string) => crewmate !== null && !href.startsWith('/crew');
  const action = followsViewer(localItem.action.href)
    ? { label: 'Open profile', href: `/crew/${crewmate}` }
    : localItem.action;

  if (isResolved) return null;

  const handleAcknowledge = () => {
    setError(null);
    const prevItem = { ...localItem };
    const prevRelatedAcked = relatedAcked;
    // Acknowledging the row acknowledges every alert it holds.
    const keys = [
      ...(localItem.state === 'acknowledged' ? [] : [localItem.key]),
      ...(relatedAcked ? [] : related.filter((r) => r.state !== 'acknowledged').map((r) => r.key)),
    ];

    // Optimistic update
    setLocalItem((prev) => ({
      ...prev,
      state: 'acknowledged',
      acknowledged_by: currentUser ?? 'crew',
      acknowledged_at: Date.now() / 1000,
    }));
    setRelatedAcked(true);

    startTransition(async () => {
      const results = await Promise.all(keys.map((k) => acknowledgeAttention(k)));
      const failed = results.find((r) => !r.ok);
      if (failed) {
        // Rollback
        setLocalItem(prevItem);
        setRelatedAcked(prevRelatedAcked);
        setError(failed.error ?? 'Failed to acknowledge alert. Please try again.');
        return;
      }
      // Acknowledging a crewmate's alert is a buddy check: value-neutral XP, once per alert.
      const xp = results.reduce((sum, r) => sum + (r.ok ? (r.data.xp_gained ?? 0) : 0), 0);
      if (xp > 0) toast({ tone: 'reward', title: `Buddy check · +${xp} XP`, body: 'Thanks for looking out for a crewmate.' });
      else play('confirm');
    });
  };

  const handleResolveSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolveNote.trim()) {
      setError('A short note is required to resolve this alert.');
      return;
    }
    setError(null);
    const prevItem = { ...localItem };

    // Optimistic update
    setLocalItem((prev) => ({
      ...prev,
      state: 'resolved',
      resolved_by: currentUser ?? 'cmo',
      resolved_at: Date.now() / 1000,
      note: resolveNote.trim(),
    }));

    startTransition(async () => {
      const res = await resolveAttention(localItem.key, resolveNote.trim());
      if (!res.ok) {
        // Rollback
        setLocalItem(prevItem);
        setError(res.error ?? 'Failed to resolve alert. Please try again.');
      } else {
        setResolving(false);
        play('success');
        onResolved?.(localItem.key);
      }
    });
  };

  return (
    <li
      className={`${s.item} ${isAcked ? s.acknowledged : ''}`}
      data-key={localItem.key}
      data-severity={localItem.severity}
      data-state={localItem.state}
    >
      <div className={s.itemRow}>
        <span
          className={`${s.sevIcon} ${isAct ? s.sevAct : s.sevWatch}`}
          role="img"
          aria-label={`Status ${isAct ? 'Act' : 'Watch'}`}
        >
          {isAct ? <Siren size={17} /> : <TriangleAlert size={17} />}
        </span>

        <div className={s.itemText}>
          <div className={s.titleRow}>
            <span className={s.itemTitle}>{reading ? reading.label : keepUnits(localItem.title)}</span>
            {reading ? (
              <span className={`${s.valueChip} ${isAct ? s.valueAct : s.valueWatch}`}>
                {reading.value}
                {reading.unit ? <small>{reading.unit}</small> : null}
              </span>
            ) : null}
          </div>
          <p className={s.itemReason}>
            {keepUnits(localItem.reason)}
            {localItem.stale ? ' This reading is out of date: measure again to confirm.' : ''}
            <span className={s.metaInline}>
              <span aria-hidden> · </span>
              {formatAge(localItem.age)}
            </span>
            {localItem.escalation_tier ? (
              <span className={s.tierBadge} title={`Escalation tier ${localItem.escalation_tier}`}>
                Tier {localItem.escalation_tier}
              </span>
            ) : null}
            {localItem.source === 'sim' ? (
              <ReadingSource source="sim" />
            ) : null}
            {localItem.stale ? (
              <span className={s.staleBadge} title="Reading is out of date">
                Stale
              </span>
            ) : null}
          </p>
          {related.length ? (
            <ul className={s.related} aria-label={`Related to ${localItem.title}`}>
              {related.map((r) => (
                <li key={r.key}>
                  <Link2 size={13} aria-hidden className={s.relatedIcon} />
                  <span>
                    <span className={s.relatedTitle}>{keepUnits(r.title)}.</span> {keepUnits(r.reason)}{' '}
                    {followsViewer(r.action.href) ? null : (
                      <Link href={r.action.href} className={s.relatedLink}>
                        {r.action.label}
                      </Link>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        {trend && trend.spark.length > 1 ? (
          <span className={s.spark} aria-hidden>
            <Sparkline values={trend.spark} band={null} status={trend.status} width={104} height={30} />
          </span>
        ) : null}

        <div className={s.actions}>
          <Link
            href={action.href}
            className={`btn btn-sm ${isAct && !isAcked && action === localItem.action ? 'btn-primary' : 'btn-tonal'}`}
          >
            {action.label}
          </Link>
          {isAcked ? (
            <span className={s.ackedText}>
              <Check size={14} color="var(--ok)" />
              <span>
                Acknowledged{localItem.acknowledged_by ? ` by ${displayName(localItem.acknowledged_by)}` : ''}
              </span>
            </span>
          ) : (
            <button
              type="button"
              className={`btn btn-sm btn-ghost ${s.ackBtn}`}
              onClick={handleAcknowledge}
              disabled={isPending}
              aria-label={`Acknowledge ${localItem.title}`}
            >
              <Check size={15} />
              <span>Acknowledge</span>
            </button>
          )}
          {isCmo && !resolving ? (
            <button
              type="button"
              className="btn btn-sm btn-ghost"
              onClick={() => {
                setResolving(true);
                setError(null);
              }}
              disabled={isPending}
              aria-label={`Resolve alert ${localItem.title}`}
            >
              <ShieldAlert size={15} />
              <span>Resolve</span>
            </button>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className={s.inlineError} role="alert">
          {error}
        </div>
      ) : null}

      {resolving ? (
        <form onSubmit={handleResolveSubmit} className={s.resolveForm}>
          <label htmlFor={`resolve-note-${localItem.key}`} style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-2)' }}>
            Resolution note (required):
          </label>
          <input
            id={`resolve-note-${localItem.key}`}
            type="text"
            className={s.resolveInput}
            placeholder="e.g. Assessed, vitals normalized, resting quietly"
            value={resolveNote}
            onChange={(e) => setResolveNote(e.target.value)}
            disabled={isPending}
          />
          <div className={s.resolveFormActions}>
            <button
              type="button"
              className={s.resolveCancelBtn}
              onClick={() => {
                setResolving(false);
                setError(null);
              }}
              disabled={isPending}
            >
              Cancel
            </button>
            <button type="submit" className={s.resolveSubmitBtn} disabled={isPending || !resolveNote.trim()}>
              {isPending ? 'Resolving...' : 'Confirm resolve'}
            </button>
          </div>
        </form>
      ) : null}
    </li>
  );
}
