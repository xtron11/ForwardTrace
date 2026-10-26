"use client";

import { PlayAudio } from "@/components/PlayAudio";
import { QuoteChip } from "@/components/QuoteChip";
import { api } from "@/lib/api";
import type { Rating, Segment } from "@/lib/types";
import { useT } from "@/lib/useT";

export type BubbleMessage = {
  id?: string;
  role: string;
  content: Segment[];
  rating?: Rating | null;
  has_audio?: boolean;
  audio_seconds?: number | null;
};

const RATINGS: Rating[] = ["helped", "not_it"];

/** One message: the person's on the right, the assistant's on the left with its quotes
 *  and, under a finished reply, "Helped / Not it". */
export function MessageBubble({
  message,
  onRate,
  streaming,
  currentDay,
}: {
  message: BubbleMessage;
  /** Present only when this reply can be rated. */
  onRate?: (rating: Rating) => void;
  streaming?: boolean;
  /** The day being shown, so a quote from that very day does not link to itself. */
  currentDay?: string;
}) {
  const { t } = useT();
  const mine = message.role === "user";

  const body = message.content.map((segment, i) =>
    segment.type === "quote" ? (
      <QuoteChip key={i} segment={segment} current={currentDay} />
    ) : (
      <span key={i} className="whitespace-pre-wrap">
        {segment.text}
      </span>
    ),
  );

  if (mine) {
    const id = message.id;
    return (
      <div className="enter ml-auto max-w-[88%] rounded-md bg-surface px-3.5 py-2.5">
        <p className="label mb-1">{t.today.you}</p>
        <div className="break-words">{body}</div>
        {message.has_audio && id && (
          <p className="mt-1.5 text-[length:var(--text-small)] text-dim">
            <PlayAudio
              fetchUrl={() => api.messageAudioUrl(id)}
              seconds={message.audio_seconds}
              playLabel={t.history.voice}
            />
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="enter max-w-[94%]">
      <p className="label mb-1">{t.today.assistant}</p>
      <div className="break-words">
        {body}
        {streaming && (
          <span className="ml-0.5 inline-block h-2 w-2 animate-pulse rounded-full bg-sunrise" aria-hidden />
        )}
      </div>
      {onRate && (
        <div className="mt-2 flex gap-2 text-[length:var(--text-small)]">
          {message.rating ? (
            <span className="text-dim">{t.today.rated}</span>
          ) : (
            RATINGS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => onRate(r)}
                className="press rounded-sm border border-line px-2.5 py-1 text-muted hover:border-bone hover:text-bone"
              >
                {r === "helped" ? t.today.helped : t.today.notIt}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
