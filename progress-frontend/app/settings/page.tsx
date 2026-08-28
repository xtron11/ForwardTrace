"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/Logo";
import { BareShell } from "@/components/Shell";
import { api, clearTokens } from "@/lib/api";
import {
  disablePush,
  enablePush,
  pushState,
  type PushState,
} from "@/lib/push";
import {
  installState,
  promptInstall,
  subscribeToInstallState,
  type InstallState,
} from "@/lib/pwa";
import type { User } from "@/lib/types";
import { useT } from "@/lib/useT";

const APP_VERSION = "0.1";

export default function SettingsPage() {
  return (
    <BareShell>
      <Settings />
    </BareShell>
  );
}

/** A hanging mono label beside its control, matching the report's rhythm. */
function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[92px_1fr] gap-x-4 border-t border-line py-6">
      <span className="font-mono text-[10px] uppercase leading-[1.7] tracking-[0.16em] text-label">
        {label}
      </span>
      <div>{children}</div>
    </div>
  );
}

function Settings() {
  const { t, locale } = useT();
  const router = useRouter();

  const [me, setMe] = useState<User | null>(null);
  const [push, setPush] = useState<PushState>("off");
  const [install, setInstall] = useState<InstallState>("unavailable");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void (async () => {
      setMe(await api.me().catch(() => null));
      setPush(await pushState());
    })();
    const sync = () => setInstall(installState());
    sync();
    return subscribeToInstallState(sync);
  }, []);

  async function togglePush() {
    setBusy(true);
    try {
      setPush(push === "on" ? await disablePush() : await enablePush());
    } catch {
      setPush(await pushState());
    } finally {
      setBusy(false);
    }
  }

  async function setHour(hour: number) {
    setMe((current) => (current ? { ...current, reminder_hour: hour } : current));
    await api.updateReminderSettings({ reminder_hour: hour }).catch(() => {});
  }

  const since = me
    ? new Date(me.created_at).toLocaleDateString(locale, {
        day: "numeric",
        month: "long",
      })
    : "";

  const hourLabel = `${String(me?.reminder_hour ?? 20).padStart(2, "0")}:00`;

  const action =
    "press w-full rounded-[6px] border border-line py-[15px] font-mono text-[11px] uppercase tracking-[0.14em] text-bone disabled:opacity-40";

  return (
    <div className="enter mx-auto min-h-dvh max-w-[560px] px-[26px] pb-14">
      <header className="flex items-center justify-between pt-6">
        <span className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-label">
          {t.settings.title}
        </span>
        <button
          onClick={() => router.back()}
          className="press font-mono text-[10.5px] uppercase tracking-[0.16em] text-label transition-colors hover:text-bone"
        >
          {t.settings.close}
        </button>
      </header>

      <div className="mt-10 flex items-center gap-4">
        <Logo size={38} />
        <div className="min-w-0">
          {/* Whose account this is. An address can be long, so it truncates rather than
              pushing the date off the screen. */}
          <p className="truncate font-display text-[22px] font-medium" title={me?.email}>
            {me?.display_name || me?.email || ""}
          </p>
          {me?.display_name && me.email && (
            <p className="truncate font-mono text-[11px] text-dim">{me.email}</p>
          )}
          {since && (
            <p className="mt-0.5 font-mono text-[11px] text-label">
              {t.settings.withUsSince} {since.toUpperCase()}
            </p>
          )}
        </div>
      </div>

      <div className="mt-10">
        <Row label={t.settings.appLabel}>
          {install === "installed" ? (
            <p className="text-[16px] text-dim">{t.settings.installed}</p>
          ) : (
            <>
              <p className="max-w-[40ch] text-[16px] text-dim">
                {install === "manual" ? t.reminders.iosInstall : t.settings.installBody}
              </p>
              {install === "available" && (
                <button
                  onClick={() => void promptInstall().then(() => setInstall(installState()))}
                  className={`${action} mt-4`}
                >
                  {t.settings.install}
                </button>
              )}
            </>
          )}
        </Row>

        <Row label={t.settings.remindersLabel}>
          {push === "unsupported" || push === "unconfigured" ? (
            <p className="text-[16px] text-dim">{t.reminders.unsupported}</p>
          ) : push === "needs-install" ? (
            <p className="text-[16px] text-dim">{t.reminders.iosInstall}</p>
          ) : push === "denied" ? (
            <p className="text-[16px] text-dim">{t.reminders.unsupported}</p>
          ) : (
            <>
              <p className="max-w-[40ch] text-[16px] text-dim">
                {push === "on"
                  ? t.settings.remindersOn(hourLabel)
                  : t.settings.remindersOff}
              </p>
              <button onClick={togglePush} disabled={busy} className={`${action} mt-4`}>
                {push === "on" ? t.reminders.turnOff : t.reminders.enable}
              </button>
              {push === "on" && (
                <button
                  onClick={() => void api.pushTest().catch(() => {})}
                  className="press mt-3 font-mono text-[11px] uppercase tracking-[0.14em] text-label transition-colors hover:text-bone"
                >
                  {t.reminders.sendTest}
                </button>
              )}
            </>
          )}
        </Row>

        {push === "on" && (
          <Row label={t.settings.timeLabel}>
            <div className="flex flex-wrap gap-2">
              {[7, 12, 18, 20, 21, 22].map((hour) => (
                <button
                  key={hour}
                  onClick={() => setHour(hour)}
                  aria-pressed={me?.reminder_hour === hour}
                  className={`border px-3 py-1.5 font-mono text-[12px] transition-colors ${
                    me?.reminder_hour === hour
                      ? "border-sunrise text-sunrise"
                      : "border-line text-label hover:text-bone"
                  }`}
                >
                  {String(hour).padStart(2, "0")}:00
                </button>
              ))}
            </div>
          </Row>
        )}

        <div className="grid grid-cols-[92px_1fr] gap-x-4 border-y border-line py-6">
          <span className="font-mono text-[10px] uppercase leading-[1.7] tracking-[0.16em] text-label">
            {t.settings.version}
          </span>
          <span className="font-mono text-[13px] text-dim">{APP_VERSION}</span>
        </div>
      </div>

      <button
        onClick={() => {
          clearTokens();
          router.replace("/login");
        }}
        className="press mt-10 font-mono text-[11px] uppercase tracking-[0.16em] text-label transition-colors hover:text-error"
      >
        {t.settings.signOut}
      </button>
    </div>
  );
}
