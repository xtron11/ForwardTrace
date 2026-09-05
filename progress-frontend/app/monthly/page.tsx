"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { BareShell } from "@/components/Shell";
import { api } from "@/lib/api";
import type { MonthlyDigest } from "@/lib/types";
import { useT } from "@/lib/useT";

export default function MonthlyPage() {
  return (
    <BareShell>
      <Monthly />
    </BareShell>
  );
}

/**
 * The month, one thought per screen.
 *
 * Deliberately monthly rather than weekly: the form works because it does not arrive
 * often. Everything shown here was computed or already validated elsewhere - nothing
 * on these cards was written for the occasion, which is what keeps it from becoming
 * the year-in-review genre it borrows its shape from.
 */
function Monthly() {
  const { t, locale } = useT();
  const [digest, setDigest] = useState<MonthlyDigest | null>(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    void api.monthlyDigest().then(setDigest).catch(() => setDigest(null));
  }, []);

  const monthName = digest
    ? new Date(digest.period_start + "T12:00:00").toLocaleDateString(locale, {
        month: "long",
        year: "numeric",
      })
    : "";

  const cards = useMemo(() => {
    if (!digest) return [];
    const list: React.ReactNode[] = [];

    list.push(
      <>
        <p className="label">{monthName}</p>
        <p className="figure mt-6 text-[104px] text-sunrise">{digest.days_logged}</p>
        <p className="mt-3 max-w-[22ch] font-display text-[24px] leading-[1.2]">
          {t.monthly.daysCard(digest.days_logged, digest.days_in_month)}
        </p>
        {digest.goal_title && (
          <p className="mt-6 font-mono text-[12px] text-label">{digest.goal_title}</p>
        )}
      </>,
    );

    if (digest.metrics.length > 0) {
      list.push(
        <>
          <p className="label">{t.monthly.metricsLabel}</p>
          <div className="mt-8 space-y-8">
            {digest.metrics.map((m) => (
              <div key={`${m.name}-${m.unit}`}>
                <p className="figure text-[72px] text-sunrise">{m.total}</p>
                <p className="mt-1 font-display text-[20px]">{m.unit || m.name}</p>
              </div>
            ))}
          </div>
        </>,
      );
    }

    if (digest.strongest_day) {
      const day = new Date(digest.strongest_day.date + "T12:00:00").toLocaleDateString(
        locale,
        { day: "numeric", month: "long" },
      );
      list.push(
        <>
          <p className="label">{t.monthly.strongestLabel}</p>
          <p className="figure mt-6 text-[64px]">{day}</p>
          <p className="mt-2 font-display text-[22px] text-sunrise">
            {t.monthly.minutes(digest.strongest_day.minutes)}
          </p>
          {digest.strongest_day.quote && (
            <p className="mt-7 font-mono text-[13px] leading-[1.9] text-dim">
              <span className="said">{digest.strongest_day.quote}</span>
            </p>
          )}
        </>,
      );
    }

    if (digest.changes.length > 0) {
      list.push(
        <>
          <p className="label">{t.monthly.changesLabel}</p>
          <div className="mt-7 space-y-7">
            {digest.changes.map((c) => (
              <div key={c.text}>
                <p className="concluded text-[22px] leading-[1.4]">{c.text}</p>
                {c.evidence && (
                  <p className="mt-2 font-mono text-[12px] leading-[1.9] text-dim">
                    {c.evidence}
                  </p>
                )}
              </div>
            ))}
          </div>
        </>,
      );
    }

    // The pair that does the real work: the first and last thing said this month,
    // side by side, with nothing added between them.
    if (digest.then && digest.now) {
      const fmt = (iso: string) =>
        new Date(iso + "T12:00:00").toLocaleDateString(locale, {
          day: "numeric",
          month: "long",
        });
      list.push(
        <>
          <p className="label">
            {t.monthly.thenLabel} · {fmt(digest.then.date)}
          </p>
          <p className="mt-3 font-mono text-[13px] leading-[1.95] text-dim">
            <span className="said">{digest.then.said}</span>
          </p>
          <div className="my-8 h-[1px] w-16 bg-sunrise" />
          <p className="label">
            {t.monthly.nowLabel} · {fmt(digest.now.date)}
          </p>
          <p className="mt-3 font-mono text-[13px] leading-[1.95] text-dim">
            <span className="said">{digest.now.said}</span>
          </p>
        </>,
      );
    }

    return list;
  }, [digest, locale, monthName, t]);

  if (!digest) return null;

  if (digest.thin || cards.length === 0) {
    return (
      <div className="mx-auto flex min-h-dvh max-w-[560px] flex-col justify-center px-[26px]">
        <p className="label">{monthName}</p>
        <h1 className="mt-4 whitespace-pre-line font-display text-[29px] font-medium">
          {t.monthly.thinTitle}
        </h1>
        <p className="mt-4 max-w-[38ch] text-[17px] text-dim">
          {digest.days_logged === 0 ? t.monthly.empty : t.monthly.thinBody}
        </p>
        <Link
          href="/report"
          className="press mt-9 w-full max-w-[320px] rounded-[6px] border border-line py-[17px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-bone"
        >
          {t.monthly.done}
        </Link>
      </div>
    );
  }

  const last = index >= cards.length - 1;

  return (
    <div className="mx-auto flex min-h-dvh max-w-[560px] flex-col px-[26px]">
      {/* Progress across the cards, not toward a goal. */}
      <div className="flex gap-1.5 pt-6" aria-hidden>
        {cards.map((_, i) => (
          <span
            key={i}
            className="h-[2px] flex-1 rounded-full transition-colors"
            style={{
              background: i <= index ? "var(--color-sunrise)" : "var(--color-line)",
            }}
          />
        ))}
      </div>

      <div key={index} className="enter flex flex-1 flex-col justify-center py-12">
        {cards[index]}
      </div>

      <div className="pb-10">
        {last ? (
          <Link
            href="/report"
            className="press block w-full rounded-[6px] border border-line py-[17px] text-center font-mono text-[12px] uppercase tracking-[0.12em] text-bone"
          >
            {t.monthly.done}
          </Link>
        ) : (
          <button
            onClick={() => setIndex((i) => i + 1)}
            className="press block w-full rounded-[6px] bg-sunrise py-[17px] font-mono text-[12px] uppercase tracking-[0.12em] text-on-accent"
          >
            {t.monthly.next}
          </button>
        )}
      </div>
    </div>
  );
}
