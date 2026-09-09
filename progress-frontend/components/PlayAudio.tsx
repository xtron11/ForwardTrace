"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Plays back a recording.
 *
 * The audio element is created in JavaScript rather than rendered as JSX. React
 * reconciles attributes on every update, and with no `src` in the markup it kept
 * resetting the source mid-playback - which aborts play() and was why the first press
 * produced silence. An element React does not own cannot be reset by it.
 *
 * The file sits behind an auth check, so it cannot be a plain URL either: it is
 * fetched as a blob on the first press. Loading every recording in a chronicle of
 * thirty entries up front would be pointless traffic.
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
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    const audio = new Audio();
    audio.preload = "none";
    audio.addEventListener("ended", () => setPlaying(false));
    audio.addEventListener("pause", () => setPlaying(false));
    audioRef.current = audio;

    return () => {
      audio.pause();
      audio.src = "";
      // Blob URLs leak until revoked.
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  async function toggle() {
    const audio = audioRef.current;
    if (!audio) return;

    if (playing) {
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

      // Assigning src begins loading by itself; calling load() as well would start a
      // second one and abort the first.
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
      setPlaying(false);
    }
  }

  return (
    <button
      onClick={toggle}
      disabled={loading}
      className="press inline-flex items-center gap-1.5 underline underline-offset-4 transition-colors hover:text-sunrise disabled:opacity-50"
    >
      <span aria-hidden>{playing ? "■" : "▶"}</span>
      {playing ? stopLabel : playLabel}
      {seconds ? " · " + Math.round(seconds) + "с" : ""}
    </button>
  );
}
