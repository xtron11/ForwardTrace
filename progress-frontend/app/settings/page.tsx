"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

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
import type { AccountDeleted, User } from "@/lib/types";
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

/** Asked before anything happens, with the cancel button focused: an account is the
 *  one thing on this screen a slip of the finger should not cost. */
function ConfirmDelete({
  busy,
  error,
  onConfirm,
  onCancel,
}: {
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useT();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => cancelRef.current?.focus(), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onCancel]);

  return (
    <div
      className="fixed inset-0 z-20 flex items-end justify-center bg-ink/85 px-4 pb-6 sm:items-center sm:pb-0"
      onClick={() => !busy && onCancel()}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-title"
        aria-describedby="delete-body"
        onClick={(e) => e.stopPropagation()}
        className="enter w-full max-w-[420px] rounded-[8px] border border-line bg-ink p-6"
      >
        <h2 id="delete-title" className="font-display text-[22px] font-medium leading-snug">
          {t.settings.deleteTitle}
        </h2>
        <p id="delete-body" className="mt-3 text-[16px] text-dim">
          {t.settings.deleteBody}
        </p>
        {error && (
          <p role="alert" className="mt-4 text-[14px] text-error">
            {error}
          </p>
        )}
        <div className="mt-7 grid grid-cols-2 gap-3">
          <button
            ref={cancelRef}
            onClick={onCancel}
            disabled={busy}
            className="press rounded-[6px] border border-line py-[15px] font-mono text-[11px] uppercase tracking-[0.14em] text-bone disabled:opacity-40"
          >
            {t.settings.deleteCancel}
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className="press rounded-[6px] border border-error bg-error py-[15px] font-mono text-[11px] uppercase tracking-[0.14em] text-bone disabled:opacity-60"
          >
            {busy ? t.settings.deleting : t.settings.deleteConfirm}
          </button>
        </div>
      </div>
    </div>
  );
}

/** The account is locked by now and the session gone, so this is the last thing the
 *  screen can say: how long the way back stays open, and where it was sent. */
function Deleted({ result }: { result: AccountDeleted }) {
  const { t, locale } = useT();
  // A plain date, not a moment: parsed as local so it cannot slide a day west of UTC.
  const [y, m, d] = result.erase_on.split("-").map(Number);
  const until = new Date(y, m - 1, d).toLocaleDateString(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="enter mx-auto flex min-h-dvh max-w-[560px] flex-col justify-center px-[26px]">
      <Logo size={38} />
      <h1 className="mt-7 font-display text-[29px] font-medium">{t.settings.deletedTitle}</h1>
      <p className="mt-4 max-w-[44ch] text-[17px] text-dim">
        {t.settings.deletedBody(result.restore_days, until, result.email)}
      </p>
      {!result.letter_sent && (
        <p className="mt-4 max-w-[44ch] text-[15px] text-dim">{t.settings.deletedNoLetter}</p>
      )}
      <Link
        href="/"
        className="press mt-9 block w-full max-w-[320px] rounded-[6px] border border-line py-[17px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-bone"
      >
        {t.settings.deletedCta}
      </Link>
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
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleted, setDeleted] = useState<AccountDeleted | null>(null);

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

  async function deleteAccount() {
    setDeleting(true);
    setDeleteError(null);
    try {
      const result = await api.deleteAccount();
      // The server has already ended every session; drop the dead tokens too.
      clearTokens();
      setDeleted(result);
      setConfirming(false);
    } catch {
      setDeleteError(t.settings.deleteFailed);
    } finally {
      setDeleting(false);
    }
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

  if (deleted) return <Deleted result={deleted} />;

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

      <button
        onClick={() => {
          setDeleteError(null);
          setConfirming(true);
        }}
        className="press mt-6 block font-mono text-[11px] uppercase tracking-[0.16em] text-error/80 transition-colors hover:text-error"
      >
        {t.settings.deleteAccount}
      </button>

      {confirming && (
        <ConfirmDelete
          busy={deleting}
          error={deleteError}
          onConfirm={() => void deleteAccount()}
          onCancel={() => setConfirming(false)}
        />
      )}
    </div>
  );
}
