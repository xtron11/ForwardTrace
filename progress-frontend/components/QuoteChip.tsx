"use client";

import Link from "next/link";
import { useState } from "react";

import { PlayAudio } from "@/components/PlayAudio";
import { api } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import type { QuoteSegment } from "@/lib/types";
import { useT } from "@/lib/useT";

/**
 * A quote the person once said, in guillemets, with its date. Tapping opens that day.
 * With a recording it can play the fragment; the menu holds "this is not accurate".
 * Quotes from the first conversation are marked as recollections.
 */
export function QuoteChip({ segment, current }: { segment: QuoteSegment; current?: string }) {
  const { t, locale } = useT();
  const [menu, setMenu] = useState(false);
  const [flagged, setFlagged] = useState(false);
  const [failed, setFailed] = useState(false);

  const messageId = segment.message_id;
  const hasAudio = !!messageId && segment.audio_start_ms != null && segment.audio_end_ms != null;
  const sameDay = current === segment.local_date;

  async function flag() {
    try {
      await api.flagFact(segment.fact_id);
      setFlagged(true);
      setFailed(false);
    } catch {
      setFailed(true);
    }
    setMenu(false);
  }

  const text = <span className="said">«{segment.quote}»</span>;

  return (
    <span className={`my-2 block ${flagged ? "opacity-60" : ""}`}>
      {sameDay ? (
        text
      ) : (
        <Link
          href={`/history/${segment.local_date}`}
          aria-label={`${t.today.openDay}: ${segment.local_date}`}
          onClick={() => void api.logEvent("quote_opened")}
        >
          {text}
        </Link>
      )}
      <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[length:var(--text-small)] text-dim">
        <span className="label">
          {formatDay(segment.local_date, locale, { day: "numeric", month: "short", year: "numeric" })}
        </span>
        {segment.recalled && <span>{t.today.recalled}</span>}
        {hasAudio && messageId && (
          <PlayAudio
            fetchUrl={() => api.messageAudioUrl(messageId)}
            startMs={segment.audio_start_ms}
            endMs={segment.audio_end_ms}
          />
        )}
        {!flagged && (
          <button
            type="button"
            aria-label={t.today.quoteActions}
            aria-expanded={menu}
            onClick={() => setMenu((v) => !v)}
            className="press -my-2 px-2 py-2 text-label hover:text-bone"
          >
            ⋯
          </button>
        )}
      </span>
      {menu && !flagged && (
        <button
          type="button"
          onClick={flag}
          className="press mt-1 block rounded-sm border border-line px-3 py-1.5 text-[length:var(--text-small)] text-muted hover:border-bone"
        >
          {t.today.inaccurate}
        </button>
      )}
      {flagged && (
        <span className="mt-1 block text-[length:var(--text-small)] text-dim">{t.today.inaccurateDone}</span>
      )}
      {failed && <span className="mt-1 block text-[length:var(--text-small)] text-error">{t.errors.generic}</span>}
    </span>
  );
}
