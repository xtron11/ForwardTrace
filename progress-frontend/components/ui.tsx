"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" | "link" }) {
  const styles = {
    primary:
      "bg-sunrise text-on-accent hover:bg-ink disabled:bg-line disabled:text-dim px-5 py-2.5",
    quiet:
      "bg-transparent text-bone border border-line hover:border-bone disabled:opacity-50 px-5 py-2.5",
    link: "text-sunrise underline underline-offset-4 hover:text-bone px-0 py-0",
  }[variant];

  return (
    <button
      {...props}
      className={`rounded-sm font-display text-[length:var(--text-small)] font-semibold tracking-tight transition-colors disabled:cursor-not-allowed ${styles} ${className}`}
    />
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="label">{children}</p>;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="label mb-1.5 block">{label}</span>
      {children}
      {hint && <span className="mt-1.5 block text-[length:var(--text-small)] text-dim">{hint}</span>}
    </label>
  );
}

/** Verbatim speech. Never wrap model-written prose in this. */
export function Quote({ children }: { children: ReactNode }) {
  return (
    <p className="font-mono text-[length:var(--text-small)] leading-relaxed text-bone">
      <span className="said">{children}</span>
    </p>
  );
}

export function Notice({
  tone = "info",
  children,
}: {
  tone?: "info" | "error";
  children: ReactNode;
}) {
  const color = tone === "error" ? "text-error border-error/40" : "text-dim border-line";
  return (
    <p className={`border-l-2 pl-3 text-[length:var(--text-small)] ${color}`} role={tone === "error" ? "alert" : undefined}>
      {children}
    </p>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <p className="flex items-center gap-2.5 text-[length:var(--text-small)] text-dim" aria-live="polite">
      <span className="inline-block h-2 w-2 animate-ping rounded-full bg-sunrise" />
      {label}
    </p>
  );
}
