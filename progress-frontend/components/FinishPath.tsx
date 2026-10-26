"use client";

import { QuoteChip } from "@/components/QuoteChip";
import type { Fact, Goal } from "@/lib/types";
import { useT } from "@/lib/useT";

/** The goal, why it matters, the finish line (or "just growing"), and the way to it:
 *  the person's latest words about their level, newest first, each with its date.
 *  Words and dates only - never a percentage or a scale. */
export function FinishPath({ goal, levelFacts }: { goal: Goal; levelFacts?: Fact[] }) {
  const { t } = useT();
  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="label">{t.progress.goal}</p>
        <p className="mt-1">{goal.title}</p>
      </div>
      {goal.why_text && (
        <div>
          <p className="label">{t.progress.why}</p>
          <p className="mt-1">
            <span className="said">«{goal.why_text}»</span>
          </p>
        </div>
      )}
      <div>
        <p className="label">{t.progress.finish}</p>
        <p className="mt-1">{goal.finish_line ?? t.progress.noFinish}</p>
      </div>
      {levelFacts && (
        <div>
          <p className="label">{t.progress.path}</p>
          {levelFacts.length === 0 ? (
            <p className="mt-1 text-dim">{t.progress.pathEmpty}</p>
          ) : (
            <ol className="mt-1 flex flex-col">
              {levelFacts.map((fact) => (
                <li key={fact.id} className="border-b border-line py-1 last:border-b-0">
                  <QuoteChip
                    segment={{
                      type: "quote",
                      fact_id: fact.id,
                      quote: fact.quote,
                      local_date: fact.local_date,
                      message_id: fact.message_id,
                      audio_start_ms: fact.audio_start_ms,
                      audio_end_ms: fact.audio_end_ms,
                    }}
                  />
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  );
}
