"use client";

import { useState } from "react";

import { Button, Notice, Quote } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import type { Fact, Goal, Memory, Thread } from "@/lib/types";
import { useT } from "@/lib/useT";

const smallButton =
  "press px-2 py-2 text-[length:var(--text-small)] disabled:opacity-50";

/** "Delete" that asks first: the word, then "Delete" / "Keep" with the question. */
function ConfirmDelete({
  ask,
  busy,
  onDelete,
}: {
  ask: string;
  busy: boolean;
  onDelete: () => void;
}) {
  const { t } = useT();
  const [asking, setAsking] = useState(false);
  if (!asking) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => setAsking(true)}
        className={`${smallButton} text-dim hover:text-bone`}
      >
        {t.memory.delete}
      </button>
    );
  }
  return (
    <span className="flex flex-wrap items-center gap-1">
      <span className="text-[length:var(--text-small)] text-muted">{ask}</span>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setAsking(false);
          onDelete();
        }}
        className={`${smallButton} text-error`}
      >
        {t.memory.deleteYes}
      </button>
      <button
        type="button"
        onClick={() => setAsking(false)}
        className={`${smallButton} text-dim hover:text-bone`}
      >
        {t.memory.deleteNo}
      </button>
    </span>
  );
}

function ThreadItem({
  thread,
  busy,
  onClose,
  onDelete,
}: {
  thread: Thread;
  busy: boolean;
  onClose?: () => void;
  onDelete: () => void;
}) {
  const { t, locale } = useT();
  const kind = thread.kind === "topic" ? t.memory.kindTopic : t.memory.kindStruggle;
  const date = thread.status === "closed" ? thread.closed_on : thread.opened_on;
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line py-2.5 last:border-b-0">
      <span className="min-w-0 break-words">{thread.title}</span>
      <span className="text-[length:var(--text-small)] text-dim">
        {kind}
        {date ? ` · ${formatDay(date, locale, { day: "numeric", month: "short" })}` : ""}
      </span>
      <span className="ml-auto flex flex-wrap items-center gap-1">
        {onClose && (
          <button
            type="button"
            disabled={busy}
            onClick={onClose}
            className={`${smallButton} text-muted hover:text-bone`}
          >
            {t.memory.closeTopic}
          </button>
        )}
        <ConfirmDelete ask={t.memory.deleteTopicAsk} busy={busy} onDelete={onDelete} />
      </span>
    </li>
  );
}

function FactItem({ fact, busy, onDelete }: { fact: Fact; busy: boolean; onDelete: () => void }) {
  const { t, locale } = useT();
  return (
    <li className="flex flex-col gap-1.5 border-b border-line py-3 last:border-b-0">
      <p className="text-[length:var(--text-small)] text-dim">
        {formatDay(fact.local_date, locale, { day: "numeric", month: "short", year: "numeric" })}
        {" · "}
        {t.memory.factTypes[fact.type] ?? fact.type}
      </p>
      <Quote>{fact.quote}</Quote>
      <div className="-ml-2">
        <ConfirmDelete ask={t.memory.deleteFactAsk} busy={busy} onDelete={onDelete} />
      </div>
    </li>
  );
}

/** Put `item` back at `index` (a failed delete returns the row where it was). */
function restore<T>(list: T[], item: T, index: number): T[] {
  const next = [...list];
  next.splice(Math.min(index, next.length), 0, item);
  return next;
}

/** "What I remember": the goal with its motivation and finish line, the topics being
 *  followed (close, delete) and the latest facts (delete). Rows go at once and come
 *  back with an error if the server refuses. */
export function MemorySection({
  memory,
  goal,
  loadFailed,
  onEditGoal,
}: {
  memory: Memory | null;
  goal: Goal | null;
  loadFailed: boolean;
  onEditGoal: () => void;
}) {
  const { t } = useT();
  const [open, setOpen] = useState<Thread[]>(memory?.open_threads ?? []);
  const [closed, setClosed] = useState<Thread[]>(memory?.closed_threads ?? []);
  const [facts, setFacts] = useState<Fact[]>(memory?.facts ?? []);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function closeThread(thread: Thread) {
    setError(null);
    setBusy(thread.id);
    try {
      const updated = await api.updateThread(thread.id, { status: "closed" });
      setOpen((list) => list.filter((x) => x.id !== thread.id));
      setClosed((list) => [updated, ...list]);
    } catch {
      setError(t.memory.changeFailed);
    }
    setBusy(null);
  }

  async function deleteThread(thread: Thread, isOpen: boolean) {
    setError(null);
    const set = isOpen ? setOpen : setClosed;
    const index = (isOpen ? open : closed).findIndex((x) => x.id === thread.id);
    set((list) => list.filter((x) => x.id !== thread.id));
    try {
      await api.updateThread(thread.id, { status: "deleted" });
    } catch {
      set((list) => restore(list, thread, index));
      setError(t.memory.changeFailed);
    }
  }

  async function deleteFact(fact: Fact) {
    setError(null);
    const index = facts.findIndex((x) => x.id === fact.id);
    setFacts((list) => list.filter((x) => x.id !== fact.id));
    try {
      await api.deleteFact(fact.id);
    } catch {
      setFacts((list) => restore(list, fact, index));
      setError(t.memory.changeFailed);
    }
  }

  const empty = !goal && !open.length && !closed.length && !facts.length;

  return (
    <section className="border-t border-line py-6" aria-labelledby="memory-title">
      <h2 id="memory-title" className="label mb-4">
        {t.memory.title}
      </h2>
      <div className="flex flex-col gap-6">
        {error && <Notice tone="error">{error}</Notice>}

        {loadFailed ? (
          <Notice tone="error">{t.memory.loadFailed}</Notice>
        ) : empty ? (
          <p className="text-dim">{t.memory.empty}</p>
        ) : (
          <>
            {goal && (
              <div className="flex flex-col gap-3">
                <div>
                  <p className="label">{t.memory.goal}</p>
                  <p className="mt-1">{goal.title}</p>
                </div>
                <div>
                  <p className="label">{t.memory.why}</p>
                  <p className="mt-1">{goal.why_text ?? "—"}</p>
                </div>
                <div>
                  <p className="label">{t.memory.finish}</p>
                  <p className="mt-1">{goal.finish_line ?? t.memory.noFinish}</p>
                </div>
                <div>
                  <Button variant="link" onClick={onEditGoal}>
                    {t.memory.editGoal}
                  </Button>
                </div>
              </div>
            )}

            <div>
              <p className="label mb-1">{t.memory.topics}</p>
              {open.length ? (
                <ul>
                  {open.map((th) => (
                    <ThreadItem
                      key={th.id}
                      thread={th}
                      busy={busy === th.id}
                      onClose={() => void closeThread(th)}
                      onDelete={() => void deleteThread(th, true)}
                    />
                  ))}
                </ul>
              ) : (
                <p className="text-dim">{t.memory.empty}</p>
              )}
              {closed.length > 0 && (
                <details className="mt-2">
                  <summary className="press cursor-pointer py-2 text-[length:var(--text-small)] text-muted hover:text-bone">
                    {t.memory.topicsClosed(closed.length)}
                  </summary>
                  <ul>
                    {closed.map((th) => (
                      <ThreadItem
                        key={th.id}
                        thread={th}
                        busy={busy === th.id}
                        onDelete={() => void deleteThread(th, false)}
                      />
                    ))}
                  </ul>
                </details>
              )}
            </div>

            <div>
              <p className="label mb-1">{t.memory.facts}</p>
              {facts.length ? (
                <ul>
                  {facts.map((f) => (
                    <FactItem key={f.id} fact={f} busy={false} onDelete={() => void deleteFact(f)} />
                  ))}
                </ul>
              ) : (
                <p className="text-dim">{t.memory.empty}</p>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
