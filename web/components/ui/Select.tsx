'use client';

import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { cx } from '@/lib/format';
import { Check, ChevronDown } from './icons';
import s from './select.module.css';

export interface SelectOption {
  value: string;
  label: string;
  /** Second line under the label, e.g. a crew member's role. */
  description?: string;
  /** Shown before the label, e.g. an avatar or icon. */
  leading?: React.ReactNode;
  /** Options with the same group are listed under one heading, in first-seen order. */
  group?: string;
  /** Small tag after the label, e.g. "You". */
  tag?: string;
}

interface SelectProps {
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  /** Accessible name; required because the trigger has no visible <label> of its own. */
  'aria-label'?: string;
  'aria-labelledby'?: string;
  disabled?: boolean;
  /** sm: compact toolbar control; md: form field. */
  size?: 'sm' | 'md';
  /** Show the selected option's description inside the trigger (md only). */
  showDescription?: boolean;
  className?: string;
  /** Popover width; defaults to the trigger width, at least 220px. */
  menuWidth?: number;
  id?: string;
}

/**
 * A styled single-choice dropdown (ARIA listbox pattern) that replaces native <select>, whose popup the OS draws.
 * Keyboard: Enter/Space/ArrowDown opens; arrows, Home/End and typing a letter move; Enter selects; Escape/Tab close.
 */
export function Select({
  value,
  options,
  onChange,
  disabled,
  size = 'md',
  showDescription = false,
  className,
  menuWidth,
  id,
  ...aria
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  /** Where the menu opens: above the trigger, aligned to its right edge, or as a bottom sheet on phones. */
  const [place, setPlace] = useState<{ up: boolean; end: boolean; sheet: boolean; maxH?: number }>({
    up: false,
    end: false,
    sheet: false,
  });
  const wrap = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const typed = useRef({ text: '', at: 0 });
  const baseId = useId();
  const listId = `${baseId}-list`;
  const optId = (i: number) => `${baseId}-opt-${i}`;

  const selectedIndex = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const selected = options[selectedIndex];

  const openAt = (i: number) => {
    if (disabled) return;
    // Decide the direction before the menu renders, so it never paints below the fold and then jumps.
    const r = trigger.current?.getBoundingClientRect();
    if (r) {
      const sheet = window.matchMedia('(max-width: 560px)').matches;
      const below = window.innerHeight - r.bottom;
      const up = !sheet && below < 280 && r.top > below;
      const topbar = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topbar')) || 56;
      // Keep the menu inside the viewport and clear of the sticky top bar; it scrolls inside instead.
      const maxH = sheet ? undefined : Math.max(120, Math.floor(up ? r.top - topbar - 18 : below - 18));
      setPlace({ up, end: false, sheet, maxH });
    }
    setActive(i);
    setOpen(true);
  };
  const close = (focusTrigger = true) => {
    setOpen(false);
    if (focusTrigger) trigger.current?.focus();
  };
  const choose = (i: number) => {
    const o = options[i];
    close();
    if (o && o.value !== value) onChange(o.value);
  };

  // Open upward when there is not enough room below (decided in openAt); align to the trigger's right edge
  // when the menu would run off the right side of the viewport. Focus without scrolling the page.
  useLayoutEffect(() => {
    if (!open || !trigger.current || !list.current) return;
    if (!window.matchMedia('(max-width: 560px)').matches) {
      const r = trigger.current.getBoundingClientRect();
      const w = list.current.getBoundingClientRect().width;
      // Inside the page, its right edge is the limit: the docked specialist panel sits beyond it on wide screens.
      const main = trigger.current.closest('#main-content');
      const edge = Math.min(window.innerWidth, main ? main.getBoundingClientRect().right : Infinity);
      if (r.left + w > edge - 12) setPlace((p) => ({ ...p, end: true }));
    }
    list.current.focus({ preventScroll: true });
  }, [open]);

  // Keep the active option in view.
  useEffect(() => {
    if (!open) return;
    document.getElementById(optId(active))?.scrollIntoView({ block: 'nearest' });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- optId is derived from a stable id
  }, [open, active]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const typeAhead = (key: string) => {
    const now = Date.now();
    typed.current.text = now - typed.current.at > 600 ? key : typed.current.text + key;
    typed.current.at = now;
    const q = typed.current.text.toLowerCase();
    const start = q.length === 1 ? active + 1 : active;
    for (let k = 0; k < options.length; k++) {
      const i = (start + k) % options.length;
      if (options[i].label.toLowerCase().startsWith(q)) return i;
    }
    return -1;
  };

  const onTriggerKey = (e: React.KeyboardEvent) => {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
      e.preventDefault();
      openAt(e.key === 'ArrowUp' ? Math.max(0, selectedIndex - 1) : selectedIndex);
    }
  };

  const onListKey = (e: React.KeyboardEvent) => {
    const last = options.length - 1;
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActive((i) => Math.min(last, i + 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActive((i) => Math.max(0, i - 1));
        break;
      case 'Home':
        e.preventDefault();
        setActive(0);
        break;
      case 'End':
        e.preventDefault();
        setActive(last);
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        choose(active);
        break;
      case 'Escape':
        e.preventDefault();
        close();
        break;
      case 'Tab':
        setOpen(false);
        break;
      default:
        if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
          const i = typeAhead(e.key);
          if (i >= 0) setActive(i);
        }
    }
  };

  // Group headings, in first-seen order; options keep their index for keyboard movement.
  const sections: { group?: string; items: { o: SelectOption; i: number }[] }[] = [];
  options.forEach((o, i) => {
    const last = sections[sections.length - 1];
    if (last && last.group === o.group) last.items.push({ o, i });
    else sections.push({ group: o.group, items: [{ o, i }] });
  });

  return (
    <div ref={wrap} className={cx(s.wrap, className)}>
      <button
        ref={trigger}
        id={id}
        type="button"
        className={cx(s.trigger, size === 'sm' ? s.sm : s.md)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        disabled={disabled}
        onClick={() => (open ? close(false) : openAt(selectedIndex))}
        onKeyDown={onTriggerKey}
        {...aria}
      >
        {selected?.leading ? <span className={s.leading}>{selected.leading}</span> : null}
        <span className={s.value}>
          <span className={s.label}>{selected?.label}</span>
          {showDescription && selected?.description ? <small>{selected.description}</small> : null}
        </span>
        <ChevronDown size={16} className={s.chevron} aria-hidden />
      </button>

      {open ? (
        <div
          ref={list}
          id={listId}
          role="listbox"
          tabIndex={-1}
          aria-label={aria['aria-label']}
          aria-labelledby={aria['aria-labelledby']}
          aria-activedescendant={optId(active)}
          className={cx(s.menu, place.up && s.up, place.end && s.end, place.sheet && s.sheet)}
          style={
            place.sheet
              ? undefined
              : {
                  minWidth: menuWidth ?? '100%',
                  maxHeight: place.maxH ? `min(60vh, 360px, ${place.maxH}px)` : undefined,
                }
          }
          onKeyDown={onListKey}
        >
          {sections.map((sec) => (
            <div key={`${sec.group ?? 'none'}-${sec.items[0].o.value}`} role="presentation">
              {sec.group ? (
                <div className={s.groupHead} role="presentation">
                  {sec.group}
                </div>
              ) : null}
              <div role="group" aria-label={sec.group}>
                {sec.items.map(({ o, i }) => {
                  const isSel = o.value === value;
                  return (
                    // Keys are handled on the listbox (aria-activedescendant); options are not focusable.
                    // eslint-disable-next-line jsx-a11y/click-events-have-key-events
                    <div
                      key={o.value}
                      id={optId(i)}
                      role="option"
                      tabIndex={-1}
                      aria-selected={isSel}
                      className={cx(s.option, i === active && s.active, isSel && s.selected)}
                      onMouseMove={() => i !== active && setActive(i)}
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => choose(i)}
                    >
                      {o.leading ? <span className={s.leading}>{o.leading}</span> : null}
                      <span className={s.value}>
                        <span className={s.label}>
                          {o.label}
                          {o.tag ? <span className={s.tag}>{o.tag}</span> : null}
                        </span>
                        {o.description ? <small>{o.description}</small> : null}
                      </span>
                      {isSel ? <Check size={16} className={s.check} aria-hidden /> : null}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
