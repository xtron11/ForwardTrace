"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthFrame } from "@/components/AuthFrame";
import { Button, Field, Notice } from "@/components/ui";
import { ApiError, api, retryMinutes, saveTokens } from "@/lib/api";
import { toLocale } from "@/lib/i18n";
import { setLocale, useT } from "@/lib/useT";

export default function Login() {
  const router = useRouter();
  const { t } = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // A refusal because the address is unconfirmed needs a way forward, not just a message.
  const [unverified, setUnverified] = useState(false);
  const [resent, setResent] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setUnverified(false);
    setResent(null);
    setBusy(true);
    try {
      saveTokens(await api.login(email.trim(), password));
      // The interface speaks the language stored on the account from here on.
      try {
        setLocale(toLocale((await api.me()).locale));
      } catch {
        /* AppShell loads it again on /today */
      }
      router.replace("/today");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError(t.auth.tooManyAttempts(retryMinutes(err)));
      } else if (err instanceof ApiError && err.status === 410) {
        // Deleted, still inside the grace period. The server has just mailed the
        // restore link, so the way back is in their inbox, not on this screen.
        setError(t.restore.deletedOnLogin);
      } else if (err instanceof ApiError && err.status === 403) {
        setUnverified(true);
        setError(t.verify.notConfirmed);
      } else {
        setError(err instanceof ApiError ? t.auth.signInFailed : t.errors.offline);
      }
      setBusy(false);
    }
  }

  async function resend() {
    try {
      await api.resendVerification(email.trim());
      setResent(t.verify.resent);
    } catch (err) {
      // Anything but the limit is still "sent": the server says the same for every address.
      setResent(
        err instanceof ApiError && err.status === 429
          ? t.auth.tooManyAttempts(retryMinutes(err))
          : t.verify.resent,
      );
    }
  }

  return (
    <AuthFrame>
      <h1 className="mt-5 text-3xl">{t.auth.signInTitle}</h1>

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

        <Field label={t.auth.password}>
          <input
            type="password"
            required
            autoComplete="current-password"
            className="field"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>

        {error && <Notice tone="error">{error}</Notice>}

        {unverified &&
          (resent ? (
            <p className="font-mono text-xs text-label">{resent}</p>
          ) : (
            <button
              type="button"
              onClick={resend}
              className="press font-mono text-xs text-label underline underline-offset-4 hover:text-bone"
            >
              {t.verify.resend}
            </button>
          ))}

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? t.auth.signingIn : t.auth.signIn}
        </Button>
      </form>

      <p className="mt-7 text-sm text-dim">
        {t.auth.noAccount}{" "}
        <Link href="/register" className="text-sunrise underline underline-offset-4">
          {t.auth.createOne}
        </Link>
      </p>
    </AuthFrame>
  );
}
