"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthFrame } from "@/components/AuthFrame";
import { Button, Field, Notice } from "@/components/ui";
import { ApiError, api, retryMinutes, saveTokens } from "@/lib/api";
import { describeError } from "@/lib/i18n";
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
  // What to say in place of the resend link once it has been pressed.
  const [resent, setResent] = useState<string | null>(null);

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
        // The assistant answers in this language; it becomes users.locale.
        locale,
      });
      if (isRegistered(result)) {
        // No session on purpose: the account is not usable until the link is followed.
        setAwaiting(result.email);
        setBusy(false);
        return;
      }
      saveTokens(result);
      // The first conversation starts on Today by itself.
      router.replace("/today");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError(t.auth.tooManyAttempts(retryMinutes(err)));
      } else if (err instanceof ApiError && err.status !== 409) {
        setError(t.auth.createFailed);
      } else {
        // 409 (address taken) shows the server's own sentence; a dead network shows offline.
        setError(describeError(err, t));
      }
      setBusy(false);
    }
  }

  async function resend(address: string) {
    try {
      await api.resendVerification(address);
      setResent(t.verify.resent);
    } catch (err) {
      // Anything but the limit is still "sent": the screen has nothing better to offer,
      // and the server says the same for every address.
      setResent(
        err instanceof ApiError && err.status === 429
          ? t.auth.tooManyAttempts(retryMinutes(err))
          : t.verify.resent,
      );
    }
  }

  if (awaiting) {
    return (
      <AuthFrame>
        <div className="enter">
          <p className="label mt-7 text-sunrise">{t.verify.pendingLabel}</p>
          <p className="mt-3 text-dim">{t.verify.pendingBody.replace("{email}", awaiting)}</p>

          {resent ? (
            <p className="mt-6 font-mono text-xs text-label">{resent}</p>
          ) : (
            <button
              type="button"
              onClick={() => void resend(awaiting)}
              className="press mt-6 font-mono text-xs text-label underline underline-offset-4 hover:text-bone"
            >
              {t.verify.resend}
            </button>
          )}

          <Link href="/login" className="mt-10 block font-mono text-xs text-label hover:text-bone">
            {t.auth.alreadyHave} {t.auth.signInLink}
          </Link>
        </div>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame>
      <h1 className="mt-5 text-3xl">{t.auth.createTitle}</h1>
      <p className="mt-3 text-sm text-dim">{t.auth.createLede}</p>

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

      <p className="mt-7 text-sm text-dim">
        {t.auth.alreadyHave}{" "}
        <Link href="/login" className="text-sunrise underline underline-offset-4">
          {t.auth.signInLink}
        </Link>
      </p>
    </AuthFrame>
  );
}
