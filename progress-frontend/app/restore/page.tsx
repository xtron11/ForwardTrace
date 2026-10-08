"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { api } from "@/lib/api";
import { useT } from "@/lib/useT";

export default function RestorePage() {
  return (
    <Suspense fallback={<div className="min-h-dvh bg-ink" />}>
      <Restore />
    </Suspense>
  );
}

/**
 * Where the link in the "your account was deleted" letter lands.
 *
 * Not behind the auth gate, for the same reason as /verify, and because a deleted
 * account has no session to gate with. Restoring hands out no tokens: the person signs
 * in as usual afterwards.
 */
function Restore() {
  const { t } = useT();
  const params = useSearchParams();
  const [state, setState] = useState<"checking" | "ok" | "failed">("checking");

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setState("failed");
      return;
    }
    void api
      .restoreAccount(token)
      .then(() => setState("ok"))
      .catch(() => setState("failed"));
  }, [params]);

  return (
    <div className="mx-auto flex min-h-dvh max-w-[560px] flex-col justify-center px-[26px]">
      <Logo size={38} />

      {state === "checking" && <p className="label mt-8">{t.restore.checking}</p>}

      {state === "ok" && (
        <div className="enter mt-7">
          <h1 className="font-display text-[29px] font-medium">{t.restore.okTitle}</h1>
          <p className="mt-4 text-[17px] text-dim">{t.restore.okBody}</p>
          <Link
            href="/login"
            className="press mt-9 block w-full max-w-[320px] rounded-[6px] bg-sunrise py-[17px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-on-accent"
          >
            {t.restore.okCta}
          </Link>
        </div>
      )}

      {state === "failed" && (
        <div className="enter mt-7">
          <h1 className="font-display text-[29px] font-medium">{t.restore.failTitle}</h1>
          <p className="mt-4 max-w-[42ch] text-[17px] text-dim">{t.restore.failBody}</p>
          <Link
            href="/login"
            className="press mt-9 block w-full max-w-[320px] rounded-[6px] border border-line py-[17px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-bone"
          >
            {t.restore.failCta}
          </Link>
        </div>
      )}
    </div>
  );
}
