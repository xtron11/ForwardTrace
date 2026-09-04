"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Goal } from "@/lib/types";
import { useT } from "@/lib/useT";

/**
 * The reason they started, on the screen they open every evening.
 *
 * People do not quit because they stopped wanting the thing. They quit because the
 * reason stops being present while the effort stays. Keeping it in view costs nothing
 * and is the one piece of text here that is entirely theirs - written or spoken in the
 * moment they decided, and never rewritten by anything.
 *
 * When it was recorded, the recording is offered: hearing yourself from that day
 * carries something the transcript does not.
 */
export function WhyAnchor({ goal }: { goal: Goal | null }) {
  const { t } = useT();
  const [url, setUrl] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const hasAudio = Boolean(goal?.why_audio_seconds);

  useEffect(() => {
    if (!goal || !hasAudio) return;
    let objectUrl: string | null = null;
    void api.whyAudioUrl(goal.id).then((result) => {
      objectUrl = result;
      setUrl(result);
    });
    return () => {
      // Blob URLs leak until revoked.
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [goal, hasAudio]);

  if (!goal || (!goal.why_text && !hasAudio)) return null;

  function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      audio.currentTime = 0;
      setPlaying(false);
    } else {
      void audio.play();
      setPlaying(true);
    }
  }

  return (
    <div className="mt-6 border-l-2 border-sunrise pl-4">
      <p className="label">{t.home.anchorLabel}</p>

      {goal.why_text && (
        <p className="mt-2 font-body text-[17px] italic leading-[1.5] text-bone">
          «{goal.why_text}»
        </p>
      )}

      {hasAudio && url && (
        <>
          <audio
            ref={audioRef}
            src={url}
            onEnded={() => setPlaying(false)}
            preload="none"
          />
          <button
            onClick={toggle}
            className="press mt-2 flex items-center gap-2 font-mono text-[12px] text-label transition-colors hover:text-sunrise"
          >
            <span
              aria-hidden
              className="inline-flex h-[18px] w-[18px] items-center justify-center rounded-full border border-current"
            >
              {playing ? "■" : "▶"}
            </span>
            {playing ? t.home.anchorPause : t.home.anchorPlay}
            {goal.why_audio_seconds ? ` · ${Math.round(goal.why_audio_seconds)}с` : ""}
          </button>
        </>
      )}
    </div>
  );
}
