"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { Button, Eyebrow, Notice, Quote, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Entry } from "@/lib/types";
import { useT } from "@/lib/useT";

export default function TimelinePage() {
  return (
    <Shell>
      <Timeline />
    </Shell>
  );
}

function Timeline() {
  const { t, locale } = useT();
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setEntries(await api.listEntries());
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t.timeline.loadFailed);
      }
    })();
  }, []);

  async function retry(id: string) {
    try {
      await api.retryEntry(id);
      setEntries(await api.listEntries());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.timeline.retryFailed);
    }
  }

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!entries) return <Spinner label={t.timeline.loading} />;

  if (entries.length === 0) {
    return (
      <div>
        <h1 className="text-[2.1rem]">{t.timeline.emptyTitle}</h1>
        <p className="mt-3 text-[16px] text-muted">
{t.timeline.emptyLede}
        </p>
        <Link
          href="/today"
          className="mt-7 inline-block rounded-sm bg-signal px-5 py-2.5 font-display text-[15px] font-semibold text-card hover:bg-ink"
        >
{t.timeline.recordToday}
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-[2.1rem]">{t.timeline.title}</h1>
      <p className="mt-3 text-[16px] text-muted">
{t.timeline.count(entries.length)}
      </p>

      <ol className="mt-10 space-y-0">
        {entries.map((entry) => {
          const expanded = open === entry.id;
          const date = new Date(`${entry.local_date}T12:00:00`);
          return (
            <li key={entry.id} className="border-l border-rule pl-6 pb-8 relative">
              <span className="absolute -left-[4.5px] top-1.5 h-2 w-2 rounded-full bg-rule" />

              <div className="flex items-baseline justify-between gap-4">
                <p className="font-mono text-[12px] uppercase tracking-[0.1em] text-muted">
                  {date.toLocaleDateString(locale, {
                    weekday: "short",
                    day: "numeric",
                    month: "short",
                  })}
                </p>
                {entry.status === "failed" && (
                  <button
                    onClick={() => retry(entry.id)}
                    className="font-mono text-[12px] text-alert underline underline-offset-4"
                  >
{t.timeline.retry}
                  </button>
                )}
              </div>

              {entry.status === "failed" ? (
                <p className="mt-2 text-[15px] text-alert">
{entry.error ?? t.timeline.failed}
                </p>
              ) : entry.status !== "done" ? (
                <div className="mt-2"><Spinner label={t.timeline.stillProcessing} /></div>
              ) : entry.activities.length === 0 ? (
                <p className="mt-2 text-[16px] text-muted">
{t.timeline.nothingPulled}
                </p>
              ) : (
                <>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {entry.activities.map((activity) => (
                      <span
                        key={activity.id}
                        className="rounded-sm border border-rule bg-card px-2.5 py-1 font-mono text-[12px]"
                      >
                        {activity.category}
                        {activity.minutes_explicit && activity.minutes
                          ? ` · ${activity.minutes}m`
                          : ""}
                      </span>
                    ))}
                  </div>

                  {entry.activities.some((a) => a.details?.length) && (
                    <ul className="mt-3 space-y-1">
                      {entry.activities.flatMap((a) =>
                        (a.details ?? []).map((d) => (
                          <li key={`${a.id}-${d}`} className="text-[16px]">
                            {d}
                          </li>
                        )),
                      )}
                    </ul>
                  )}

                  <button
                    onClick={() => setOpen(expanded ? null : entry.id)}
                    className="mt-3 font-mono text-[12px] text-muted underline underline-offset-4 hover:text-ink"
                    aria-expanded={expanded}
                  >
                    {expanded ? t.timeline.hideSaid : t.timeline.showSaid}
                  </button>

                  {expanded && (
                    <div className="rise mt-3 space-y-3">
                      {entry.activities
                        .filter((a) => a.quote)
                        .map((a) => (
                          <Quote key={`q-${a.id}`}>{a.quote}</Quote>
                        ))}
                      {entry.raw_transcript && (
                        <details className="mt-2">
                          <summary className="cursor-pointer font-mono text-[12px] text-muted">
{t.timeline.fullTranscript}
                          </summary>
                          <p className="mt-2 font-mono text-[13px] leading-relaxed text-muted">
                            {entry.raw_transcript}
                          </p>
                        </details>
                      )}
                    </div>
                  )}
                </>
              )}
            </li>
          );
        })}
      </ol>

      <div className="mt-6 border-t border-rule pt-8">
        <Link href="/report">
<Button variant="quiet">{t.timeline.seeReport}</Button>
        </Link>
      </div>
    </div>
  );
}
