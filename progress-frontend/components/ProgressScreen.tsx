"use client";

import { useEffect, useState } from "react";

import { FinishPath } from "@/components/FinishPath";
import { MonthlySummaryCard } from "@/components/MonthlySummaryCard";
import { PairCard } from "@/components/PairCard";
import { ThreadChip } from "@/components/ThreadChip";
import { Button, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { describeError } from "@/lib/i18n";
import type { Progress, Thread } from "@/lib/types";
import { useT } from "@/lib/useT";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-9">
      <h2 className="label mb-3">{title}</h2>
      {children}
    </section>
  );
}

/** One thread: its tag, and for an open one the ways to close or delete it. */
function ThreadRow({
  thread,
  onChange,
}: {
  thread: Thread;
  onChange: (id: string, status: "closed" | "deleted") => Promise<void>;
}) {
  const { t, locale } = useT();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const closed = thread.status === "closed";

  async function act(status: "closed" | "deleted") {
    setBusy(true);
    await onChange(thread.id, status);
    setBusy(false);
    setConfirming(false);
  }

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line py-2.5 last:border-b-0">
      <ThreadChip thread={thread} />
      {closed && thread.closed_on && (
        <span className="text-[length:var(--text-small)] text-dim">
          {t.progress.closedOn(formatDay(thread.closed_on, locale, { day: "numeric", month: "short" }))}
        </span>
      )}
      <span className="ml-auto flex items-center gap-1">
        {!closed && !confirming && (
          <button
            type="button"
            disabled={busy}
            onClick={() => void act("closed")}
            className="press px-2 py-2 text-[length:var(--text-small)] text-muted hover:text-bone disabled:opacity-50"
          >
            {t.progress.closeThread}
          </button>
        )}
        {confirming ? (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={() => void act("deleted")}
              className="press px-2 py-2 text-[length:var(--text-small)] text-error disabled:opacity-50"
            >
              {t.progress.deleteThread}?
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="press px-2 py-2 text-[length:var(--text-small)] text-dim hover:text-bone"
            >
              ×
            </button>
          </>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => setConfirming(true)}
            className="press px-2 py-2 text-[length:var(--text-small)] text-dim hover:text-bone disabled:opacity-50"
          >
            {t.progress.deleteThread}
          </button>
        )}
      </span>
    </li>
  );
}

/** Progress without a model call: the unseen monthly summary, the goal and the way to
 *  the finish line, before-and-after cards, and the difficulties being followed. */
export function ProgressScreen() {
  const { t } = useT();
  const [data, setData] = useState<Progress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setData(await api.progress());
    } catch (err) {
      setError(describeError(err, t));
    }
  }

  useEffect(() => {
    void api.logEvent("progress_opened");
    // eslint-disable-next-line react-hooks/exhaustive-deps
    void load();
  }, []);

  function hidden(id: string) {
    setData((d) => (d ? { ...d, pairs: d.pairs.filter((p) => p.id !== id) } : d));
  }

  async function changeThread(id: string, status: "closed" | "deleted") {
    setNotice(null);
    try {
      await api.updateThread(id, { status });
      // Closing makes a card and moves the thread; reload rather than guess.
      await load();
    } catch {
      setNotice(t.progress.changeFailed);
    }
  }

  return (
    <section className="enter pt-2">
      <h1 className="text-[length:var(--text-base)]">{t.progress.title}</h1>
      {error ? (
        <div className="mt-5 flex flex-col items-start gap-3">
          <p className="text-error" role="alert">
            {error}
          </p>
          <Button variant="quiet" onClick={() => void load()}>
            {t.shell.retry}
          </Button>
        </div>
      ) : data === null ? (
        <div className="mt-5">
          <Spinner label={t.shell.loading} />
        </div>
      ) : (
        <>
          {data.monthly && (
            <div className="mt-5">
              <MonthlySummaryCard summary={data.monthly} />
            </div>
          )}

          <div className="mt-6">
            {data.goal ? (
              <FinishPath goal={data.goal} levelFacts={data.level_facts} />
            ) : (
              <p className="text-dim">{t.progress.noGoal}</p>
            )}
          </div>

          <Section title={t.progress.pairs}>
            {data.pairs.length === 0 ? (
              <p className="text-dim">{t.progress.pairsEmpty}</p>
            ) : (
              <div className="flex flex-col gap-3">
                {data.pairs.map((pair) => (
                  <PairCard key={pair.id} pair={pair} onHidden={hidden} />
                ))}
              </div>
            )}
          </Section>

          <Section title={t.progress.threads}>
            {notice && (
              <p className="mb-2 text-[length:var(--text-small)] text-error" role="alert">
                {notice}
              </p>
            )}
            {data.open_threads.length === 0 && data.closed_threads.length === 0 ? (
              <p className="text-dim">{t.progress.threadsEmpty}</p>
            ) : (
              <div className="flex flex-col gap-5">
                <div>
                  <p className="text-[length:var(--text-small)] text-dim">{t.progress.threadsOpen}</p>
                  {data.open_threads.length === 0 ? (
                    <p className="mt-1 text-dim">{t.progress.threadsNone}</p>
                  ) : (
                    <ul className="mt-1">
                      {data.open_threads.map((th) => (
                        <ThreadRow key={th.id} thread={th} onChange={changeThread} />
                      ))}
                    </ul>
                  )}
                </div>
                {data.closed_threads.length > 0 && (
                  <div>
                    <p className="text-[length:var(--text-small)] text-dim">{t.progress.threadsClosed}</p>
                    <ul className="mt-1">
                      {data.closed_threads.map((th) => (
                        <ThreadRow key={th.id} thread={th} onChange={changeThread} />
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </Section>
        </>
      )}
    </section>
  );
}
