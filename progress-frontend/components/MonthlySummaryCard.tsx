"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PairCard } from "@/components/PairCard";
import { QuoteChip } from "@/components/QuoteChip";
import { ThreadChip } from "@/components/ThreadChip";
import { Button, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { describeError } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import type { MonthlySummary, Segment } from "@/lib/types";
import { useT } from "@/lib/useT";

/** "September" / "сентябрь" from "2026-09". */
export function monthLabel(month: string, locale: Locale): string {
  const [y, m] = month.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { month: "long", timeZone: "UTC" }).format(
    new Date(Date.UTC(y, m - 1, 1)),
  );
}

/** Text the model wrote, with the person's quotes (rendered by the server) inside. */
function Prose({ segments }: { segments: Segment[] }) {
  return (
    <p className="concluded">
      {segments.map((segment, i) =>
        segment.type === "text" ? (
          <span key={i}>{segment.text}</span>
        ) : (
          <QuoteChip key={i} segment={segment} />
        ),
      )}
    </p>
  );
}

function hasText(segments: Segment[] | undefined): segments is Segment[] {
  return !!segments && segments.some((s) => s.type === "quote" || s.text.trim() !== "");
}

/** The preview on the Progress screen: the month and the first lines; tap to read it all. */
export function MonthlySummaryCard({ summary }: { summary: MonthlySummary }) {
  const { t, locale } = useT();
  const label = monthLabel(summary.month, locale);
  const thin = summary.status === "thin";
  const intro = summary.content?.intro.filter((s) => s.type === "text") ?? [];
  return (
    <Link
      href={`/progress/monthly/${summary.month}`}
      className="card enter press block p-4 transition-colors hover:bg-surface"
    >
      <p className="label">{t.progress.monthly.title(label)}</p>
      <p className="mt-2 text-muted">
        {thin ? t.progress.monthly.thin(label) : intro.map((s) => (s.type === "text" ? s.text : "")).join("")}
      </p>
      <p className="mt-3 text-[length:var(--text-small)] text-sunrise">{t.progress.monthly.open} ›</p>
    </Link>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="figure text-[length:var(--text-figure)]">{value}</p>
      <p className="label mt-1">{label}</p>
    </div>
  );
}

/** The whole summary of one month. The server marks it as seen when it is opened. */
export function MonthlySummaryView({ month }: { month: string }) {
  const { t, locale } = useT();
  const [summary, setSummary] = useState<MonthlySummary | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setSummary(await api.monthly(month));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setMissing(true);
      else setError(describeError(err, t));
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps
    void load();
  }, [month]);

  const label = monthLabel(month, locale);
  const stats = summary?.stats;
  const content = summary?.content;

  return (
    <section className="enter pt-2">
      <Link href="/progress" className="label hover:text-bone">
        ‹ {t.progress.monthly.back}
      </Link>
      <h1 className="mt-2 text-[length:var(--text-base)]">{t.progress.monthly.title(label)}</h1>

      {missing && <p className="mt-6 text-dim">{t.progress.monthly.notFound}</p>}
      {error && (
        <div className="mt-6 flex flex-col items-start gap-3">
          <p className="text-error" role="alert">
            {error}
          </p>
          <Button variant="quiet" onClick={() => void load()}>
            {t.shell.retry}
          </Button>
        </div>
      )}
      {!summary && !missing && !error && (
        <div className="mt-6">
          <Spinner label={t.shell.loading} />
        </div>
      )}

      {summary && stats && (
        <div className="mt-6 flex flex-col gap-8">
          {summary.status === "thin" && (
            <p className="text-muted">{t.progress.monthly.thin(label)}</p>
          )}
          {content && hasText(content.intro) && <Prose segments={content.intro} />}

          <div className="grid grid-cols-3 gap-4">
            <Stat label={t.progress.monthly.days} value={stats.days} />
            <Stat label={t.progress.monthly.closedThreads} value={stats.closed_threads} />
            <Stat label={t.progress.monthly.newPairs} value={stats.new_pairs} />
          </div>

          {stats.pairs.length > 0 && (
            <div>
              <h2 className="label mb-3">{t.progress.monthly.cards}</h2>
              <div className="flex flex-col gap-3">
                {stats.pairs.map((pair) => (
                  <PairCard key={pair.id} pair={pair} />
                ))}
              </div>
            </div>
          )}

          {stats.closed.length > 0 && (
            <div>
              <h2 className="label mb-3">{t.progress.monthly.closed}</h2>
              <div className="flex flex-wrap gap-1.5">
                {stats.closed.map((thread) => (
                  <ThreadChip key={thread.id} thread={thread} />
                ))}
              </div>
            </div>
          )}

          {content && hasText(content.open_struggle) && (
            <div>
              <h2 className="label mb-2">{t.progress.monthly.openStruggle}</h2>
              <Prose segments={content.open_struggle} />
            </div>
          )}

          {stats.why_text && (
            <div>
              <h2 className="label mb-2">{t.progress.monthly.motivation}</h2>
              <p>
                <span className="said">«{stats.why_text}»</span>
              </p>
            </div>
          )}

          {content && hasText(content.next_step) && (
            <div>
              <h2 className="label mb-2">{t.progress.monthly.nextStep}</h2>
              <Prose segments={content.next_step} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}
