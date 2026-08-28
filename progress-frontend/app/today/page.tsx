"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { TodaysTasks } from "@/components/Tasks";
import { api } from "@/lib/api";
import type { DailySummary } from "@/lib/types";
import { useT } from "@/lib/useT";

export default function TodayPage() {
  return (
    <Shell flush showSettings>
      <Today />
    </Shell>
  );
}

/**
 * The fortnight, one bar a day.
 *
 * Bars are sized against the fullest day in view rather than against a target: there is
 * no target, so a quiet day is simply short, not short of something. Empty days are a
 * thin grey line - present, unremarkable, never marked as missed. Tapping a bar opens
 * that day, which is why there is no second week strip anywhere in the app.
 */
function Horizon({ days }: { days: DailySummary["horizon"] }) {
  return (
    <div className="mt-5 flex h-[44px] items-end gap-[2px]">
      {days.map((day, index) => (
        <Link
          key={day.date}
          href={`/timeline?date=${day.date}`}
          aria-label={day.date}
          className="bar-rise flex-1 rounded-[1px] transition-opacity hover:opacity-80"
          style={{
            height: `${day.has_entry ? 12 + day.weight * 32 : 6}px`,
            background: day.has_entry
              ? "var(--color-sunrise)"
              : "var(--color-line-strong)",
            animationDelay: `${120 + index * 18}ms`,
          }}
        />
      ))}
    </div>
  );
}

function Today() {
  const { t, locale } = useT();
  const router = useRouter();
  const [summary, setSummary] = useState<DailySummary | null>(null);

  const load = useCallback(async () => {
    try {
      setSummary(await api.dailySummary());
    } catch {
      setSummary(null);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const today = new Date().toLocaleDateString(locale, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  // Built from parts so a missing piece drops out cleanly rather than leaving a
  // dangling separator.
  const statusParts: string[] = [];
  if (summary) {
    statusParts.push(`${summary.horizon.length}`);
    if (summary.accumulated) {
      statusParts.push(
        `${summary.accumulated.total} ${summary.accumulated.unit || summary.accumulated.name}`,
      );
    }
    if (summary.days_until_report !== null) {
      statusParts.push(
        summary.days_until_report <= 0
          ? t.home.reportReady
          : t.home.reportIn(summary.days_until_report),
      );
    }
  }

  const heading = !summary
    ? ""
    : summary.checked_in_today
      ? t.home.told
      : summary.days_in_journey === 0
        ? t.home.firstDay
        : t.home.notToldYet;

  return (
    <>
      <p className="label mt-2">{today}</p>

      {/* Days on which something was said. A gap adds nothing rather than taking
          something away, so this number never falls. */}
      <div className="count-up mt-3 flex items-end gap-[10px]">
        <span className="figure text-[86px] text-bone">{summary?.days_in_journey ?? 0}</span>
        <span className="label whitespace-pre-line pb-3 leading-[1.35]">
          {t.home.daysLabel}
        </span>
      </div>

      {summary && summary.horizon.length > 0 && <Horizon days={summary.horizon} />}

      {statusParts.length > 0 && (
        <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.1em] text-label">
          {t.home.horizonLabel(
            summary!.horizon.length,
            statusParts[1] ?? "",
            statusParts[statusParts.length - 1] ?? "",
          )}
        </p>
      )}

      <TodaysTasks />

      <div className="mt-6 border-t border-line" />

      <div className="flex flex-1 flex-col items-center justify-center gap-[26px] py-10">
        <h2 className="whitespace-pre-line text-center font-display text-[29px] font-medium">
          {heading}
        </h2>

        <button
          onClick={() => router.push("/record")}
          className="press flex h-[168px] w-[168px] flex-col items-center justify-center gap-3 rounded-full"
          style={{
            background: "var(--color-sunrise)",
            boxShadow: "0 0 0 12px rgba(255,176,32,.10), 0 0 64px rgba(255,176,32,.28)",
          }}
        >
          <span className="block h-[22px] w-[22px] rounded-full bg-ink" />
          <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-bone">
            {t.home.speak}
          </span>
        </button>

        <p className="font-mono text-[12px] text-label">{t.home.speakHint}</p>
      </div>

      <Link
        href="/record?mode=text"
        className="pb-5 text-center font-mono text-[12px] text-dim transition-colors hover:text-bone"
      >
        {t.home.writeInstead}
      </Link>
    </>
  );
}
