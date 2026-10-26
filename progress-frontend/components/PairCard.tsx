"use client";

import { useEffect, useState } from "react";

import { QuoteChip } from "@/components/QuoteChip";
import { api } from "@/lib/api";
import type { Fact, Pair, QuoteSegment } from "@/lib/types";
import { useT } from "@/lib/useT";

function asQuote(fact: Fact): QuoteSegment {
  return {
    type: "quote",
    fact_id: fact.id,
    quote: fact.quote,
    local_date: fact.local_date,
    message_id: fact.message_id,
    audio_start_ms: fact.audio_start_ms,
    audio_end_ms: fact.audio_end_ms,
  };
}

/** A "then -> now" card: the theme, two quotes of the person with their dates (each can
 *  play the recording when there is one), and a way to hide the card. Cards built from
 *  the first conversation say they come from the person's recollection. */
export function PairCard({ pair, onHidden }: { pair: Pair; onHidden?: (id: string) => void }) {
  const { t } = useT();
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    void api.logEvent("pair_shown", { pair_id: pair.id });
  }, [pair.id]);

  async function hide() {
    setBusy(true);
    setFailed(false);
    try {
      await api.hidePair(pair.id);
      onHidden?.(pair.id);
    } catch {
      setFailed(true);
      setBusy(false);
    }
  }

  return (
    <article className="card enter p-4">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-[length:var(--text-base)]">{pair.theme}</h3>
        {onHidden && (
          <button
            type="button"
            onClick={hide}
            disabled={busy}
            aria-label={t.progress.hideLabel}
            className="press -my-2 -mr-2 px-2 py-2 text-[length:var(--text-small)] text-dim hover:text-bone disabled:opacity-50"
          >
            {t.progress.hide}
          </button>
        )}
      </div>
      {pair.recalled && (
        <p className="mt-1 text-[length:var(--text-small)] text-dim">{t.today.recalled}</p>
      )}
      <div className="mt-3">
        <p className="label">{t.progress.then}</p>
        <QuoteChip segment={asQuote(pair.then)} />
      </div>
      <div className="mt-2">
        <p className="label">{t.progress.now}</p>
        <QuoteChip segment={asQuote(pair.now)} />
      </div>
      {failed && (
        <p className="mt-2 text-[length:var(--text-small)] text-error" role="alert">
          {t.progress.changeFailed}
        </p>
      )}
    </article>
  );
}
