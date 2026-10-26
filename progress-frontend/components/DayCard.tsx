"use client";

import Link from "next/link";

import { ThreadChip } from "@/components/ThreadChip";
import { formatDay } from "@/lib/dates";
import type { Day } from "@/lib/types";
import { useT } from "@/lib/useT";

/** One row of the history: the date, the day's gist, and its threads. */
export function DayCard({ day }: { day: Day }) {
  const { t, locale } = useT();
  return (
    <Link
      href={`/history/${day.local_date}`}
      className="press block border-b border-line py-4 transition-colors hover:bg-surface"
    >
      <p className="label">
        {formatDay(day.local_date, locale, { weekday: "short", day: "numeric", month: "long" })}
        {" · "}
        {t.history.messages(day.message_count)}
      </p>
      {day.summary && <p className="mt-1.5 text-muted">{day.summary}</p>}
      {day.started_by === "assistant" && (
        <p className="mt-1 text-[length:var(--text-small)] text-dim">{t.history.startedByAi}</p>
      )}
      {day.threads.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {day.threads.map((th) => (
            <ThreadChip key={th.id} thread={th} />
          ))}
        </div>
      )}
    </Link>
  );
}
