"use client";

import { useEffect, useState, type ReactNode } from "react";

import { useUser } from "@/components/AppShell";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, Field, Notice } from "@/components/ui";
import { api } from "@/lib/api";
import { todayIn } from "@/lib/dates";
import { describeError, toLocale, type Locale } from "@/lib/i18n";
import { installState, promptInstall, subscribeToInstallState, type InstallState } from "@/lib/pwa";
import type { Goal, OutreachChannel, UserPatch } from "@/lib/types";
import { useT } from "@/lib/useT";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line py-6">
      <h2 className="label mb-4">{title}</h2>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  );
}

const HOURS = Array.from({ length: 24 }, (_, h) => h);

export function ProfileScreen() {
  const { t } = useT();
  const { user, setUser, signOut } = useUser();
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const [goal, setGoal] = useState<Goal | null>(null);
  const [goalLoaded, setGoalLoaded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [why, setWhy] = useState("");
  const [finish, setFinish] = useState("");
  const [noFinish, setNoFinish] = useState(false);
  const [savingGoal, setSavingGoal] = useState(false);

  const [telegramUrl, setTelegramUrl] = useState<string | null>(null);
  const [install, setInstall] = useState<InstallState>("unavailable");
  const [exporting, setExporting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  useEffect(() => {
    api
      .memory()
      .then((m) => setGoal(m.goal))
      .catch(() => {})
      .finally(() => setGoalLoaded(true));
  }, []);

  // Telegram is offered only when the server can hand out a link (503 while it is off).
  useEffect(() => {
    if (user.telegram_linked) return;
    api
      .telegramLink()
      .then((r) => setTelegramUrl(r.url))
      .catch(() => setTelegramUrl(null));
  }, [user.telegram_linked]);

  useEffect(() => {
    const refresh = () => setInstall(installState());
    refresh();
    return subscribeToInstallState(refresh);
  }, []);

  async function patch(data: UserPatch) {
    setError(null);
    setSaved(null);
    try {
      setUser(await api.updateMe(data));
      setSaved(t.profile.saved);
    } catch (err) {
      setError(describeError(err, t));
    }
  }

  function startEditing() {
    if (!goal) return;
    setTitle(goal.title);
    setWhy(goal.why_text ?? "");
    setFinish(goal.finish_line ?? "");
    setNoFinish(goal.finish_line === null);
    setEditing(true);
  }

  async function saveGoal() {
    if (!goal) return;
    setSavingGoal(true);
    setError(null);
    setSaved(null);
    const body: { title?: string; why_text?: string; finish_line?: string | null } = {};
    if (title.trim() && title.trim() !== goal.title) body.title = title.trim();
    if (why.trim() !== (goal.why_text ?? "")) body.why_text = why.trim();
    const nextFinish = noFinish ? null : finish.trim() || null;
    if (nextFinish !== goal.finish_line) body.finish_line = nextFinish;
    try {
      if (Object.keys(body).length) setGoal(await api.patchGoal(body));
      setEditing(false);
      setSaved(t.profile.saved);
    } catch (err) {
      setError(describeError(err, t));
    }
    setSavingGoal(false);
  }

  async function exportData() {
    setExporting(true);
    setError(null);
    const blob = await api.exportData();
    setExporting(false);
    if (!blob) {
      setError(t.errors.generic);
      return;
    }
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `forwardtrace-export-${todayIn(user.timezone)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function deleteAccount() {
    setError(null);
    try {
      await api.deleteAccount();
      signOut();
    } catch (err) {
      setError(describeError(err, t));
      setConfirmDelete(false);
    }
  }

  const channels: { value: OutreachChannel; label: string }[] = [
    { value: "push", label: t.profile.channelPush },
    ...(user.telegram_linked ? [{ value: "telegram" as const, label: t.profile.channelTelegram }] : []),
    { value: "none", label: t.profile.channelNone },
  ];

  return (
    <div className="enter pt-2">
      <h1 className="text-[length:var(--text-base)]">{t.profile.title}</h1>

      {(error || saved) && (
        <div className="mt-4">
          <Notice tone={error ? "error" : "info"}>{error ?? saved}</Notice>
        </div>
      )}

      <Section title={t.profile.account}>
        <p className="break-all">{user.email}</p>
      </Section>

      <Section title={t.profile.goal}>
        {!goalLoaded ? null : !goal ? (
          <p className="text-dim">{t.profile.noGoal}</p>
        ) : editing ? (
          <>
            <Field label={t.profile.goalTitle}>
              <input className="field" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
            </Field>
            <Field label={t.profile.goalWhy}>
              <textarea className="field" rows={3} value={why} onChange={(e) => setWhy(e.target.value)} />
            </Field>
            <Field label={t.profile.goalFinish}>
              <input
                className="field"
                value={finish}
                maxLength={120}
                disabled={noFinish}
                onChange={(e) => setFinish(e.target.value)}
              />
            </Field>
            <label className="flex items-start gap-2 text-[length:var(--text-small)] text-muted">
              <input
                type="checkbox"
                className="mt-1 accent-(--sunrise)"
                checked={noFinish}
                onChange={(e) => setNoFinish(e.target.checked)}
              />
              {t.profile.noFinishToggle}
            </label>
            <div className="flex gap-3">
              <Button onClick={() => void saveGoal()} disabled={savingGoal || !title.trim()}>
                {savingGoal ? t.profile.saving : t.profile.save}
              </Button>
              <Button variant="quiet" onClick={() => setEditing(false)} disabled={savingGoal}>
                {t.profile.cancel}
              </Button>
            </div>
          </>
        ) : (
          <>
            <div>
              <p className="label">{t.profile.goalTitle}</p>
              <p className="mt-1">{goal.title}</p>
            </div>
            <div>
              <p className="label">{t.profile.goalWhy}</p>
              <p className="mt-1">{goal.why_text ?? "—"}</p>
            </div>
            <div>
              <p className="label">{t.profile.goalFinish}</p>
              <p className="mt-1">{goal.finish_line ?? t.profile.noFinish}</p>
            </div>
            <div>
              <Button variant="quiet" onClick={startEditing}>
                {t.profile.edit}
              </Button>
            </div>
          </>
        )}
      </Section>

      <Section title={t.profile.messages}>
        <Field label={t.profile.hour}>
          <select
            className="field"
            value={user.reminder_hour}
            onChange={(e) => void patch({ reminder_hour: Number(e.target.value) })}
          >
            {HOURS.map((h) => (
              <option key={h} value={h}>
                {String(h).padStart(2, "0")}:00
              </option>
            ))}
          </select>
        </Field>

        <fieldset className="flex flex-col gap-2">
          <legend className="label mb-1.5">{t.profile.channel}</legend>
          {channels.map((c) => (
            <label key={c.value} className="flex items-center gap-2.5 py-1">
              <input
                type="radio"
                name="channel"
                className="accent-(--sunrise)"
                checked={user.outreach_channel === c.value}
                onChange={() => void patch({ outreach_channel: c.value })}
              />
              {c.label}
            </label>
          ))}
        </fieldset>

        {user.telegram_linked ? (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-muted">{t.profile.telegramLinked}</p>
            <Button
              variant="quiet"
              onClick={async () => {
                setError(null);
                try {
                  await api.telegramUnlink();
                  setUser(await api.me());
                } catch (err) {
                  setError(describeError(err, t));
                }
              }}
            >
              {t.profile.telegramUnlink}
            </Button>
          </div>
        ) : (
          telegramUrl && (
            <div>
              <a
                href={telegramUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-block rounded-sm border border-line px-5 py-2.5 font-display text-[length:var(--text-small)] font-semibold hover:border-bone"
              >
                {t.profile.telegramConnect}
              </a>
              <p className="mt-2 text-[length:var(--text-small)] text-dim">{t.profile.telegramHint}</p>
            </div>
          )
        )}
      </Section>

      <Section title={t.profile.appearance}>
        <Field label={t.profile.language}>
          <select
            className="field"
            value={toLocale(user.locale)}
            onChange={(e) => void patch({ locale: e.target.value as Locale })}
          >
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </Field>
        <div className="flex items-center gap-3">
          <span className="label">{t.profile.theme}</span>
          <ThemeToggle />
        </div>
        {install === "available" && (
          <div>
            <Button variant="quiet" onClick={() => void promptInstall()}>
              {t.profile.install}
            </Button>
          </div>
        )}
        {install === "manual" && <p className="text-[length:var(--text-small)] text-dim">{t.profile.installManual}</p>}
        {install === "installed" && <p className="text-[length:var(--text-small)] text-dim">{t.profile.installed}</p>}
      </Section>

      <Section title={t.profile.data}>
        <div>
          <Button variant="quiet" onClick={() => void exportData()} disabled={exporting}>
            {exporting ? t.profile.exporting : t.profile.export}
          </Button>
        </div>
        {confirmDelete ? (
          <div className="flex flex-col gap-3">
            <p className="text-muted">{t.profile.deleteAsk}</p>
            <div className="flex gap-3">
              <Button onClick={() => void deleteAccount()}>{t.profile.deleteYes}</Button>
              <Button variant="quiet" onClick={() => setConfirmDelete(false)}>
                {t.profile.deleteNo}
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="press font-mono text-[length:var(--text-label)] uppercase tracking-[0.16em] text-label transition-colors hover:text-error"
            >
              {t.profile.deleteAccount}
            </button>
          </div>
        )}
      </Section>

      <div className="border-t border-line pt-6">
        <button
          type="button"
          onClick={signOut}
          className="press font-mono text-[length:var(--text-label)] uppercase tracking-[0.16em] text-label transition-colors hover:text-error"
        >
          {t.profile.signOut}
        </button>
      </div>
    </div>
  );
}
