'use client';

import { motion } from 'motion/react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState, useTransition } from 'react';
import { useTheme } from '../ui/theme';
import { Assistant } from '../assistant/Assistant';
import { LiveRefresh } from '../sim/LiveRefresh';
import { CrewAvatar } from '../ui/CrewAvatar';
import { setCrew, setEnvironment } from '@/app/actions';
import { cx, duration, formatUtc } from '@/lib/format';
import type { AttentionCounts, Clock, Comms, CrewMember, Environment } from '@/lib/types';
import { Logo, LogoMark } from '../ui/Logo';
import {
  BookOpen,
  ChartSpline,
  Check,
  ChevronDown,
  LayoutDashboard,
  LoaderCircle,
  type LucideIcon,
  Moon,
  Settings2,
  Siren,
  Stethoscope,
  Sun,
  Users,
} from '../ui/icons';
import s from './shell.module.css';

interface NavDef {
  href: string;
  label: string;
  icon: LucideIcon;
  due?: boolean;
  /** Shorter label for the phone's bottom bar. */
  short?: string;
}

const NAV: NavDef[] = [
  { href: '/', label: 'Today', icon: LayoutDashboard },
  { href: '/measure', label: 'Measure', icon: Stethoscope, due: true },
  { href: '/trends', label: 'Trends', icon: ChartSpline },
  { href: '/crew', label: 'Crew', icon: Users },
  { href: '/learn', label: 'Reference', short: 'Learn', icon: BookOpen },
];

const isActive = (path: string, href: string) => {
  // Routine is opened from Today's checks, so it belongs to Today.
  if (href === '/') return path === '/' || path.startsWith('/routine');
  // Library and Data are one Reference area.
  if (href === '/learn') return path.startsWith('/learn') || path.startsWith('/data');
  return path.startsWith(href);
};

export interface ShellProps {
  crew: CrewMember[];
  envs: Environment[];
  crewId: string;
  envId: string;
  clock: Clock;
  dueCount: number;
  mission: string;
  attentionCounts?: AttentionCounts | null;
  comms?: Comms | null;
  children: React.ReactNode;
}

export function Shell({
  crew,
  envs,
  crewId,
  envId,
  clock,
  dueCount,
  mission,
  attentionCounts,
  comms,
  children,
}: ShellProps) {
  const path = usePathname();
  const env = envs.find((e) => e.id === envId) ?? envs[0];
  const me = crew.find((c) => c.id === crewId) ?? crew[0];
  const emergency = path.startsWith('/emergency');
  const settingsActive = isActive(path, '/settings');
  const exerciseActive = isActive(path, '/exercise');

  return (
    <div className={s.shell}>
      <a href="#main-content" className={s.skipLink}>
        Skip to main content
      </a>

      <header className={s.bar}>
        <Link href="/" className={s.brand} aria-label={`ASTRA, crew health for ${mission}`}>
          <Logo height={24} className={s.brandWord} />
          <LogoMark size={22} className={s.brandMark} />
        </Link>

        <nav className={s.tabs} aria-label="Primary navigation">
          {NAV.map((n) => {
            const active = isActive(path, n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cx(s.tab, active && s.active)}
                aria-current={active ? 'page' : undefined}
              >
                {n.short ? (
                  <>
                    <span className={s.tabFull}>{n.label}</span>
                    <span className={s.tabShort}>{n.short}</span>
                  </>
                ) : (
                  <span>{n.label}</span>
                )}
                {n.due && dueCount > 0 ? (
                  <>
                    <span className={s.count} aria-hidden="true">
                      {dueCount}
                    </span>
                    <span className="sr-only">, {dueCount} checks due</span>
                  </>
                ) : null}
                {active ? (
                  <motion.span
                    layoutId="tab-line"
                    className={s.line}
                    transition={{ type: 'spring', stiffness: 520, damping: 42 }}
                  />
                ) : null}
              </Link>
            );
          })}
        </nav>

        <span className={s.spacer} />

        <div className={s.actions}>
          {attentionCounts && (attentionCounts.act > 0 || attentionCounts.watch > 0) && !emergency ? (
            <Link
              href="/#attention-queue"
              className={s.attentionBadge}
              aria-label={attentionLabel(attentionCounts, me.name)}
              title={attentionLabel(attentionCounts, me.name)}
            >
              {attentionCounts.act > 0 ? (
                <span className={s.actPill}>
                  <span aria-hidden="true">■</span>
                  <span className={s.badgeNum}>{attentionCounts.act}</span>
                  <span className={s.badgeLabel}>Act</span>
                </span>
              ) : null}
              {attentionCounts.watch > 0 ? (
                <span className={s.watchPill}>
                  <span aria-hidden="true">▲</span>
                  <span className={s.badgeNum}>{attentionCounts.watch}</span>
                  <span className={s.badgeLabel}>Watch</span>
                </span>
              ) : null}
            </Link>
          ) : null}
          <Link
            href="/exercise"
            className={cx(s.iconBtn, s.barExercise, exerciseActive && s.on)}
            aria-label="Exercise"
            aria-current={exerciseActive ? 'page' : undefined}
            title="Exercise"
          >
            <span className={s.exerciseIcon} aria-hidden="true" />
          </Link>
          <ThemeToggle className={s.barTheme} />
          <Link
            href="/settings"
            className={cx(s.iconBtn, s.barSettings, settingsActive && s.on)}
            aria-label="Settings"
            title="Settings"
          >
            <Settings2 size={18} />
          </Link>
          <CrewMenu crew={crew} me={me} settingsActive={settingsActive} />
          {!emergency ? <span className={s.divider} aria-hidden="true" /> : null}
          {!emergency ? (
            <Link href="/emergency" className={s.sos} aria-label="Emergency" title="Open emergency protocols">
              <Siren size={18} />
              <span className={s.sosLabel}>Emergency</span>
            </Link>
          ) : null}
        </div>
      </header>

      <MissionStrip clock={clock} env={env} envs={envs} comms={comms} />

      <main id="main-content" tabIndex={-1} className={cx(s.main, emergency && s.mainEmergency)}>
        {children}
      </main>

      {!emergency ? <MobileNav path={path} dueCount={dueCount} /> : null}

      {/* The AI specialist: everywhere except the emergency runner, which must stay single-purpose. */}
      {!emergency ? <Assistant viewerName={me.name.split(' ')[0]} viewerId={me.id} crew={crew} /> : null}

      {/* Background telemetry from ASTRA Core: every screen refreshes itself as new readings arrive. */}
      <LiveRefresh />
    </div>
  );
}

/** The header badge counts only the person being viewed as; say so, since the Crew page counts everyone. */
function attentionLabel(c: AttentionCounts, name: string) {
  const parts = [c.act ? `${c.act} Act` : '', c.watch ? `${c.watch} Watch` : ''].filter(Boolean).join(', ');
  return `${name.split(' ')[0]}'s alerts: ${parts}. Open needs-attention list`;
}

/* ------------------------------------------------------------------ mission strip */
function MissionStrip({
  clock,
  env,
  envs,
  comms,
}: {
  clock: Clock;
  env: Environment;
  envs: Environment[];
  comms?: Comms | null;
}) {
  const isBlackout = comms?.conjunction?.phase === 'blackout';
  const isLive = env.delay_s < 5 && !isBlackout;
  const linkStatusClass = isBlackout ? 'linkBlocked' : isLive ? 'linkLive' : 'linkDelayed';
  const linkStatusText = isBlackout ? 'blocked' : isLive ? 'live' : 'delayed';

  // Fallback ISO UTC string if not provided by comms
  const utcIso =
    comms?.utc ||
    new Date(Date.UTC(2026, 10, 12, 0, 0, 0) + clock.met_s * 1000).toISOString();
  // The UTC label already says UTC.
  const utcFormatted = formatUtc(utcIso).replace(/ UTC$/, '');

  const delayText = isLive ? '0s (live)' : `${duration(env.delay_s)} one way`;
  const replyText = isLive ? 'immediate' : `≥ ${duration(2 * env.delay_s + 90)}`;

  return (
    <div id="mission-strip" className={s.missionStrip} role="region" aria-label="Mission status">
      {/* Desktop & Tablet view */}
      <div className={s.stripDesktop}>
        <div className={s.stripGroup}>
          <span className={s.stripLabel}>MET</span>
          <span className={s.stripVal}>
            <MetClock clock={clock} />
          </span>
        </div>
        <span className={s.dotSep} aria-hidden="true">·</span>
        <div className={s.stripGroup}>
          <span className={cx(s.linkPill, s[linkStatusClass])}>
            <i className={s.linkDot} />
            <span>Link {linkStatusText}</span>
          </span>
        </div>
        <span className={s.dotSep} aria-hidden="true">·</span>
        <div className={s.stripGroup}>
          <span className={s.stripLabel}>UTC</span>
          <span className={s.stripVal}>{utcFormatted}</span>
        </div>
        <span className={s.dotSep} aria-hidden="true">·</span>
        <div className={cx(s.stripGroup, s.stripLocation)}>
          <span className={s.stripLabel}>Location</span>
          <EnvMenu envs={envs} env={env} />
        </div>
        <span className={s.dotSep} aria-hidden="true">·</span>
        <div className={s.stripGroup}>
          <span className={s.stripLabel}>Earth delay</span>
          <span className={s.stripVal}>{delayText}</span>
        </div>
        {!isLive ? (
          <>
            {/* Lowest priority: hidden while the specialist panel narrows the strip (globals.css). */}
            <span className={s.dotSep} aria-hidden="true" data-strip-optional>·</span>
            <div className={cx(s.stripGroup, s.stripReply)} data-strip-optional>
              <span className={s.stripLabel}>Earliest reply</span>
              <span className={s.stripVal}>{replyText}</span>
            </div>
          </>
        ) : null}
      </div>

      {/* Compact Phone view */}
      <div className={s.stripPhone}>
        <span className={s.stripPhoneFixed}>
          <span className={s.stripPhoneMet}>MET</span> Day {clock.day}
        </span>
        <span className={s.dotSep} aria-hidden="true">·</span>
        <EnvMenu envs={envs} env={env} />
        <span className={s.dotSep} aria-hidden="true">·</span>
        <span className={s.stripPhoneFixed}>
          <i className={s.linkDot} data-link={linkStatusText} />
          {isBlackout ? (
            'Earth link blocked'
          ) : (
            <>
              Earth {isLive ? '0s' : duration(env.delay_s)}
              {/* The coloured dot carries this on narrow phones (shell.module.css). */}
              <span className={s.stripPhoneStatus}> ({linkStatusText})</span>
            </>
          )}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ clock */
function MetClock({ clock }: { clock: Clock }) {
  const [now, setNow] = useState(clock.met_s);
  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => setNow(clock.met_s + (Date.now() - start) / 1000), 1000);
    return () => clearInterval(t);
  }, [clock.met_s]);
  const day = Math.floor(now / 86400) + 1;
  const sod = Math.floor(now % 86400);
  const hh = String(Math.floor(sod / 3600)).padStart(2, '0');
  const mm = String(Math.floor((sod % 3600) / 60)).padStart(2, '0');
  const ss = String(sod % 60).padStart(2, '0');
  return (
    <>
      Day {day} {hh}:{mm}
      <span className={s.sec}>:{ss}</span>
    </>
  );
}

/* ------------------------------------------------------------------ menus hook */
function useMenuDismiss(
  open: boolean,
  close: () => void,
  triggerRef?: React.RefObject<HTMLButtonElement | null>,
) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        close();
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close();
        triggerRef?.current?.focus();
      }
    };
    // Tab (or any focus move) out of the menu closes it.
    const onFocusOut = (e: FocusEvent) => {
      const next = e.relatedTarget as Node | null;
      if (next && ref.current && !ref.current.contains(next)) close();
    };
    const wrap = ref.current;
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    wrap?.addEventListener('focusout', onFocusOut);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
      wrap?.removeEventListener('focusout', onFocusOut);
    };
  }, [open, close, triggerRef]);
  return ref;
}

/* ------------------------------------------------------------------ Env Menu */
function EnvMenu({ envs, env }: { envs: Environment[]; env: Environment }) {
  const [open, setOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [pending, start] = useTransition();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useMenuDismiss(open, () => setOpen(false), triggerRef);
  const itemsRef = useRef<(HTMLButtonElement | null)[]>([]);

  const toggleOpen = () => {
    setOpen((o) => {
      const next = !o;
      if (next) {
        const idx = envs.findIndex((e) => e.id === env.id);
        const targetIdx = idx >= 0 ? idx : 0;
        setFocusedIndex(targetIdx);
        setTimeout(() => itemsRef.current[targetIdx]?.focus(), 0);
      }
      return next;
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = (focusedIndex + 1) % envs.length;
      setFocusedIndex(next);
      itemsRef.current[next]?.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = (focusedIndex - 1 + envs.length) % envs.length;
      setFocusedIndex(prev);
      itemsRef.current[prev]?.focus();
    }
  };

  return (
    <div className={s.menuWrap} ref={menuRef}>
      <button
        ref={triggerRef}
        type="button"
        className={s.envBtn}
        onClick={toggleOpen}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Location: ${env.name}. Change mission environment`}
        title="Change mission environment"
      >
        {pending ? <LoaderCircle size={14} className="spin" /> : null}
        <span className={s.envName}>{env.name}</span>
        <ChevronDown size={14} />
      </button>
      {open ? (
        <div
          className={cx(s.menu, s.menuLeft)}
          role="listbox"
          tabIndex={-1}
          aria-label="Mission environment"
          onKeyDown={handleKeyDown}
        >
          <div className={s.menuHead} role="presentation">
            Mission environment
          </div>
          {envs.map((e, idx) => (
            <button
              key={e.id}
              ref={(el) => {
                itemsRef.current[idx] = el;
              }}
              type="button"
              role="option"
              aria-selected={e.id === env.id}
              tabIndex={focusedIndex === idx ? 0 : -1}
              className={cx(s.menuItem, e.id === env.id && s.selected)}
              onClick={() => {
                setOpen(false);
                triggerRef.current?.focus();
                if (e.id !== env.id) start(() => setEnvironment(e.id));
              }}
            >
              <span>
                <b>{e.name}</b>
                <small>
                  {e.gravity.split(' ·')[0]}, {e.delay_s < 5 ? 'live link' : `${duration(e.delay_s)} delay`},{' '}
                  {e.radiation_msv_day} mSv a day
                </small>
              </span>
              {e.id === env.id ? <Check size={16} className={s.check} /> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ Crew Menu */
function CrewMenu({ crew, me, settingsActive }: { crew: CrewMember[]; me: CrewMember; settingsActive: boolean }) {
  const [open, setOpen] = useState(false);
  // A switch is confirmed right here, under the button that shows who you are viewing as. Switches made elsewhere
  // (the View as buttons on crew cards and profiles) change this button too, so they get the same note.
  const [shownId, setShownId] = useState(me.id);
  const [noteFor, setNoteFor] = useState<string | null>(null);
  if (shownId !== me.id) {
    setShownId(me.id);
    setNoteFor(me.id);
  }
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [pending, start] = useTransition();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useMenuDismiss(open, () => setOpen(false), triggerRef);
  const itemsRef = useRef<(HTMLButtonElement | null)[]>([]);

  const toggleOpen = () => {
    setNoteFor(null);
    setOpen((o) => {
      const next = !o;
      if (next) {
        const idx = crew.findIndex((c) => c.id === me.id);
        const targetIdx = idx >= 0 ? idx : 0;
        setFocusedIndex(targetIdx);
        setTimeout(() => itemsRef.current[targetIdx]?.focus(), 0);
      }
      return next;
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      const next = (focusedIndex + 1) % crew.length;
      setFocusedIndex(next);
      itemsRef.current[next]?.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      const prev = (focusedIndex - 1 + crew.length) % crew.length;
      setFocusedIndex(prev);
      itemsRef.current[prev]?.focus();
    }
  };

  return (
    <div className={s.menuWrap} ref={menuRef}>
      <button
        ref={triggerRef}
        type="button"
        className={s.crewBtn}
        onClick={toggleOpen}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Viewing as ${me.title} ${me.name}. Change crew member`}
        title={`${me.title} ${me.name}, ${me.role}`}
      >
        <CrewAvatar member={me} size={28} pending={pending} />
        <span className={s.crewName}>{me.name.split(' ')[0]}</span>
        <ChevronDown size={14} className={s.crewChevron} />
      </button>
      {open ? (
        <div className={s.menu}>
          <div role="listbox" tabIndex={-1} aria-label="Crew member" onKeyDown={handleKeyDown}>
            <div className={s.menuHead} role="presentation">
              View as
            </div>
            {crew.map((c, idx) => (
              <button
                key={c.id}
                ref={(el) => {
                  itemsRef.current[idx] = el;
                }}
                type="button"
                role="option"
                aria-selected={c.id === me.id}
                tabIndex={focusedIndex === idx ? 0 : -1}
                className={cx(s.menuItem, c.id === me.id && s.selected)}
                onClick={() => {
                  setOpen(false);
                  triggerRef.current?.focus();
                  if (c.id !== me.id) start(() => setCrew(c.id));
                }}
              >
                <CrewAvatar member={c} size={30} />
                <span>
                  <b>
                    {c.title} {c.name}
                  </b>
                  <small>{c.role}</small>
                </span>
                {c.id === me.id ? <Check size={16} className={s.check} /> : null}
              </button>
            ))}
          </div>
          {/* Narrower bars move the theme toggle (and on small phones Settings) in here; shell.module.css shows them. */}
          <div className={s.menuMore}>
            <ThemeToggle withLabel className={s.menuTheme} />
            <Link
              href="/settings"
              className={cx(s.menuItem, s.menuSettings, settingsActive && s.selected)}
              aria-current={settingsActive ? 'page' : undefined}
              onClick={() => setOpen(false)}
            >
              <Settings2 size={18} />
              <span>
                <b>Settings</b>
              </span>
            </Link>
          </div>
        </div>
      ) : null}
      {noteFor === me.id && !open ? (
        <div
          key={me.id}
          className={s.switchNote}
          aria-hidden
          onAnimationEnd={(e) => {
            if (e.target === e.currentTarget) setNoteFor(null);
          }}
        >
          <CrewAvatar member={me} size={32} />
          <span>
            <small>Now viewing as</small>
            <b>
              {me.title} {me.name}
            </b>
          </span>
        </div>
      ) : null}
      <span className="sr-only" role="status">
        {noteFor ? `Now viewing as ${me.title} ${me.name}` : ''}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ theme */
export function ThemeToggle({ className, withLabel = false }: { className?: string; withLabel?: boolean }) {
  const [theme, setTheme] = useTheme();
  const next = theme === 'light' ? 'dark' : 'light';
  return (
    <button
      type="button"
      className={cx(withLabel ? s.menuItem : s.iconBtn, className)}
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
    >
      {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
      {withLabel ? (
        <span>
          <b>{theme === 'light' ? 'Dark theme' : 'Light theme'}</b>
        </span>
      ) : null}
    </button>
  );
}

/* ------------------------------------------------------------------ mobile nav */
function MobileNav({ path, dueCount }: { path: string; dueCount: number }) {
  return (
    <nav className={s.mobileNav} aria-label="Mobile navigation">
      {NAV.map((n) => {
        const active = isActive(path, n.href);
        return (
          <Link
            key={n.href}
            href={n.href}
            className={cx(s.mItem, active && s.active)}
            aria-current={active ? 'page' : undefined}
          >
            <n.icon size={20} strokeWidth={1.8} />
            <span>{n.short ?? n.label}</span>
            {n.due && dueCount > 0 ? (
              <>
                <span className={s.dot} aria-hidden="true" />
                <span className="sr-only">, {dueCount} checks due</span>
              </>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
