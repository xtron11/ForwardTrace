"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Plays back a recording.
 *
 * The file sits behind an auth check, so it cannot be a plain `<audio src>` - it is
 * fetched as a blob and handed to the element. Loaded only on the first press: pulling
 * every recording in a chronicle of thirty entries would be pointless traffic.
 */
export function PlayAudio({
  fetchUrl,
  seconds,
  playLabel,
  stopLabel,
}: {
  fetchUrl: () => Promise<string | null>;
  seconds?: number | null;
  playLabel: string;
  stopLabel: string;
}) {
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Kept in a ref rather than state: the element needs it during this click, not
  // after the next render. Waiting for a re-render is what made the first press
  // silent and the second one work.
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      // Blob URLs leak until revoked.
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;

    if (playing) {
      // onPause flips the state; setting it here too would fight with that handler.
      audio.pause();
      audio.currentTime = 0;
      return;
    }

    if (!urlRef.current) {
      setLoading(true);
      const src = await fetchUrl();
      setLoading(false);
      if (!src) return;
      urlRef.current = src;

      // Assigning src starts loading on its own. Calling load() afterwards begins a
      // second load that aborts the first, which is what made the very first press
      // silent: play() was interrupted before any audio arrived.
      await new Promise<void>((resolve) => {
        const done = () => {
          audio.removeEventListener("canplay", done);
          audio.removeEventListener("error", done);
          resolve();
        };
        audio.addEventListener("canplay", done);
        audio.addEventListener("error", done);
        audio.src = src;
      });
    }

    try {
      await audio.play();
      setPlaying(true);
    } catch {
      // Some browsers reject play() outside a user gesture; the press itself is one,
      // so this only fires when the file is genuinely unplayable.
      setPlaying(false);
    }
  }

  return (
    <>
      <audio
        ref={audioRef}
        onEnded={() => setPlaying(false)}
        onPause={() => setPlaying(false)}
        preload="none"
      />
      <button
        onClick={toggle}
        disabled={loading}
        className="press inline-flex items-center gap-1.5 underline underline-offset-4 transition-colors hover:text-sunrise disabled:opacity-50"
      >
        <span aria-hidden>{playing ? "■" : "▶"}</span>
        {playing ? stopLabel : playLabel}
        {seconds ? ` · ${Math.round(seconds)}с` : ""}
      </button>
    </>
  );
}
