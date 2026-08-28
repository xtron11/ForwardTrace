"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { Entry, Task } from "@/lib/types";
import { useT } from "@/lib/useT";

import { Button, Eyebrow, Notice, Quote, Spinner } from "./ui";

function dayNumber(task: Task): number {
  const start = new Date(`${task.starts_on}T12:00:00`).getTime();
  const today = new Date();
  const elapsed = Math.floor((today.setHours(12, 0, 0, 0) - start) / 86_400_000);
  return Math.min(Math.max(elapsed + 1, 1), task.span_days);
}

/**
 * What is on today, shown above the record button.
 *
 * This is the reason to come back: not a number to protect, but a specific thing the
 * person chose yesterday and has not closed. It carries no progress bar and no tick.
 */
export function TodaysTasks({ onChanged }: { onChanged?: () => void }) {
  const { t } = useT();
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const load = useCallback(async () => {
    try {
      setTasks(await api.listTasks());
    } catch {
      setTasks([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!tasks || tasks.length === 0) return null;

  return (
    <div className="mt-6 space-y-2">
      <Eyebrow>{t.tasks.todayLabel}</Eyebrow>
      {tasks.map((task) => (
        <div key={task.id} className="border border-line px-4 py-3">
          {editing === task.id ? (
            <div className="flex gap-2">
              <input
                className="field"
                autoFocus
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
              <Button
                variant="quiet"
                disabled={!draft.trim()}
                onClick={async () => {
                  await api.updateTask(task.id, { text: draft.trim() });
                  setEditing(null);
                  await load();
                  onChanged?.();
                }}
              >
                {t.setup.add}
              </Button>
            </div>
          ) : (
            <>
              <p className="text-[17px]">{task.text}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-3">
                {task.span_days > 1 && (
                  <span className="font-mono text-[12px] text-dim">
                    {t.tasks.dayOf(dayNumber(task), task.span_days)}
                  </span>
                )}
                <button
                  onClick={() => {
                    setEditing(task.id);
                    setDraft(task.text);
                  }}
                  className="font-mono text-[12px] text-dim underline underline-offset-4 hover:text-bone"
                >
                  {t.tasks.edit}
                </button>
                <button
                  onClick={async () => {
                    await api.updateTask(task.id, { close: true });
                    await load();
                    onChanged?.();
                  }}
                  className="font-mono text-[12px] text-dim underline underline-offset-4 hover:text-bone"
                >
                  {t.tasks.remove}
                </button>
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
}

/**
 * After a check-in: how what they said lines up with what they intended.
 *
 * Only matches appear. A task the day went past is simply absent - no "not done", no
 * empty checkbox. Nobody needs reminding of what they did not get to.
 */
export function TaskReflection({ entry }: { entry: Entry }) {
  const { t } = useT();
  const [touched, setTouched] = useState<Task[]>([]);

  useEffect(() => {
    void (async () => {
      try {
        const all = await api.listTasks(true);
        setTouched(
          all.filter((task) =>
            task.evidence.some((e) => e.date === entry.local_date),
          ),
        );
      } catch {
        /* the card is complete without this */
      }
    })();
  }, [entry.local_date]);

  if (touched.length === 0) return null;

  return (
    <div className="enter mt-8 space-y-4">
      {touched.map((task) => {
        const today = task.evidence.find((e) => e.date === entry.local_date);
        return (
          <div key={task.id}>
            <Eyebrow>{t.tasks.youIntended}</Eyebrow>
            <p className="mt-1 text-[17px]">{task.text}</p>
            {today?.quote && (
              <div className="mt-2">
                <Eyebrow>{t.tasks.whatHappened}</Eyebrow>
                <div className="mt-1">
                  <Quote>{today.quote}</Quote>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Offered only when nothing is on. An intention already in play is reason enough to
 * come back, and asking on top of it is noise.
 */
export function TaskSuggestion({ onAdded }: { onAdded?: () => void }) {
  const { t } = useT();
  const [ideas, setIdeas] = useState<string[] | null>(null);
  const [ask, setAsk] = useState(false);
  const [own, setOwn] = useState("");
  const [days, setDays] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const result = await api.taskSuggestions();
        setAsk(result.should_ask);
        setIdeas(result.suggestions);
      } catch {
        setAsk(false);
      }
    })();
  }, []);

  async function add(text: string) {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.createTask({ text: text.trim(), days, source: ideas?.includes(text) ? "ai" : "user" });
      setGone(true);
      onAdded?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.tasks.createFailed);
    } finally {
      setBusy(false);
    }
  }

  if (!ask || gone) return null;

  return (
    <div className="enter mt-10 border border-line p-5">
      <h2 className="font-display text-[19px]">{t.tasks.askTitle}</h2>
      <p className="mt-2 max-w-[46ch] text-[15px] text-dim">{t.tasks.askBody}</p>

      {ideas === null ? (
        <div className="mt-4">
          <Spinner label={t.tasks.thinking} />
        </div>
      ) : (
        <>
          <div className="mt-4 space-y-2">
            {ideas.map((idea) => (
              <button
                key={idea}
                disabled={busy}
                onClick={() => add(idea)}
                className="w-full rounded-sm border border-line bg-transparent px-4 py-3 text-left text-[16px] transition-colors hover:border-bone"
              >
                {idea}
              </button>
            ))}
            {ideas.length === 0 && (
              <p className="text-[15px] text-dim">{t.tasks.noIdeas}</p>
            )}
          </div>

          <div className="mt-4">
            <Eyebrow>{t.tasks.ownIdea}</Eyebrow>
            <div className="mt-1.5 flex gap-2">
              <input
                className="field"
                value={own}
                placeholder={t.tasks.placeholder}
                onChange={(e) => setOwn(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && own.trim()) {
                    e.preventDefault();
                    void add(own);
                  }
                }}
              />
              <Button variant="quiet" disabled={!own.trim() || busy} onClick={() => add(own)}>
                {t.tasks.add}
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <span className="label">{t.tasks.forHowLong}</span>
            {[
              { value: 1, label: t.tasks.oneDay },
              { value: 3, label: t.tasks.threeDays },
              { value: 7, label: t.tasks.week },
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => setDays(option.value)}
                aria-pressed={days === option.value}
                className={`rounded-sm border px-3 py-1 font-mono text-[12px] transition-colors ${
                  days === option.value
                    ? "border-sunrise bg-sunrise/15 text-bone"
                    : "border-line bg-transparent text-dim hover:text-bone"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}

          <div className="mt-5">
            <button
              onClick={async () => {
                await api.declineTasks().catch(() => {});
                setGone(true);
              }}
              className="text-[14px] text-dim underline underline-offset-4 hover:text-bone"
            >
              {t.tasks.notNow}
            </button>
          </div>
        </>
      )}
    </div>
  );
}


/**
 * Under the report's recommendation.
 *
 * The recommendation is already derived from the person's own reported friction, so
 * this turns something they read and forgot into something waiting for them tomorrow.
 * It is an offer, never applied automatically.
 */
export function TaskFromRecommendation({ text }: { text: string }) {
  const { t } = useT();
  const [days, setDays] = useState(3);
  const [state, setState] = useState<"idle" | "busy" | "added" | "hidden">("idle");

  if (!text.trim() || state === "hidden") return null;

  if (state === "added") {
    return <p className="mt-4 text-[14px] text-dim">{t.tasks.added}</p>;
  }

  return (
    <div className="mt-5 flex flex-wrap items-center gap-3">
      <span className="text-[15px] text-dim">{t.tasks.fromReport}</span>
      {[
        { value: 1, label: t.tasks.oneDay },
        { value: 3, label: t.tasks.threeDays },
        { value: 7, label: t.tasks.week },
      ].map((option) => (
        <button
          key={option.value}
          onClick={() => setDays(option.value)}
          aria-pressed={days === option.value}
          className={`rounded-sm border px-3 py-1 font-mono text-[12px] transition-colors ${
            days === option.value
              ? "border-sunrise bg-sunrise/15 text-bone"
              : "border-line bg-transparent text-dim hover:text-bone"
          }`}
        >
          {option.label}
        </button>
      ))}
      <Button
        variant="quiet"
        disabled={state === "busy"}
        onClick={async () => {
          setState("busy");
          try {
            await api.createTask({ text: text.trim(), days, source: "ai" });
            setState("added");
          } catch {
            setState("hidden");
          }
        }}
      >
        {t.tasks.add}
      </Button>
      <button
        onClick={() => setState("hidden")}
        className="text-[14px] text-dim underline underline-offset-4 hover:text-bone"
      >
        {t.tasks.notNow}
      </button>
    </div>
  );
}
