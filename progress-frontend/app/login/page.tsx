"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/Logo";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, Field, Notice } from "@/components/ui";
import { ApiError, api, saveTokens } from "@/lib/api";
import { useT } from "@/lib/useT";

export default function Login() {
  const router = useRouter();
  const { t } = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // A refusal because the address is unconfirmed needs a way forward, not just a message.
  const [unverified, setUnverified] = useState(false);
  const [resent, setResent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      saveTokens(await api.login(email.trim(), password));
      const goals = await api.listGoals();
      router.replace(goals.length ? "/today" : "/setup");
    } catch (err) {
      if (err instanceof ApiError && err.status === 410) {
        // Deleted, still inside the grace period. The server has just mailed the
        // restore link, so the way back is in their inbox, not on this screen.
        setError(t.restore.deletedOnLogin);
      } else if (err instanceof ApiError && err.status === 403) {
        setUnverified(true);
        setError(t.verify.notConfirmed);
      } else {
        setError(err instanceof ApiError ? err.message : t.auth.signInFailed);
      }
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-ink">
      <div className="mx-auto max-w-[420px] px-5 py-20">
        <div className="flex items-center justify-between">
          <Logo />
          <ThemeToggle />
        </div>
        <h1 className="mt-5 text-[2rem]">{t.auth.signInTitle}</h1>

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

          <Button type="submit" disabled={busy} className="w-full">
            {busy ? t.auth.signingIn : t.auth.signIn}
          </Button>
        </form>

        <p className="mt-7 text-[15px] text-dim">
          {t.auth.noAccount}{" "}
          <Link href="/register" className="text-sunrise underline underline-offset-4">
            {t.auth.createOne}
          </Link>
        </p>
      </div>
    </div>
  );
}
