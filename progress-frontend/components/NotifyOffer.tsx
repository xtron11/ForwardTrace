"use client";

import { useEffect, useState } from "react";

import { useUser } from "@/components/AppShell";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { enablePush, isStandalone, type PushState } from "@/lib/push";
import { useT } from "@/lib/useT";

type Phase = "ask" | "on" | "off";

function onIphoneBrowser(): boolean {
  return /iPad|iPhone|iPod/.test(navigator.userAgent) && !isStandalone();
}

/**
 * After the first conversation: ask for notification permission (it must follow a tap),
 * and if that is refused, impossible (iPhone outside the home screen) or not set up,
 * offer Telegram instead - but only when the server can hand out a link.
 */
export function NotifyOffer({ hour, onClose }: { hour: number; onClose: () => void }) {
  const { t } = useT();
  const { user, setUser } = useUser();
  const [phase, setPhase] = useState<Phase>("ask");
  const [busy, setBusy] = useState(false);
  const [telegramUrl, setTelegramUrl] = useState<string | null>(null);
  const [iphone, setIphone] = useState(false);

  // An iPhone without the installed app cannot be asked at all: go straight to the
  // alternative. Probing the link also tells whether Telegram is switched on.
  useEffect(() => {
    setIphone(onIphoneBrowser());
  }, []);

  async function probeTelegram() {
    try {
      const { url } = await api.telegramLink();
      setTelegramUrl(url);
    } catch {
      setTelegramUrl(null); // 503 telegram_disabled: the option stays hidden
    }
  }

  useEffect(() => {
    if (iphone) void probeTelegram();
  }, [iphone]);

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
      await probeTelegram();
    }
    setBusy(false);
  }

  async function skip() {
    await probeTelegram();
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
            <Button variant="quiet" onClick={() => void skip()}>
              {t.notify.later}
            </Button>
          </div>
        </>
      )}

      {phase === "ask" && iphone && (
        <>
          <p className="mt-2 text-muted">{t.notify.iosInstall}</p>
          <TelegramBlock url={telegramUrl} />
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
          <TelegramBlock url={telegramUrl} />
          <p className="mt-3 text-[length:var(--text-small)] text-dim">{t.notify.laterInProfile}</p>
          <Button className="mt-4" variant="quiet" onClick={onClose}>
            {t.paywall.close}
          </Button>
        </>
      )}
    </section>
  );
}

function TelegramBlock({ url }: { url: string | null }) {
  const { t } = useT();
  if (!url) return null;
  return (
    <div className="mt-3">
      <p className="text-muted">{t.notify.telegramBody}</p>
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="mt-2 inline-block rounded-sm bg-sunrise px-5 py-2.5 font-display text-[length:var(--text-small)] font-semibold text-on-accent"
      >
        {t.notify.telegramCta}
      </a>
    </div>
  );
}
