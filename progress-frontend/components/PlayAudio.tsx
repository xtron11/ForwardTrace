"use client";

import { useEffect, useRef, useState } from "react";

import { useT } from "@/lib/useT";

/**
 * Plays back a recording, or just a fragment of it: with `startMs`/`endMs` it starts
 * at `startMs` and stops itself at `endMs` (a quote inside a longer voice message).
 *
 * The audio element is created in JavaScript rather than rendered as JSX. React
 * reconciles attributes on every update, and with no `src` in the markup it kept
 * resetting the source mid-playback - which aborts play() and was why the first press
 * produced silence. An element React does not own cannot be reset by it.
 *
 * The file sits behind an auth check, so it cannot be a plain URL either: it is
 * fetched as a blob on the first press, not for every recording in a list up front.
 */
export function PlayAudio({
  fetchUrl,
  seconds,
  startMs,
  endMs,
  playLabel,
  stopLabel,
}: {
  fetchUrl: () => Promise<string | null>;
  seconds?: number | null;
  startMs?: number | null;
  endMs?: number | null;
  playLabel?: string;
  stopLabel?: string;
}) {
  const { t } = useT();
  const [playing, setPlaying] = useState(false);
  const [loading, setLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);
  // Read from the audio events, which are bound once.
  const rangeRef = useRef({ startMs, endMs });
  rangeRef.current = { startMs, endMs };

  useEffect(() => {
    const audio = new Audio();
    audio.preload = "none";
    audio.addEventListener("ended", () => setPlaying(false));
    audio.addEventListener("pause", () => setPlaying(false));
    audio.addEventListener("timeupdate", () => {
      const end = rangeRef.current.endMs;
      if (end != null && audio.currentTime * 1000 >= end) audio.pause();
    });
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

    // Every press starts from the fragment's beginning (0 for a whole recording).
    audio.currentTime = (rangeRef.current.startMs ?? 0) / 1000;
    try {
      await audio.play();
      setPlaying(true);
    } catch {
      setPlaying(false);
    }
  }

  const fragmentSeconds =
    startMs != null && endMs != null ? Math.max(1, Math.round((endMs - startMs) / 1000)) : null;
  const shown = fragmentSeconds ?? (seconds ? Math.round(seconds) : null);

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={loading}
      className="press inline-flex items-center gap-1.5 underline underline-offset-4 transition-colors hover:text-sunrise disabled:opacity-50"
    >
      <span aria-hidden>{playing ? "■" : "▶"}</span>
      {playing ? (stopLabel ?? t.audio.stop) : (playLabel ?? t.audio.play)}
      {shown ? " · " + t.audio.seconds(shown) : ""}
    </button>
  );
}
