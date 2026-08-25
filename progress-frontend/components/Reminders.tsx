"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { disablePush, enablePush, pushState, type PushState } from "@/lib/push";
import {
  installState,
  promptInstall,
  subscribeToInstallState,
  type InstallState,
} from "@/lib/pwa";
import { useT } from "@/lib/useT";

import { Button, Eyebrow, Notice } from "./ui";

const DISMISSED_KEY = "progress.remindersDismissed";

/**
 * Asked after the first check-in, never on arrival.
 *
 * A permission prompt shown before the person has seen what the product does is
 * answered with "block", and that answer is permanent - browsers do not ask twice. So
 * the prompt waits until they have produced something and seen it come back.
 */
export function ReminderPrompt({ onDone }: { onDone?: () => void }) {
  const { t } = useT();
  const [state, setState] = useState<PushState | null>(null);
  const [busy, setBusy] = useState(false);
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    void (async () => {
      if (window.localStorage.getItem(DISMISSED_KEY)) return;
      const current = await pushState();
      setState(current);
      // Only worth asking when it can actually be turned on.
      setHidden(!(current === "off" || current === "needs-install"));
    })();
  }, []);

  function dismiss() {
    window.localStorage.setItem(DISMISSED_KEY, "1");
    setHidden(true);
    onDone?.();
  }

  if (hidden || state === null) return null;

  return (
    <div className="card rise mt-10 p-5">
      <Eyebrow>{t.reminders.promptEyebrow}</Eyebrow>
      <p className="mt-2 max-w-[46ch] text-[17px]">{t.reminders.promptBody}</p>

      {state === "needs-install" ? (
        <p className="mt-4 text-[15px] text-muted">{t.reminders.iosInstall}</p>
      ) : (
        <div className="mt-5 flex flex-wrap items-center gap-4">
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              const next = await enablePush().catch(() => "off" as PushState);
              setState(next);
              setBusy(false);
              if (next === "on") {
                setHidden(true);
                onDone?.();
              }
            }}
          >
            {busy ? t.reminders.enabling : t.reminders.enable}
          </Button>
          <button
            onClick={dismiss}
            className="text-[14px] text-muted underline underline-offset-4 hover:text-ink"
          >
            {t.reminders.notNow}
          </button>
        </div>
      )}

      {state === "denied" && (
        <div className="mt-4">
          <Notice>{t.reminders.blocked}</Notice>
        </div>
      )}
    </div>
  );
}

/** Offer to install, wherever the browser lets us. On iOS this can only be
 *  instructions, because Safari provides no programmatic route. */
export function InstallApp() {
  const { t } = useT();
  const [state, setState] = useState<InstallState>("unavailable");

  useEffect(() => {
    const sync = () => setState(installState());
    sync();
    return subscribeToInstallState(sync);
  }, []);

  if (state === "unavailable") return null;

  return (
    <section className="border-t border-rule pt-6">
      <Eyebrow>{t.reminders.installTitle}</Eyebrow>

      {state === "installed" ? (
        <p className="mt-3 text-[15px] text-muted">{t.reminders.installed}</p>
      ) : (
        <>
          <p className="mt-3 max-w-[48ch] text-[15px] text-muted">
            {state === "manual" ? t.reminders.installBodyIos : t.reminders.installBody}
          </p>
          {state === "available" && (
            <div className="mt-4">
              <Button onClick={() => void promptInstall().then(() => setState(installState()))}>
                {t.reminders.install}
              </Button>
            </div>
          )}
        </>
      )}
    </section>
  );
}

/** Persistent control, for turning reminders on later or moving the hour. */
export function ReminderSettings() {
  const { t } = useT();
  const [state, setState] = useState<PushState | null>(null);
  const [hour, setHour] = useState(20);
  const [busy, setBusy] = useState(false);
  const [tested, setTested] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setState(await pushState());
    try {
      const me = await api.me();
      setHour(me.reminder_hour ?? 20);
    } catch {
      /* the toggle still works without it */
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (state === null) return null;

  return (
    <section className="mt-12 border-t border-rule pt-6">
      <Eyebrow>{t.reminders.title}</Eyebrow>

      {state === "unsupported" && (
        <p className="mt-3 text-[15px] text-muted">{t.reminders.unsupported}</p>
      )}
      {state === "unconfigured" && (
        <p className="mt-3 text-[15px] text-muted">{t.reminders.unconfigured}</p>
      )}
      {state === "needs-install" && (
        <p className="mt-3 max-w-[48ch] text-[15px] text-muted">{t.reminders.iosInstall}</p>
      )}
      {state === "denied" && (
        <p className="mt-3 max-w-[48ch] text-[15px] text-muted">{t.reminders.blocked}</p>
      )}

      {(state === "off" || state === "on") && (
        <>
          <p className="mt-3 max-w-[48ch] text-[15px] text-muted">
            {state === "on" ? t.reminders.onAt(hour) : t.reminders.offBody}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-4">
            <Button
              variant={state === "on" ? "quiet" : "primary"}
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setState(state === "on" ? await disablePush() : await enablePush());
                setBusy(false);
              }}
            >
              {state === "on" ? t.reminders.turnOff : t.reminders.enable}
            </Button>

            {state === "on" && (
              <>
                <label className="flex items-center gap-2 text-[14px] text-muted">
                  {t.reminders.hourLabel}
                  <select
                    className="rounded-sm border border-rule bg-card px-2 py-1 font-mono text-[13px] text-ink"
                    value={hour}
                    onChange={async (e) => {
                      const next = Number(e.target.value);
                      setHour(next);
                      await api.updateReminderSettings({ reminder_hour: next });
                    }}
                  >
                    {Array.from({ length: 24 }, (_, h) => (
                      <option key={h} value={h}>
                        {String(h).padStart(2, "0")}:00
                      </option>
                    ))}
                  </select>
                </label>

                <button
                  onClick={async () => {
                    setTested(null);
                    try {
                      await api.pushTest();
                      setTested(t.reminders.testSent);
                    } catch {
                      setTested(t.reminders.testFailed);
                    }
                  }}
                  className="text-[14px] text-signal underline underline-offset-4"
                >
                  {t.reminders.sendTest}
                </button>
              </>
            )}
          </div>

          {tested && <p className="mt-3 text-[14px] text-muted">{tested}</p>}

          <p className="mt-4 max-w-[48ch] font-mono text-[12px] leading-relaxed text-muted">
            {t.reminders.rule}
          </p>
        </>
      )}
    </section>
  );
}
