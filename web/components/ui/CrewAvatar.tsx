'use client';

import { useEffect, useRef, useState } from 'react';
import type { CrewMember } from '@/lib/types';
import { LoaderCircle } from './icons';

/**
 * A crew member's portrait from /crew/<id>.webp, drawn over their initials.
 * When the photo is missing or fails to load, the initials stay visible.
 * Portraits are of fictional people only: the app shows medical alerts next to them.
 */
type Props = {
  member: Pick<CrewMember, 'id' | 'initials' | 'hue' | 'name'>;
  size?: number;
  pending?: boolean;
  className?: string;
};

/** Keyed by crew id, so switching crew member starts the photo state fresh. */
export function CrewAvatar(props: Props) {
  return <Avatar key={props.member.id} {...props} />;
}

function Avatar({
  member,
  size = 32,
  pending = false,
  className,
}: Props) {
  const [loaded, setLoaded] = useState(false);
  const img = useRef<HTMLImageElement>(null);
  // The image may finish (or fail) before hydration attaches onLoad, so check it once on mount.
  useEffect(() => {
    const el = img.current;
    if (el?.complete && el.naturalWidth > 0) setLoaded(true);
  }, []);
  return (
    <span
      className={`avatar${className ? ` ${className}` : ''}`}
      style={{
        ['--h' as string]: member.hue,
        width: size,
        height: size,
        fontSize: Math.round(size * 0.4),
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {pending ? <LoaderCircle size={Math.round(size * 0.45)} className="spin" /> : member.initials}
      {!pending ? (
        // eslint-disable-next-line @next/next/no-img-element -- tiny static avatar; initials show if it is missing
        <img
          ref={img}
          src={`/crew/${member.id}.webp`}
          alt=""
          width={size}
          height={size}
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => setLoaded(false)}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            // Hidden until it has really loaded, so a missing file never shows a broken-image icon.
            opacity: loaded ? 1 : 0,
          }}
        />
      ) : null}
    </span>
  );
}
