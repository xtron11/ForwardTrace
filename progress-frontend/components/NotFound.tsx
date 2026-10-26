"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { isSignedIn } from "@/lib/api";
import { useT } from "@/lib/useT";

/**
 * The 404 screen, for unknown URLs and for notFound() alike.
 *
 * The way back depends on who is lost: someone signed in wants their day, not the
 * landing. The session lives in localStorage, so it is read after mount; reading it
 * during render would disagree with the server's HTML.
 */
export function NotFound() {
  const { t } = useT();
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => {
    setSignedIn(isSignedIn());
  }, []);

  return (
    <main className="mx-auto flex min-h-dvh max-w-(--column-max) flex-col justify-center px-(--page-pad)">
      <Link href="/" aria-label="ForwardTrace" className="self-start text-bone">
        <Logo size={38} />
      </Link>

      <div className="enter mt-9">
        <BrokenTrace />
        <p className="label mt-6">{t.notFound.label}</p>
        <h1 className="mt-3 font-display text-3xl font-medium">{t.notFound.title}</h1>
        <p className="mt-4 max-w-[42ch] text-base text-dim">{t.notFound.body}</p>
        <Link
          href={signedIn ? "/today" : "/"}
          className="press mt-9 block w-full max-w-80 rounded-md bg-sunrise py-4 text-center font-mono text-xs uppercase tracking-[0.12em] text-on-accent"
        >
          {signedIn ? t.notFound.ctaToday : t.notFound.ctaHome}
        </Link>
      </div>
    </main>
  );
}

/** The logo's rising line, cut off before it arrives: a trace that leads nowhere. */
function BrokenTrace() {
  return (
    <svg width="148" height="44" viewBox="0 0 148 44" fill="none" aria-hidden="true">
      <path d="M2 40 L46 22 L70 28" stroke="var(--line-strong)" strokeWidth="3" strokeLinecap="square" />
      <path
        d="M70 28 L112 10"
        stroke="var(--sunrise)"
        strokeWidth="3"
        strokeLinecap="square"
        strokeDasharray="2 8"
      />
      <circle cx="136" cy="10" r="4" stroke="var(--line-strong)" strokeWidth="2" />
    </svg>
  );
}
