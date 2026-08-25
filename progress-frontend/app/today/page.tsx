"use client";

import { useCallback, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { Button, Eyebrow, Notice, Quote, Spinner } from "@/components/ui";
import { ApiError, api, pollUntilSettled } from "@/lib/api";
import type { Entry, Goal } from "@/lib/types";
import { filenameFor, listInputDevices, useRecorder, type InputDevice } from "@/lib/useRecorder";
import { useT } from "@/lib/useT";

type Phase = "ready" | "uploading" | "transcribing" | "review" | "processing" | "done" | "error";

export default function TodayPage() {
  return (
    <Shell>
      <Today />
    </Shell>
  );
}

function Today() {
  const { t, locale } = useT();
  const recorder = useRecorder();
  const [phase, setPhase] = useState<Phase>("ready");
  const [entry, setEntry] = useState<Entry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typing, setTyping] = useState(false);
  const [text, setText] = useState("");
  const [draft, setDraft] = useState("");
  const [goals, setGoals] = useState<Goal[]>([]);
  const [devices, setDevices] = useState<InputDevice[]>([]);
  const [deviceId, setDeviceId] = useState<string | undefined>(undefined);

  const today = new Date().toLocaleDateString(locale, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });

  const track = useCallback(async (accepted: { id: string }, stage: Phase) => {
    setPhase(stage);
    try {
      const settled = await pollUntilSettled(() => api.getEntry(accepted.id));
      setEntry(settled);
      if (settled.status === "failed") {
        setError(settled.error ?? t.today.processFailed);
        setPhase("error");
      } else if (settled.status === "awaiting_review") {
        setDraft(settled.raw_transcript ?? "");
        setPhase("review");
      } else {
        setPhase("done");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.today.processFailed);
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        setGoals((await api.listGoals()).filter((g) => g.is_active));
      } catch {
        /* labels are a nicety; the check-in still works */
      }
    })();
  }, []);

  useEffect(() => {
    // Show an existing check-in if one already landed today.
    void (async () => {
      try {
        const entries = await api.listEntries(5);
        const stamp = new Date().toISOString().slice(0, 10);
        const todays = entries.find((e) => e.local_date === stamp);
        if (todays && todays.status === "done") {
          setEntry(todays);
          setPhase("done");
        }
      } catch {
        /* an empty screen is fine here */
      }
    })();
  }, []);

  async function toggleRecording() {
    if (recorder.state === "recording") {
      const result = await recorder.stop();
      recorder.reset();
      if (!result) return;
      if (result.silent) {
        // Uploading this would come back as a confident, invented transcript.
        setError(t.errors.silent);
        setPhase("ready");
        void api.logEvent("silent_recording", { seconds: result.seconds, peak: result.peak });
        return;
      }
      setPhase("uploading");
      setError(null);
      try {
        const accepted = await api.submitVoice(result.blob, filenameFor(result.mimeType));
        await track(accepted, "transcribing");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t.today.sendFailed);
        setPhase("error");
      }
    } else {
      void api.logEvent("recording_started");
      void recorder.start(deviceId);
      // Labels only appear after permission is granted, so refresh the list each time.
      void listInputDevices().then(setDevices);
    }
  }

  async function submitTyped() {
    if (!text.trim()) return;
    setPhase("uploading");
    setError(null);
    try {
      const accepted = await api.submitText(text.trim());
      setText("");
      setTyping(false);
      await track(accepted, "processing");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.today.saveFailed);
      setPhase("error");
    }
  }

  async function confirmTranscript() {
    if (!entry || !draft.trim()) return;
    setPhase("processing");
    setError(null);
    try {
      const accepted = await api.confirmTranscript(entry.id, draft.trim());
      await track(accepted, "processing");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.today.confirmFailed);
      setPhase("error");
    }
  }

  function again() {
    setEntry(null);
    setError(null);
    setDraft("");
    setPhase("ready");
    recorder.reset();
  }

  const recording = recorder.state === "recording";
  const arming = recorder.state === "arming";
  const busy = phase === "uploading" || phase === "processing" || phase === "transcribing";

  return (
    <div>
      <Eyebrow>{today}</Eyebrow>

      {phase !== "done" && phase !== "review" && (
        <>
          <h1 className="mt-4 text-[2.1rem]">{t.today.title}</h1>
          <p className="mt-3 max-w-[44ch] text-[16px] text-muted">
{t.today.lede}
          </p>

          <div className="mt-14 flex flex-col items-center">
            <div className="relative flex h-[168px] w-[168px] items-center justify-center">
              {recording && (
                <>
                  <span className="rec-ring absolute inset-0 rounded-full bg-signal/25" />
                  <span
                    className="absolute inset-0 rounded-full bg-signal/15 transition-transform duration-100"
                    style={{ transform: `scale(${1 + recorder.level * 0.45})` }}
                  />
                </>
              )}
              <button
                onClick={toggleRecording}
                disabled={busy}
                aria-label={recording ? t.today.stop : t.today.record}
                className={`relative h-[140px] w-[140px] rounded-full font-display text-[15px] font-semibold transition-colors disabled:cursor-not-allowed ${
                  recording
                    ? "bg-ink text-card"
                    : "bg-signal text-card hover:bg-ink disabled:bg-rule disabled:text-muted"
                }`}
              >
                {recording ? t.today.stop : arming ? t.today.arming : busy ? "…" : t.today.record}
              </button>
            </div>

            {recording && (
              <>
                <p className="mt-6 font-mono text-[13px] text-muted" aria-live="polite">
                  {String(Math.floor(recorder.seconds / 60)).padStart(2, "0")}:
                  {String(recorder.seconds % 60).padStart(2, "0")} · {t.today.recording}
                </p>

                {/* A visible level meter. Without it, a wrong input device looks
                    identical to a working one until the transcript comes back wrong. */}
                <div
                  className="mt-3 h-1.5 w-40 overflow-hidden rounded-full bg-rule"
                  role="meter"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(recorder.level * 100)}
                >
                  <div
                    className="h-full bg-signal transition-[width] duration-75"
                    style={{ width: `${Math.min(100, recorder.level * 220)}%` }}
                  />
                </div>

                {recorder.seconds >= 2 && recorder.level < 0.035 && (
                  <p className="mt-2 font-mono text-[12px] text-alert">
                    {t.today.noSound}
                  </p>
                )}
              </>
            )}

            {phase === "uploading" && <div className="mt-6"><Spinner label={t.today.sending} /></div>}
            {phase === "transcribing" && (
              <div className="mt-6"><Spinner label={t.today.transcribing} /></div>
            )}
            {phase === "processing" && (
              <div className="mt-6"><Spinner label={t.today.processing} /></div>
            )}
          </div>

          {(recorder.error || error) && (
            <div className="mt-8">
              <Notice tone="error">{recorder.error ? t.errors[recorder.error] : error}</Notice>
            </div>
          )}

          {devices.length > 1 && (
            <div className="mt-10 flex flex-wrap items-center justify-center gap-2">
              <span className="eyebrow">{t.today.microphone}</span>
              <select
                className="rounded-sm border border-rule bg-card px-2 py-1 font-mono text-[12px]"
                value={deviceId ?? devices[0]?.deviceId}
                onChange={(e) => setDeviceId(e.target.value)}
                aria-label={t.today.microphone}
              >
                {devices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="mt-12 border-t border-rule pt-6">
            {typing ? (
              <div>
                <textarea
                  className="field min-h-[120px] resize-y"
                  autoFocus
                  value={text}
                  placeholder={t.today.typePlaceholder}
                  onChange={(e) => setText(e.target.value)}
                />
                <div className="mt-3 flex gap-3">
                  <Button onClick={submitTyped} disabled={!text.trim() || busy}>
{t.today.saveCheckin}
                  </Button>
                  <Button variant="quiet" onClick={() => setTyping(false)}>
                    {t.today.cancel}
                  </Button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setTyping(true)}
                className="text-[14px] text-muted underline underline-offset-4 hover:text-ink"
              >
{t.today.typeInstead}
              </button>
            )}
          </div>
        </>
      )}

      {phase === "review" && entry && (
        <div className="rise">
          <h1 className="mt-4 text-[2.1rem]">{t.today.reviewTitle}</h1>
          <p className="mt-3 max-w-[46ch] text-[16px] text-muted">
{t.today.reviewLede}
          </p>

          <textarea
            className="field mt-7 min-h-[170px] resize-y font-mono text-[14px] leading-relaxed"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            aria-label={t.today.transcriptLabel}
          />

          {entry.audio_seconds != null && (
            <p className="mt-2 font-mono text-[12px] text-muted">
              {t.today.audioMeta(Math.round(entry.audio_seconds))}
              {entry.stt_ms ? t.today.transcribedIn((entry.stt_ms / 1000).toFixed(1)) : ""}
            </p>
          )}

          {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}

          <div className="mt-7 flex flex-wrap items-center gap-4">
            <Button onClick={confirmTranscript} disabled={!draft.trim()}>
{t.today.looksRight}
            </Button>
            <button
              onClick={again}
              className="text-[14px] text-muted underline underline-offset-4 hover:text-ink"
            >
{t.today.discard}
            </button>
          </div>
        </div>
      )}

      {phase === "done" && entry && <Logged entry={entry} goals={goals} onAgain={again} t={t} />}
    </div>
  );
}

function Logged({
  entry,
  goals,
  onAgain,
  t,
}: {
  entry: Entry;
  goals: Goal[];
  onAgain: () => void;
  t: ReturnType<typeof useT>["t"];
}) {
  const nothing = entry.activities.length === 0;
  const [routing, setRouting] = useState<Record<string, string | null>>(
    Object.fromEntries(entry.activities.map((a) => [a.id, a.goal_id])),
  );

  async function reassign(activityId: string, goalId: string | null) {
    const previous = routing[activityId] ?? null;
    setRouting((prev) => ({ ...prev, [activityId]: goalId }));
    try {
      await api.reassignActivity(activityId, goalId);
    } catch {
      setRouting((prev) => ({ ...prev, [activityId]: previous }));
    }
  }

  return (
    <div className="rise mt-4">
      <h1 className="text-[2.1rem]">{t.today.loggedTitle}</h1>
      <p className="mt-3 text-[16px] text-muted">
{nothing ? t.today.loggedNothing : t.today.loggedLede}
      </p>

      <div className="mt-9 space-y-4">
        {entry.activities.map((activity) => (
          <div key={activity.id} className="card p-5">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="text-[19px]">{activity.category}</h2>
              <span className="font-mono text-[12px] text-muted">
                {activity.minutes_explicit && activity.minutes
                  ? t.today.minutes(activity.minutes)
                  : t.today.noTime}
              </span>
            </div>

            {activity.details && activity.details.length > 0 && (
              <ul className="mt-3 space-y-1">
                {activity.details.map((detail) => (
                  <li key={detail} className="text-[16px] before:mr-2 before:text-muted before:content-['—']">
                    {detail}
                  </li>
                ))}
              </ul>
            )}

            {activity.metrics && activity.metrics.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {activity.metrics.map((m) => (
                  <span
                    key={`${m.name}-${m.value}`}
                    className="rounded-sm border border-signal/40 bg-signal-dim px-2.5 py-1 font-mono text-[12px]"
                  >
                    {m.value} {m.unit || m.name}
                  </span>
                ))}
              </div>
            )}

            {activity.quote && (
              <div className="mt-4 border-t border-rule pt-3">
                <Eyebrow>{t.today.fromWhatYouSaid}</Eyebrow>
                <div className="mt-1.5">
                  <Quote>{activity.quote}</Quote>
                </div>
              </div>
            )}

            {goals.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-rule pt-3">
                <span className="eyebrow">{t.today.filedUnder}</span>
                {goals.map((goal) => (
                  <button
                    key={goal.id}
                    onClick={() => reassign(activity.id, goal.id)}
                    aria-pressed={routing[activity.id] === goal.id}
                    title={goal.title}
                    className={`max-w-[14rem] truncate rounded-sm border px-2.5 py-1 font-mono text-[11px] transition-colors ${
                      routing[activity.id] === goal.id
                        ? "border-signal bg-signal-dim text-ink"
                        : "border-rule bg-card text-muted hover:text-ink"
                    }`}
                  >
                    {goal.title}
                  </button>
                ))}
                <button
                  onClick={() => reassign(activity.id, null)}
                  aria-pressed={routing[activity.id] === null}
                  className={`rounded-sm border px-2.5 py-1 font-mono text-[11px] transition-colors ${
                    routing[activity.id] === null
                      ? "border-signal bg-signal-dim text-ink"
                      : "border-rule bg-card text-muted hover:text-ink"
                  }`}
                >
                  {t.today.none}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {entry.wins && entry.wins.length > 0 && (
        <div className="mt-8">
          <Eyebrow>{t.today.wentWell}</Eyebrow>
          <ul className="mt-2 space-y-3">
            {entry.wins.map((win) => (
              <li key={win.quote}>
                <p className="text-[17px]">{win.text}</p>
                <div className="mt-1"><Quote>{win.quote}</Quote></div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {entry.friction && entry.friction.length > 0 && (
        <div className="mt-8">
          <Eyebrow>{t.today.gotInTheWay}</Eyebrow>
          <ul className="mt-2 space-y-3">
            {entry.friction.map((item) => (
              <li key={item.quote}>
                <p className="text-[17px]">{item.text}</p>
                <div className="mt-1"><Quote>{item.quote}</Quote></div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {entry.transcript_edited && (
        <p className="mt-8 font-mono text-[12px] text-muted">
{t.today.corrected}
        </p>
      )}

      {entry.dropped_facts > 0 && (
        <p className="mt-8 font-mono text-[12px] text-muted">
{t.today.dropped(entry.dropped_facts)}
        </p>
      )}

      <div className="mt-10">
        <Button variant="quiet" onClick={onAgain}>
{t.today.another}
        </Button>
      </div>
    </div>
  );
}
