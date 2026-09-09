"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { PlayAudio } from "@/components/PlayAudio";
import { Shell } from "@/components/Shell";
import { TaskReflection, TaskSuggestion } from "@/components/Tasks";
import { api } from "@/lib/api";
import type { DailySummary, Entry } from "@/lib/types";
import { useT } from "@/lib/useT";

export default function ResultPage() {
  return (
    <Shell flush>
      <Suspense fallback={<div className="min-h-dvh bg-ink" />}>
        <Result />
      </Suspense>
    </Shell>
  );
}

/**
 * The moment straight after a check-in.
 *
 * Everything here is something that happened. A personal record shows when one was set
 * and is absent otherwise; there is no "less than yesterday" and no comparison with the
 * day before at all. A thin day looks exactly like a strong one, because the number that
 * carries the screen - days counted, total accumulated - only ever goes up.
 */
function Result() {
  const { t, locale } = useT();
  const params = useSearchParams();
  const entryId = params.get("entry");

  const [entry, setEntry] = useState<Entry | null>(null);
  const [summary, setSummary] = useState<DailySummary | null>(null);

  useEffect(() => {
    void (async () => {
      const [e, s] = await Promise.all([
        entryId ? api.getEntry(entryId).catch(() => null) : Promise.resolve(null),
        api.dailySummary().catch(() => null),
      ]);
      setEntry(e);
      setSummary(s);
    })();
  }, [entryId]);

  const facts = (entry?.activities ?? []).flatMap((activity) => {
    const rows: { key: string; value: string }[] = [];
    if (activity.minutes_explicit && activity.minutes) {
      rows.push({ key: activity.category, value: `${activity.minutes} мин` });
    }
    for (const metric of activity.metrics ?? []) {
      rows.push({ key: metric.name, value: `${metric.value} ${metric.unit}`.trim() });
    }
    if (rows.length === 0 && activity.details?.length) {
      rows.push({ key: activity.category, value: activity.details[0] });
    }
    return rows;
  });

  const quote =
    entry?.activities.find((a) => a.quote)?.quote ??
    entry?.wins?.[0]?.quote ??
    entry?.friction?.[0]?.quote ??
    null;

  const dateLabel = entry
    ? new Date(`${entry.local_date}T12:00:00`).toLocaleDateString(locale, {
        day: "numeric",
        month: "long",
      })
    : "";

  return (
    <div className="enter pt-6">
      <p className="label">
        {dateLabel} · {t.result.parsed}
      </p>

      <div className="count-up mt-3 flex items-end gap-[10px]">
        <span className="figure text-[86px] text-sunrise">
          {summary?.days_in_journey ?? 0}
        </span>
        <span
          className="label whitespace-pre-line pb-3 leading-[1.35]"
          style={{ color: "var(--color-sunrise)" }}
        >
          {t.result.dayCounted}
        </span>
      </div>

      <div className="mt-6 border-t border-line" />

      {facts.length > 0 ? (
        <div className="mt-1">
          {facts.map((fact, i) => (
            <div
              key={`${fact.key}-${i}`}
              className="flex items-baseline justify-between border-b border-line-soft py-3 font-mono text-[13px]"
            >
              <span className="text-bone">{fact.key}</span>
              <span className="text-label">{fact.value}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-5 text-[17px] text-dim">{t.result.nothing}</p>
      )}

      {quote && (
        <>
          <div className="mt-6 border-t border-line" />
          {/* Mono with an amber underline: the person's own words. Never used for
              anything a model produced. */}
          <div className="mt-5 grid grid-cols-[74px_1fr] gap-x-[14px]">
            <span className="label whitespace-pre-line leading-[1.35]">
              {t.result.youSaid}
            </span>
            <div>
              <p className="font-mono text-[13px] leading-[1.95] text-dim">
                <span className="said">{quote}</span>
              </p>
              {entry?.has_audio && (
                <p className="mt-2 font-mono text-[12px] text-label">
                  <PlayAudio
                    fetchUrl={() => api.entryAudioUrl(entry.id)}
                    seconds={entry.audio_seconds}
                    playLabel={t.chronicle.listen}
                    stopLabel={t.chronicle.stop}
                  />
                </p>
              )}
            </div>
          </div>
        </>
      )}

      {summary?.personal_record && (
        <>
          <div className="mt-6 border-t border-line" />
          <div className="mt-5">
            <div
              className="record-sweep mb-3 h-[1px]"
              style={{ background: "var(--color-sunrise)" }}
            />
            <p
              className="font-mono text-[10.5px] uppercase tracking-[0.16em]"
              style={{ color: "var(--color-sunrise)" }}
            >
              {t.result.record}
            </p>
            <p className="concluded mt-2 text-[22px]">
              {t.result.recordLine(
                summary.personal_record.value,
                summary.personal_record.unit || summary.personal_record.name,
              )}
            </p>
          </div>
        </>
      )}

      {/* The answer to what they said. Comes after the facts on purpose: put text
          first and the facts stop being read. Model prose is serif italic; the
          quotes inside it stay mono with the accent underline, so "you said this"
          and "the system concluded this" never look alike. */}
      {entry?.reflection && entry.reflection.length > 0 && (
        <>
          <div className="mt-6 border-t border-line" />
          <div className="mt-5">
            <p className="label">{t.result.reflection}</p>
            <div className="mt-3 space-y-5">
              {entry.reflection.map((paragraph, i) => (
                <div key={i}>
                  <p className="concluded text-[18px] leading-[1.55]">{paragraph.text}</p>
                  {paragraph.reference && (
                    <div className="mt-2">
                      <p className="label">
                        {t.result.youSaidOn(
                          new Date(`${paragraph.reference.date}T12:00:00`).toLocaleDateString(
                            locale,
                            { day: "numeric", month: "long" },
                          ),
                        )}
                      </p>
                      <p className="mt-1 font-mono text-[12.5px] leading-[1.9] text-dim">
                        <span className="said">{paragraph.reference.quote}</span>
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {entry && <TaskReflection entry={entry} />}
      <TaskSuggestion />

      {summary && (
        <p className="mt-10 font-mono text-[12px] leading-[2] text-label">
          {summary.goal_title && `${summary.goal_title} · `}
          {summary.accumulated &&
            t.result.accumulated(
              summary.accumulated.total,
              summary.accumulated.unit || summary.accumulated.name,
            )}
          {summary.days_until_report !== null && (
            <>
              <br />
              {summary.days_until_report <= 0
                ? t.result.reportReady
                : t.result.reportIn(summary.days_until_report)}
            </>
          )}
        </p>
      )}

      <Link
        href="/today"
        className="press mt-8 block w-full rounded-[6px] border border-line py-[17px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-bone"
      >
        {t.result.back}
      </Link>

      {/* Arriving here from the chronicle, "done" sends you to Today - which is not
          where you came from. */}
      <Link
        href="/timeline"
        className="mt-4 mb-6 block text-center font-mono text-[12px] text-label transition-colors hover:text-bone"
      >
        {t.result.toChronicle}
      </Link>
    </div>
  );
}
