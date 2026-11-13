'use client';

import { useEffect, useRef, useState } from 'react';
import type { ExerciseVideo } from '@/lib/types';
import { CirclePlay, ExternalLink, Info, Maximize, Pause, Play, Repeat, Volume2, VolumeX, X } from '../ui/icons';
import s from './exercise.module.css';

const mmss = (sec: number) => {
  const v = Math.max(0, Math.round(sec));
  return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`;
};
const dateLabel = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

/** Link text with the external-link icon held to its last word, so the icon never wraps onto a line alone. */
function LinkText({ text }: { text: string }) {
  const i = text.lastIndexOf(' ') + 1;
  return (
    <>
      {text.slice(0, i)}
      <span className={s.nowrap}>
        {text.slice(i)}
        {'\u00A0'}
        <ExternalLink size={12} aria-hidden />
      </span>
    </>
  );
}

/**
 * A NASA file played as a loop of just the exercise seconds, with controls scoped to the clip: play/pause, a seek
 * bar over only those seconds, clip time, mute and fullscreen. Muted so it can start on its own.
 */
function ClipPlayer({ video }: { video: ExerciseVideo }) {
  const ref = useRef<HTMLVideoElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const [t, setT] = useState(video.start);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(true);
  const [ready, setReady] = useState(false);
  const length = video.end - video.start;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const onTime = () => {
      if (el.currentTime >= video.end || el.currentTime < video.start - 0.5) {
        el.currentTime = video.start;
        void el.play().catch(() => {});
      }
      setT(el.currentTime);
    };
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onReady = () => setReady(true);
    el.addEventListener('timeupdate', onTime);
    el.addEventListener('play', onPlay);
    el.addEventListener('pause', onPause);
    el.addEventListener('canplay', onReady);
    return () => {
      el.removeEventListener('timeupdate', onTime);
      el.removeEventListener('play', onPlay);
      el.removeEventListener('pause', onPause);
      el.removeEventListener('canplay', onReady);
    };
  }, [video.start, video.end]);

  const toggle = () => {
    const el = ref.current;
    if (!el) return;
    if (el.paused) void el.play().catch(() => {});
    else el.pause();
  };
  const seek = (v: number) => {
    const el = ref.current;
    if (!el) return;
    el.currentTime = v;
    setT(v);
  };
  const toggleMute = () => {
    const el = ref.current;
    if (!el) return;
    el.muted = !el.muted;
    setMuted(el.muted);
  };
  const fullscreen = () => {
    void box.current?.requestFullscreen?.().catch(() => {});
  };

  const into = Math.min(length, Math.max(0, t - video.start));
  const pct = (100 * into) / length;

  return (
    <div ref={box} className={s.clip}>
      {/* eslint-disable-next-line jsx-a11y/media-has-caption -- silent B-roll, no speech to caption */}
      <video
        ref={ref}
        // Start time only: an end time in the fragment makes some browsers pause there instead of looping.
        src={`${video.mp4}#t=${video.start}`}
        autoPlay
        muted
        playsInline
        preload="auto"
        aria-label={`${video.shows}: ${video.who}`}
      />
      {!ready ? <span className={s.clipLoading}>Loading clip…</span> : null}
      <span className={s.clipBadge}>
        <Repeat size={12} aria-hidden /> Looping {mmss(length)} clip
      </span>
      <div className={s.clipBar}>
        <button type="button" className={s.clipBtn} onClick={toggle} aria-label={playing ? 'Pause' : 'Play'}>
          {playing ? <Pause size={16} /> : <Play size={16} />}
        </button>
        <input
          type="range"
          className={s.clipSeek}
          min={video.start}
          max={video.end}
          step={0.1}
          value={Math.min(video.end, Math.max(video.start, t))}
          onChange={(e) => seek(Number(e.target.value))}
          aria-label="Position in clip"
          aria-valuetext={`${mmss(into)} of ${mmss(length)}`}
          style={{ ['--pct' as string]: `${pct}%` }}
        />
        <span className={s.clipTime}>
          {mmss(into)} / {mmss(length)}
        </span>
        <button type="button" className={s.clipBtn} onClick={toggleMute} aria-label={muted ? 'Unmute' : 'Mute'}>
          {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
        </button>
        <button type="button" className={s.clipBtn} onClick={fullscreen} aria-label="Full screen">
          <Maximize size={15} />
        </button>
      </div>
    </div>
  );
}

/**
 * "Watch <astronaut>" button: opens a dialog that plays only the seconds where this exercise is on screen, from the
 * agency's own YouTube channel (start/end) or NASA's public-domain file, with a full citation under the player.
 * Nothing loads until the dialog opens.
 */
export function VideoButton({ video }: { video: ExerciseVideo }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const length = video.end - video.start;
  const headingId = `vid-${video.youtube ?? video.mp4?.split('/')[4]}-${video.start}`;

  const show = () => {
    setOpen(true);
    dialog.current?.showModal();
  };
  const close = () => dialog.current?.close();

  // A click on the backdrop (the <dialog> element itself, outside the panel) closes it. This is a mouse shortcut
  // only: keyboard users have Escape (native to <dialog>) and the Close button.
  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    const onClick = (e: MouseEvent) => {
      if (e.target === el) el.close();
    };
    el.addEventListener('click', onClick);
    return () => el.removeEventListener('click', onClick);
  }, []);

  const src = video.youtube
    ? `https://www.youtube-nocookie.com/embed/${video.youtube}` +
      `?start=${video.start}&end=${video.end}&autoplay=1&rel=0&modestbranding=1`
    : null;

  return (
    <>
      <button type="button" className={`btn btn-tonal btn-sm ${s.videoBtn}`} onClick={show}>
        <CirclePlay size={16} aria-hidden /> Watch {video.who.split(' ')[0]} <span className={s.clipLen}>{mmss(length)}</span>
      </button>
      <dialog ref={dialog} className={s.dialog} aria-labelledby={headingId} onClose={() => setOpen(false)}>
        <div className={s.dialogPanel}>
          <header className={s.dialogHead}>
            <div>
              <h2 id={headingId} className={s.dialogTitle}>
                {video.shows}
              </h2>
              <p className={s.dialogSub}>
                {video.who} · {video.where} · Esc or Close to exit
              </p>
            </div>
            <button type="button" className={s.closeBtn} onClick={close} aria-label="Close video">
              <X size={18} />
            </button>
          </header>

          <div className={s.player}>
            {open && src ? (
              // The YouTube player needs scripts and its own origin; as a cross-origin frame it is already isolated.
              // eslint-disable-next-line react/iframe-missing-sandbox
              <iframe
                src={src}
                title={`${video.shows}: ${video.who}`}
                allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
                referrerPolicy="strict-origin-when-cross-origin"
              />
            ) : null}
            {open && video.mp4 ? <ClipPlayer video={video} /> : null}
          </div>

          <div className={s.dialogBody}>
            {video.note ? (
              <p className={s.clipNote}>
                <Info size={15} aria-hidden /> {video.note}
              </p>
            ) : null}
            {/* Citation: what it is, who published it and when, which seconds are shown, and the terms of use. */}
            <dl className={s.citation}>
              <div>
                <dt>Source</dt>
                <dd>
                  <a href={video.url} target="_blank" rel="noopener noreferrer">
                    <LinkText text={`“${video.title}”`} />
                  </a>
                </dd>
              </div>
              <div>
                <dt>Published</dt>
                <dd>
                  {video.channel}, {dateLabel(video.published)} · {video.youtube ? 'YouTube' : 'images.nasa.gov'}
                </dd>
              </div>
              <div>
                <dt>Clip</dt>
                <dd className={s.tnum}>
                  {mmss(video.start)}–{mmss(video.end)} of the original
                </dd>
              </div>
              <div>
                <dt>Licence</dt>
                <dd>
                  <a href={video.license_url} target="_blank" rel="noopener noreferrer">
                    <LinkText text={video.license} />
                  </a>
                </dd>
              </div>
            </dl>
            {/* Escape and Tab can stay inside the YouTube player's frame; Tab out of it lands on this button. */}
            <div className={s.dialogFoot}>
              <button type="button" className="btn btn-tonal" onClick={close}>
                Close
              </button>
            </div>
          </div>
        </div>
      </dialog>
    </>
  );
}
