"use client";

import { useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { Button } from "@/components/ui";
import { api, openTelegramLink } from "@/lib/api";
import { describeError } from "@/lib/i18n";
import { enablePush, isStandalone, type PushState } from "@/lib/push";
import { useT } from "@/lib/useT";

type Phase = "ask" | "on" | "off";

function onIphoneBrowser(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) && !isStandalone();
}

/**
 * After the first conversation: ask for notification permission (it must follow a tap),
 * and if that is refused, impossible (iPhone outside the home screen) or not set up,
 * offer Telegram instead - but only when the server runs the bot.
 */
export function NotifyOffer({ hour, onClose }: { hour: number; onClose: () => void }) {
  const { t } = useT();
  const { user, setUser } = useUser();
  const [phase, setPhase] = useState<Phase>("ask");
  const [busy, setBusy] = useState(false);
  const [iphone, setIphone] = useState(false);

  // An iPhone without the installed app cannot be asked at all: go straight to the
  // alternative.
  useEffect(() => {
    setIphone(onIphoneBrowser());
  }, []);

  async function allow() {
    setBusy(true);
    let state: PushState = "off";
    try {
      state = await enablePush();
    } catch {
      state = "off";
    }
    if (state === "on") {
      try {
        setUser(await api.updateMe({ outreach_channel: "push" }));
      } catch {
        /* the subscription exists; the channel keeps its default */
      }
      setPhase("on");
    } else {
      setPhase("off");
    }
    setBusy(false);
  }

  function skip() {
    setPhase("off");
  }

  if (user.outreach_channel === "telegram" && user.telegram_linked) return null;

  return (
    <section className="enter rounded-md border border-line p-4" aria-label={t.notify.title}>
      <h2 className="text-[length:var(--text-base)]">{t.notify.title}</h2>

      {phase === "ask" && !iphone && (
        <>
          <p className="mt-2 text-muted">{t.notify.body}</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={() => void allow()} disabled={busy}>
              {t.notify.allow}
            </Button>
            <Button variant="quiet" onClick={skip}>
              {t.notify.later}
            </Button>
          </div>
        </>
      )}

      {phase === "ask" && iphone && (
        <>
          <p className="mt-2 text-muted">{t.notify.iosInstall}</p>
          <TelegramBlock available={user.telegram_available} />
          <Button className="mt-4" variant="quiet" onClick={onClose}>
            {t.notify.later}
          </Button>
        </>
      )}

      {phase === "on" && (
        <>
          <p className="mt-2 text-muted">{t.notify.done(hour)}</p>
          <Button className="mt-4" variant="quiet" onClick={onClose}>
            {t.paywall.close}
          </Button>
        </>
      )}

      {phase === "off" && (
        <>
          <p className="mt-2 text-muted">{t.notify.failed}</p>
          <TelegramBlock available={user.telegram_available} />
          <p className="mt-3 text-[length:var(--text-small)] text-dim">{t.notify.laterInProfile}</p>
          <Button className="mt-4" variant="quiet" onClick={onClose}>
            {t.paywall.close}
          </Button>
        </>
      )}
    </section>
  );
}

function TelegramBlock({ available }: { available: boolean }) {
  const { t } = useT();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!available) return null;

  // The link is one-time: it is made on the tap.
  async function connect() {
    setBusy(true);
    setError(null);
    try {
      await openTelegramLink();
    } catch (err) {
      setError(describeError(err, t));
    }
    setBusy(false);
  }

  return (
    <div className="mt-3">
      <p className="text-muted">{t.notify.telegramBody}</p>
      <button
        type="button"
        onClick={() => void connect()}
        disabled={busy}
        className="mt-2 inline-block rounded-sm bg-sunrise px-5 py-2.5 font-display text-[length:var(--text-small)] font-semibold text-on-accent disabled:opacity-60"
      >
        {t.notify.telegramCta}
      </button>
      {error && <p className="mt-2 text-[length:var(--text-small)] text-dim">{error}</p>}
    </div>
  );
}
