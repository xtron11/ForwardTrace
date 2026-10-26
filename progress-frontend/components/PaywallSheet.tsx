"use client";

import { useEffect, useState } from "react";

import { Button, Notice } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { describeError } from "@/lib/i18n";
import { useT } from "@/lib/useT";

/**
 * Opens when a message is refused with `limit_reached`. In the beta the "door" is fake:
 * pressing "Continue with Plus" grants a month without limits and shows "We're in beta —
 * you get a month free"; closing it then lets the screen send the refused message again
 * (`onGranted`). Plus promises only unlimited conversations. Each opening is reported as
 * `paywall_viewed`; the click is recorded by the server (`paywall_clicked`).
 */
export function PaywallSheet({
  open,
  onClose,
  onGranted,
}: {
  open: boolean;
  onClose: () => void;
  onGranted: () => void;
}) {
  const { t, locale } = useT();
  const [working, setWorking] = useState(false);
  const [until, setUntil] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) void api.logEvent("paywall_viewed");
  }, [open]);

  if (!open) return null;

  async function claim() {
    setWorking(true);
    setError(null);
    try {
      const res = await api.paywallClick();
      setUntil(res.plus_until);
    } catch (err) {
      setError(describeError(err, t));
    } finally {
      setWorking(false);
    }
  }

  function close() {
    const granted = until !== null;
    setUntil(null);
    setError(null);
    if (granted) onGranted();
    else onClose();
  }

  return (
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-scrim" role="presentation" onClick={close}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="paywall-title"
        onClick={(e) => e.stopPropagation()}
        className="enter w-full max-w-(--column-max) rounded-t-lg bg-surface px-(--page-pad) pt-6"
        style={{ paddingBottom: "calc(1.5rem + env(safe-area-inset-bottom))" }}
      >
        <h2 id="paywall-title" className="text-[length:var(--text-base)]">
          {until ? t.paywall.beta : t.paywall.title}
        </h2>
        {until ? (
          <p className="mt-3 text-muted">
            {t.paywall.granted(formatDay(until.slice(0, 10), locale, { day: "numeric", month: "long" }))}
          </p>
        ) : (
          <>
            <p className="mt-3 text-muted">{t.paywall.body}</p>
            <p className="mt-2 text-[length:var(--text-small)] text-dim">{t.paywall.resets}</p>
          </>
        )}
        {error && (
          <div className="mt-3">
            <Notice tone="error">{error}</Notice>
          </div>
        )}
        <div className="mt-5 flex flex-wrap gap-3">
          {!until && (
            <Button onClick={() => void claim()} disabled={working}>
              {working ? t.paywall.working : t.paywall.cta}
            </Button>
          )}
          <Button variant="quiet" onClick={close}>
            {t.paywall.close}
          </Button>
        </div>
      </div>
    </div>
  );
}
