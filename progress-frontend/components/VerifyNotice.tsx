"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { useT } from "@/lib/useT";

/**
 * Shown until the address is confirmed.
 *
 * Placed above the record button because that is the thing which will refuse to work,
 * and finding that out by being turned away is worse than being told beforehand.
 */
export function VerifyNotice() {
  const { t } = useT();
  const [me, setMe] = useState<User | null>(null);
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api.me().then(setMe).catch(() => setMe(null));
  }, []);

  if (!me || me.email_verified) return null;

  return (
    <div className="mt-6 border border-sunrise/40 px-4 py-4">
      <p className="label" style={{ color: "var(--color-sunrise)" }}>
        {t.verify.pendingLabel}
      </p>
      <p className="mt-2 text-[16px] leading-[1.5] text-dim">
        {t.verify.pendingBody.replace("{email}", me.email)}
      </p>

      {sent ? (
        <p className="mt-3 font-mono text-[12px] text-label">{t.verify.resent}</p>
      ) : (
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            await api.resendVerification().catch(() => {});
            setSent(true);
            setBusy(false);
          }}
          className="press mt-3 font-mono text-[12px] text-label underline underline-offset-4 transition-colors hover:text-bone disabled:opacity-50"
        >
          {t.verify.resend}
        </button>
      )}
    </div>
  );
}
