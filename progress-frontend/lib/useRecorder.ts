"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Chrome and Firefox produce webm/opus; iOS Safari only produces mp4/aac.
 *  Hardcoding webm silently breaks every iPhone, so negotiate instead. */
const CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

const EXTENSIONS: Record<string, string> = {
  "audio/webm": "webm",
  "audio/mp4": "m4a",
  "audio/ogg": "ogg",
};

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  if (typeof MediaRecorder.isTypeSupported !== "function") return undefined;
  return CANDIDATES.find((type) => MediaRecorder.isTypeSupported(type));
}

export function filenameFor(mimeType: string): string {
  const base = mimeType.split(";")[0];
  return `checkin.${EXTENSIONS[base] ?? "webm"}`;
}

export type RecorderState = "idle" | "arming" | "recording" | "stopped" | "denied";

/** Peak amplitude below this for a whole recording means nothing was captured.
 *  Real speech peaks well above 0.05 even when softly spoken; a muted or wrong
 *  input device sits at essentially zero. */
export const SILENCE_PEAK = 0.035;

/** getUserMedia resolves before audio actually flows. Starting to speak immediately
 *  clips the opening words - which is how "I spent an hour coding" becomes silence.
 *  Hold the UI back briefly so the capture is already running when the person begins. */
const LEAD_IN_MS = 450;

export type InputDevice = { deviceId: string; label: string };

/** Devices are only labelled after permission has been granted once, so this is worth
 *  calling again after the first recording. */
export async function listInputDevices(): Promise<InputDevice[]> {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  try {
    const all = await navigator.mediaDevices.enumerateDevices();
    return all
      .filter((d) => d.kind === "audioinput")
      .map((d, i) => ({ deviceId: d.deviceId, label: d.label || `Microphone ${i + 1}` }));
  } catch {
    return [];
  }
}

export function useRecorder() {
  const [state, setState] = useState<RecorderState>("idle");
  const [seconds, setSeconds] = useState(0);
  // Error *codes*, not prose: the UI layer decides what language to say it in.
  const [error, setError] = useState<"noRecorder" | "micBlocked" | null>(null);
  const [level, setLevel] = useState(0);
  // Loudest moment since the recording began. The instantaneous level drops to zero in
  // the gap between two words, so anything that asks "is sound arriving?" must ask this
  // instead - otherwise a normal pause for breath looks like a dead microphone.
  const [peak, setPeak] = useState(0);
  const peakRef = useRef(0);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const rafRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const teardown = useCallback(() => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    if (timerRef.current) clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    void audioCtxRef.current?.close().catch(() => {});
    rafRef.current = null;
    timerRef.current = null;
    streamRef.current = null;
    audioCtxRef.current = null;
  }, []);

  useEffect(() => teardown, [teardown]);

  const start = useCallback(async (deviceId?: string) => {
    setError(null);
    setState("arming");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("noRecorder");
      setState("denied");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
        },
      });
    } catch {
      setError("micBlocked");
      setState("denied");
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];

    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    recorder.start();
    recorderRef.current = recorder;

    // Ambient level meter so the button visibly responds to the voice.
    try {
      const Ctx = window.AudioContext ?? (window as never as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctx();
      audioCtxRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        let peak = 0;
        for (const v of data) peak = Math.max(peak, Math.abs(v - 128) / 128);
        if (peak > peakRef.current) {
          peakRef.current = peak;
          setPeak(peak);
        }
        setLevel(peak);
        rafRef.current = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      /* the meter is decorative; recording still works without it */
    }

    setSeconds(0);
    peakRef.current = 0;
    setPeak(0);
    await new Promise((r) => setTimeout(r, LEAD_IN_MS));
    timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    setState("recording");
  }, []);

  const stop = useCallback(
    () =>
      new Promise<{
        blob: Blob;
        mimeType: string;
        seconds: number;
        peak: number;
        silent: boolean;
      } | null>((resolve) => {
        const recorder = recorderRef.current;
        if (!recorder || recorder.state === "inactive") return resolve(null);

        recorder.onstop = () => {
          const mimeType = recorder.mimeType || "audio/webm";
          const blob = new Blob(chunksRef.current, { type: mimeType });
          const peak = peakRef.current;
          teardown();
          setLevel(0);
          setState("stopped");
          // Sending silence produces a fluent, confident, entirely invented transcript.
          // Catching it here is the difference between "I could not hear you" and a
          // week of reports built on sentences the person never said.
          resolve({ blob, mimeType, seconds, peak, silent: peak < SILENCE_PEAK });
        };
        recorder.stop();
      }),
    [seconds, teardown],
  );

  const reset = useCallback(() => {
    teardown();
    chunksRef.current = [];
    setSeconds(0);
    setLevel(0);
    peakRef.current = 0;
    setPeak(0);
    setState("idle");
    setError(null);
  }, [teardown]);

  return { state, seconds, level, peak, error, start, stop, reset };
}
