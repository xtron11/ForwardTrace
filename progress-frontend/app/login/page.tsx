"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/Logo";
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

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      saveTokens(await api.login(email.trim(), password));
      const goals = await api.listGoals();
      router.replace(goals.length ? "/today" : "/setup");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.auth.signInFailed);
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-ink">
      <div className="mx-auto max-w-[420px] px-5 py-20">
        <Logo />
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
