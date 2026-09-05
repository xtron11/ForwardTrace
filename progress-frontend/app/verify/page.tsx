"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { api, isSignedIn } from "@/lib/api";
import { useT } from "@/lib/useT";

export default function VerifyPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh bg-ink" />}>
      <Verify />
    </Suspense>
  );
}

/**
 * Where the link in the letter lands.
 *
 * Not behind the auth gate on purpose: people open mail in whichever browser happens
 * to be handy, and that one usually has no session. Requiring a login here would send
 * them to a sign-in screen and lose the token in the process.
 */
function Verify() {
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
      .verifyEmail(token)
      .then(() => setState("ok"))
      .catch(() => setState("failed"));
  }, [params]);

  return (
    <div className="mx-auto flex min-h-dvh max-w-[560px] flex-col justify-center px-[26px]">
      <Logo size={38} />

      {state === "checking" && (
        <p className="label mt-8">{t.verify.checking}</p>
      )}

      {state === "ok" && (
        <div className="enter mt-7">
          <h1 className="font-display text-[29px] font-medium">{t.verify.okTitle}</h1>
          <p className="mt-4 text-[17px] text-dim">{t.verify.okBody}</p>
          <Link
            href={isSignedIn() ? "/today" : "/login"}
            className="press mt-9 block w-full max-w-[320px] rounded-[6px] bg-sunrise py-[17px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-on-accent"
          >
            {t.verify.okCta}
          </Link>
        </div>
      )}

      {state === "failed" && (
        <div className="enter mt-7">
          <h1 className="font-display text-[29px] font-medium">{t.verify.failTitle}</h1>
          <p className="mt-4 max-w-[42ch] text-[17px] text-dim">{t.verify.failBody}</p>
          <Link
            href="/login"
            className="press mt-9 block w-full max-w-[320px] rounded-[6px] border border-line py-[17px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-bone"
          >
            {t.verify.failCta}
          </Link>
        </div>
      )}
    </div>
  );
}
