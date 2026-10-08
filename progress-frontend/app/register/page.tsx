"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, Field, Notice } from "@/components/ui";
import { ApiError, api, saveTokens } from "@/lib/api";
import type { Registered, Tokens } from "@/lib/types";
import { useT } from "@/lib/useT";

/** Distinguishes the two shapes registration can return. */
function isRegistered(value: Tokens | Registered): value is Registered {
  return "verification_required" in value;
}

export default function Register() {
  const router = useRouter();
  const { t, locale } = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Set when the account exists but the address has yet to be confirmed.
  const [awaiting, setAwaiting] = useState<string | null>(null);
  const [resent, setResent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await api.register({
        email: email.trim(),
        password,
        display_name: name.trim() || undefined,
        // Every "day" and "week" boundary is computed from this.
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        // Reports are written in this language.
        locale,
      });
      if (isRegistered(result)) {
        // No session on purpose: the account is not usable until the link is followed.
        setAwaiting(result.email);
        setBusy(false);
        return;
      }
      saveTokens(result);
      router.replace("/setup");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.auth.createFailed);
      setBusy(false);
    }
  }

  if (awaiting) {
    return (
      <div className="min-h-dvh bg-ink">
        <div className="enter mx-auto max-w-[420px] px-5 py-20">
          <div className="flex items-center justify-between">
            <Logo />
            <ThemeToggle />
          </div>
          <p className="label mt-7" style={{ color: "var(--color-sunrise)" }}>
            {t.verify.pendingLabel}
          </p>
          <p className="mt-3 text-[17px] leading-[1.55] text-dim">
            {t.verify.pendingBody.replace("{email}", awaiting)}
          </p>

          {resent ? (
            <p className="mt-6 font-mono text-[12px] text-label">{t.verify.resent}</p>
          ) : (
            <button
              onClick={async () => {
                await api.resendVerification(awaiting).catch(() => {});
                setResent(true);
              }}
              className="press mt-6 font-mono text-[12px] text-label underline underline-offset-4 hover:text-bone"
            >
              {t.verify.resend}
            </button>
          )}

          <Link
            href="/login"
            className="mt-10 block font-mono text-[12px] text-label hover:text-bone"
          >
            {t.auth.alreadyHave} {t.auth.signInLink}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-ink">
      <div className="mx-auto max-w-[420px] px-5 py-20">
        <div className="flex items-center justify-between">
          <Logo />
          <ThemeToggle />
        </div>
        <h1 className="mt-5 text-[2rem]">{t.auth.createTitle}</h1>
        <p className="mt-3 text-[15px] text-dim">
{t.auth.createLede}
        </p>

        <form onSubmit={submit} className="mt-9 space-y-5">
          <Field label={t.auth.email}>
            <input
              type="email"
              required
              autoComplete="email"
              className="field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>

          <Field label={t.auth.password} hint={t.auth.passwordHint}>
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              className="field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>

          <Field label={t.auth.name} hint={t.auth.nameHint}>
            <input
              type="text"
              autoComplete="name"
              className="field"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>

          {error && <Notice tone="error">{error}</Notice>}

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? t.auth.creating : t.auth.create}
          </Button>
        </form>

        <p className="mt-7 text-[15px] text-dim">
          {t.auth.alreadyHave}{" "}
          <Link href="/login" className="text-sunrise underline underline-offset-4">
            {t.auth.signInLink}
          </Link>
        </p>
      </div>
    </div>
  );
}
