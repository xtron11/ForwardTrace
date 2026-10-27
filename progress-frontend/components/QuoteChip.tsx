"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { PlayAudio } from "@/components/PlayAudio";
import { api } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import type { QuoteSegment } from "@/lib/types";
import { useT } from "@/lib/useT";

/**
 * A quote the person once said, inside the sentence: «quote» and a short date in small
 * type right after it, in the same line, so "then → now" reads as one phrase.
 *
 * Tapping the quote opens a small menu: the full date, "Open this day" (unless it is
 * the day shown), playing the fragment when there is a recording, the recollection
 * mark for quotes from the first conversation, and "This is not accurate".
 */
export function QuoteChip({ segment, current }: { segment: QuoteSegment; current?: string }) {
  const { t, locale } = useT();
  const [menu, setMenu] = useState(false);
  const [flagged, setFlagged] = useState(false);
  const [failed, setFailed] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);

  const messageId = segment.message_id;
  const hasAudio = !!messageId && segment.audio_start_ms != null && segment.audio_end_ms != null;
  const sameDay = current === segment.local_date;

  // A tap outside or Escape closes the menu.
  useEffect(() => {
    if (!menu) return;
    function onPointer(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setMenu(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenu(false);
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [menu]);

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

  const shortDate = formatDay(segment.local_date, locale, { day: "numeric", month: "short" });
  const fullDate = formatDay(segment.local_date, locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const item =
    "press block w-full rounded-sm px-2 py-1.5 text-left text-muted hover:bg-surface hover:text-bone";

  return (
    <span ref={rootRef} className={`relative ${flagged ? "opacity-60" : ""}`}>
      <span
        role="button"
        tabIndex={0}
        aria-haspopup="menu"
        aria-expanded={menu}
        aria-label={`${t.today.quoteActions}: ${fullDate}`}
        onClick={() => setMenu((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setMenu((v) => !v);
          }
        }}
        className="said cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sunrise"
      >
        «{segment.quote}»
      </span>
      <span className="ml-1 whitespace-nowrap text-[length:var(--text-small)] text-dim">
        {shortDate}
      </span>
      {menu && (
        <span
          role="menu"
          className="absolute top-full left-0 z-20 mt-1 block w-60 max-w-[80vw] rounded-md border border-line bg-ink p-1.5 text-[length:var(--text-small)] shadow-lg"
        >
          <span className="label block px-2 pt-1 pb-1.5">{fullDate}</span>
          {segment.recalled && (
            <span className="block px-2 pb-1.5 text-dim">{t.today.recalled}</span>
          )}
          {!sameDay && (
            <Link
              role="menuitem"
              href={`/history/${segment.local_date}`}
              onClick={() => void api.logEvent("quote_opened")}
              className={item}
            >
              {t.today.openDay}
            </Link>
          )}
          {hasAudio && messageId && (
            <span className="block px-2 py-1.5">
              <PlayAudio
                fetchUrl={() => api.messageAudioUrl(messageId)}
                startMs={segment.audio_start_ms}
                endMs={segment.audio_end_ms}
              />
            </span>
          )}
          {!flagged && (
            <button type="button" role="menuitem" onClick={flag} className={item}>
              {t.today.inaccurate}
            </button>
          )}
        </span>
      )}
      {flagged && (
        <span className="ml-1 text-[length:var(--text-small)] text-dim">{t.today.inaccurateDone}</span>
      )}
      {failed && <span className="ml-1 text-[length:var(--text-small)] text-error">{t.errors.generic}</span>}
    </span>
  );
}
