"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { StatusScreen } from "@/components/AuthFrame";
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

  if (state === "checking") return <StatusScreen checking={t.restore.checking} />;
  if (state === "ok") {
    return (
      <StatusScreen
        title={t.restore.okTitle}
        body={t.restore.okBody}
        cta={t.restore.okCta}
        href="/login"
      />
    );
  }
  return (
    <StatusScreen
      title={t.restore.failTitle}
      body={t.restore.failBody}
      cta={t.restore.failCta}
      href="/login"
      tone="quiet"
    />
  );
}
