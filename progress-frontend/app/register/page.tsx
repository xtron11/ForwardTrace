"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Field, Notice } from "@/components/ui";
import { ApiError, api, saveTokens } from "@/lib/api";
import { useT } from "@/lib/useT";

export default function Register() {
  const router = useRouter();
  const { t, locale } = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const tokens = await api.register({
        email: email.trim(),
        password,
        display_name: name.trim() || undefined,
        // Every "day" and "week" boundary is computed from this.
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        // Reports are written in this language.
        locale,
      });
      saveTokens(tokens);
      router.replace("/setup");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.auth.createFailed);
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-ink">
      <div className="mx-auto max-w-[420px] px-5 py-20">
        <h1 className="text-[2rem]">{t.auth.createTitle}</h1>
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
