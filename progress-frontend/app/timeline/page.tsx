"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";

import { Shell } from "@/components/Shell";
import { api } from "@/lib/api";
import { translateServerMessage } from "@/lib/serverErrors";
import type { Entry } from "@/lib/types";
import { useT } from "@/lib/useT";

export default function TimelinePage() {
  return (
    <Shell title="" showSettings>
      <Suspense fallback={<div className="min-h-dvh bg-ink" />}>
        <Chronicle />
      </Suspense>
    </Shell>
  );
}

/**
 * A register of what was said, not a feed.
 *
 * A day with nothing on it looks the same as any other - grey, unremarked. No red, no
 * icons, no gap markers. The person is reading their own record, not being audited.
 */
function Chronicle() {
  const { t, locale } = useT();
  const params = useSearchParams();
  const focusDate = params.get("date");

  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const focusRef = useRef<HTMLLIElement | null>(null);

  const load = useCallback(async () => {
    try {
      setEntries(await api.listEntries());
    } catch {
      setEntries([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Arriving from a horizon bar should land on that day rather than the top.
  useEffect(() => {
    if (focusDate && focusRef.current) {
      focusRef.current.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [focusDate, entries]);

  if (!entries) return null;

  if (entries.length === 0) {
    return (
      <div className="enter flex flex-1 flex-col justify-center pb-16">
        <p className="label">{t.chronicle.emptyLabel}</p>
        <h2 className="mt-4 whitespace-pre-line font-display text-[29px] font-medium">
          {t.chronicle.emptyTitle}
        </h2>
        <p className="mt-4 max-w-[38ch] text-[17px] text-dim">{t.chronicle.emptyBody}</p>
        <Link
          href="/record"
          className="press mt-9 w-full max-w-[320px] rounded-[6px] bg-sunrise py-[19px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-on-accent"
        >
          {t.chronicle.emptyCta}
        </Link>
      </div>
    );
  }

  const newest = entries[0]?.id;

  return (
    <div className="enter pt-2 pb-8">
      <h1 className="font-display text-[29px] font-medium">{t.chronicle.title}</h1>

      <ol className="mt-8">
        {entries.map((entry) => {
          const date = new Date(`${entry.local_date}T12:00:00`);
          const isNewest = entry.id === newest;
          const isFocus = entry.local_date === focusDate;
          const conclusion =
            entry.wins?.[0]?.text ??
            entry.activities[0]?.details?.[0] ??
            entry.friction?.[0]?.text ??
            null;
          const quote = entry.activities.find((a) => a.quote)?.quote ?? entry.wins?.[0]?.quote;

          const metrics = entry.activities
            .flatMap((a) => [
              a.minutes_explicit && a.minutes ? `${a.category} — ${a.minutes} мин` : null,
              ...(a.metrics ?? []).map((m) => `${m.value} ${m.unit || m.name}`),
            ])
            .filter(Boolean) as string[];

          return (
            <li
              key={entry.id}
              ref={isFocus ? focusRef : undefined}
              className={`grid grid-cols-[58px_1fr] gap-x-4 border-t py-4 ${
                isNewest || isFocus ? "border-sunrise" : "border-line"
              }`}
            >
              <div
                className={`font-mono text-[11.5px] leading-[1.5] ${
                  isNewest || isFocus ? "text-sunrise" : "text-label"
                }`}
              >
                {date.toLocaleDateString(locale, { day: "2-digit", month: "2-digit" })}
                <br />
                {date
                  .toLocaleDateString(locale, { weekday: "short" })
                  .toUpperCase()
                  .slice(0, 2)}
              </div>

              <div>
                {entry.status === "failed" ? (
                  <div className="flex items-baseline justify-between gap-4">
                    <p className="text-[15px] text-dim">
                      {translateServerMessage(entry.error, t) || t.chronicle.quiet}
                    </p>
                    <button
                      onClick={async () => {
                        await api.retryEntry(entry.id).catch(() => {});
                        await load();
                      }}
                      className="shrink-0 font-mono text-[11px] text-label underline underline-offset-4 hover:text-bone"
                    >
                      {t.chronicle.retry}
                    </button>
                  </div>
                ) : entry.status !== "done" ? (
                  <p className="font-mono text-[12px] text-label">{t.chronicle.processing}</p>
                ) : (
                  <>
                    {/* Serif italic: the model's reading of the day. */}
                    {conclusion ? (
                      <p className="concluded text-[17px]">{conclusion}</p>
                    ) : (
                      <p className="text-[16px] text-dim">{t.chronicle.quiet}</p>
                    )}

                    {/* Mono with an amber underline: the person's own words. */}
                    {quote && open === entry.id && (
                      <p className="enter mt-2 font-mono text-[12.5px] leading-[1.9] text-dim">
                        <span className="said">{quote}</span>
                      </p>
                    )}

                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-label">
                      {metrics.slice(0, 3).map((m) => (
                        <span key={m}>{m}</span>
                      ))}
                      {quote && (
                        <button
                          onClick={() => setOpen(open === entry.id ? null : entry.id)}
                          className="underline underline-offset-4 hover:text-bone"
                          aria-expanded={open === entry.id}
                        >
                          {t.chronicle.showSaid} {open === entry.id ? "▴" : "▾"}
                        </button>
                      )}
                    </div>

                    {open === entry.id && entry.raw_transcript && (
                      <p className="enter mt-3 font-mono text-[11.5px] leading-[1.9] text-label">
                        {entry.raw_transcript}
                      </p>
                    )}
                  </>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
