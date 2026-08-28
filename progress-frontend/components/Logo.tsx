"use client";

/** The mark: an F with the arrow rising through and out of it.
 *  The F takes currentColor so it follows the theme; the arrow is always the accent,
 *  because forward motion is the one thing the accent is for. */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      role="img"
      aria-label="ForwardTrace"
    >
      <path d="M26 96V30a4 4 0 0 1 4-4h40" stroke="currentColor" strokeWidth="13" strokeLinecap="square" />
      <path d="M26 61h26" stroke="currentColor" strokeWidth="13" strokeLinecap="square" />
      <path d="M40 82 96 26" stroke="var(--sunrise)" strokeWidth="13" strokeLinecap="square" />
      <path d="M68 24h30v30" stroke="var(--sunrise)" strokeWidth="13" strokeLinecap="square" />
    </svg>
  );
}
