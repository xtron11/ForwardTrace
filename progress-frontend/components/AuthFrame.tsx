"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";

/** Frame of the sign-in screens: logo and theme switch on top, a narrow column below. */
export function AuthFrame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-ink">
      <div className="mx-auto max-w-105 px-(--page-pad) py-16">
        <div className="flex items-center justify-between text-bone">
          <Logo />
          <ThemeToggle />
        </div>
        {children}
      </div>
    </div>
  );
}

/** A full-screen message with one way onward: used by /verify and /restore. */
export function StatusScreen({
  checking,
  title,
  body,
  cta,
  href,
  tone = "primary",
}: {
  /** While set, only this label shows (the request is still running). */
  checking?: string;
  title?: string;
  body?: string;
  cta?: string;
  href?: string;
  tone?: "primary" | "quiet";
}) {
  const style = tone === "primary" ? "bg-sunrise text-on-accent" : "border border-line text-bone";

  return (
    <div className="mx-auto flex min-h-dvh max-w-(--column-max) flex-col justify-center px-(--page-pad)">
      <div className="text-bone">
        <Logo size={38} />
      </div>
      {checking ? (
        <p className="label mt-8" aria-live="polite">
          {checking}
        </p>
      ) : (
        <div className="enter mt-7">
          <h1 className="font-display text-3xl font-medium">{title}</h1>
          <p className="mt-4 max-w-[42ch] text-dim">{body}</p>
          {cta && href && (
            <Link
              href={href}
              className={`press mt-9 block w-full max-w-80 rounded-md py-4 text-center font-mono text-xs uppercase tracking-[0.12em] ${style}`}
            >
              {cta}
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
