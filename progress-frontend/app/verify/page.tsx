"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { StatusScreen } from "@/components/AuthFrame";
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

  if (state === "checking") return <StatusScreen checking={t.verify.checking} />;
  if (state === "ok") {
    return (
      <StatusScreen
        title={t.verify.okTitle}
        body={t.verify.okBody}
        cta={t.verify.okCta}
        href={isSignedIn() ? "/today" : "/login"}
      />
    );
  }
  return (
    <StatusScreen
      title={t.verify.failTitle}
      body={t.verify.failBody}
      cta={t.verify.failCta}
      href="/login"
      tone="quiet"
    />
  );
}
