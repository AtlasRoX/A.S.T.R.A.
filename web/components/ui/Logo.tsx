/* eslint-disable @next/next/no-img-element -- small static brand images; both theme variants ship and CSS shows one. */

/**
 * The ASTRA logo from public/logo.png, trimmed. Each image comes in a light-theme and a dark-theme variant
 * (navy text lightened for dark backgrounds); `.logo-on-light` / `.logo-on-dark` in globals.css show the
 * one that matches `html[data-theme]`.
 */

/** Symbol plus the ASTRA wordmark. */
export function Logo({ height = 26, className }: { height?: number; className?: string }) {
  const width = Math.round((height * 634) / 120);
  return (
    <span className={className} style={{ display: 'inline-flex' }}>
      <img src="/logo-wordmark.png" alt="" width={width} height={height} className="logo-on-light" />
      <img src="/logo-wordmark-dark.png" alt="" width={width} height={height} className="logo-on-dark" />
    </span>
  );
}

/** The symbol alone, for narrow spaces. */
export function LogoMark({ size = 30, className }: { size?: number; className?: string }) {
  const width = Math.round((size * 188) / 128);
  return (
    <span className={className} style={{ display: 'inline-flex' }}>
      <img src="/logo-mark.png" alt="" width={width} height={size} className="logo-on-light" />
      <img src="/logo-mark-dark.png" alt="" width={width} height={size} className="logo-on-dark" />
    </span>
  );
}
