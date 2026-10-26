"use client";

import { useEffect, useRef } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import { QuickReplies } from "@/components/QuickReplies";
import { Spinner } from "@/components/ui";
import type { Message, Rating, Segment } from "@/lib/types";
import { useT } from "@/lib/useT";

/** A reply being written: what the person just said, and what has arrived so far. */
export type Draft = {
  /** Text of the person's message; null until a recording has been transcribed. */
  user: string | null;
  voice: boolean;
  segments: Segment[];
};

/**
 * The day's messages, a reply that is still arriving, and the quick replies. It keeps
 * the newest line in view as content comes in.
 */
export function ChatThread({
  messages,
  draft,
  quickReplies,
  onQuick,
  onRate,
  canRate,
  busy,
}: {
  messages: Message[];
  draft: Draft | null;
  quickReplies: string[];
  onQuick: (text: string, index: number) => void;
  onRate: (messageId: string, rating: Rating) => void;
  /** Whether a given reply carries "Helped / Not it". */
  canRate: (message: Message, index: number) => boolean;
  busy: boolean;
}) {
  const { t } = useT();
  const endRef = useRef<HTMLDivElement>(null);
  const size = messages.length;
  const draftSize = draft ? draft.segments.length + (draft.user ? 1 : 0) : -1;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [size, draftSize, quickReplies.length]);

  const draftText = draft?.segments.some((s) => s.type === "text" && s.text.length > 0) ?? false;

  return (
    <div className="flex flex-col gap-5" aria-live="polite">
      {messages.map((m, i) => (
        <MessageBubble
          key={m.id}
          message={m}
          onRate={canRate(m, i) ? (rating) => onRate(m.id, rating) : undefined}
        />
      ))}

      {draft && (
        <>
          {(draft.user || draft.voice) && (
            <MessageBubble
              message={{
                role: "user",
                content: [{ type: "text", text: draft.user ?? t.today.sendingVoice }],
              }}
            />
          )}
          {draft.segments.length > 0 ? (
            <MessageBubble message={{ role: "assistant", content: draft.segments }} streaming />
          ) : (
            !draftText && <Spinner label={t.today.thinking} />
          )}
        </>
      )}

      {!busy && !draft && <QuickReplies options={quickReplies} onPick={onQuick} />}
      <div ref={endRef} />
    </div>
  );
}
