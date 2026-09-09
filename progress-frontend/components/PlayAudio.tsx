"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Plays back a recording.
 *
 * The file sits behind an auth check, so it cannot be a plain `<audio src>` - it is
 * fetched as a blob and handed to the element. Loaded only when asked for: pulling
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
  const [url, setUrl] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    // Blob URLs leak until revoked.
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);

  async function toggle() {
    if (playing) {
      audioRef.current?.pause();
      if (audioRef.current) audioRef.current.currentTime = 0;
      setPlaying(false);
      return;
    }

    let src = url;
    if (!src) {
      setLoading(true);
      src = await fetchUrl();
      setLoading(false);
      if (!src) return;
      setUrl(src);
      // The element needs a frame to pick up the new source.
      await new Promise((resolve) => setTimeout(resolve, 0));
    }

    const audio = audioRef.current;
    if (!audio) return;
    if (audio.src !== src) audio.src = src;
    void audio.play();
    setPlaying(true);
  }

  return (
    <>
      <audio
        ref={audioRef}
        src={url ?? undefined}
        onEnded={() => setPlaying(false)}
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
