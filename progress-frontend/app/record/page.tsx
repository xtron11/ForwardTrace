"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { BareShell } from "@/components/Shell";
import { ApiError, api, pollUntilSettled } from "@/lib/api";
import { translateServerMessage } from "@/lib/serverErrors";
import type { Entry } from "@/lib/types";
import { SILENCE_PEAK, filenameFor, useRecorder } from "@/lib/useRecorder";
import { useT } from "@/lib/useT";

type Step = "recording" | "review" | "writing" | "analysing" | "error";

export default function RecordPage() {
  return (
    <BareShell>
      <Suspense fallback={<div className="min-h-dvh bg-ink" />}>
        <Record />
      </Suspense>
    </BareShell>
  );
}

/** Live level, 16 bars. No pulsing and no glow: this reports, it does not perform. */
function Levels({ level }: { level: number }) {
  const bars = 16;
  const lit = Math.round(level * bars * 1.8);
  return (
    <div className="flex h-[104px] items-end gap-[5px]" aria-hidden>
      {Array.from({ length: bars }).map((_, i) => {
        const distance = Math.abs(i - (bars - 1) / 2) / ((bars - 1) / 2);
        const height = 10 + (1 - distance) * 94 * Math.max(level * 1.6, 0.06);
        return (
          <span
            key={i}
            className="w-[4px] rounded-[2px] transition-[height] duration-75"
            style={{
              height: `${Math.min(height, 104)}px`,
              background:
                i < lit ? "var(--color-sunrise)" : "var(--color-line-strong)",
            }}
          />
        );
      })}
    </div>
  );
}

function Record() {
  const { t } = useT();
  const router = useRouter();
  const params = useSearchParams();
  const recorder = useRecorder();

  const [step, setStep] = useState<Step>(
    params.get("mode") === "text" ? "writing" : "recording",
  );
  const [transcript, setTranscript] = useState("");
  const [entryId, setEntryId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Microphone access must come from a real tap, so recording starts on mount only
  // because arriving here was itself a tap on the button.
  useEffect(() => {
    if (step === "recording" && recorder.state === "idle") void recorder.start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  async function finishRecording() {
    const result = await recorder.stop();
    recorder.reset();
    if (!result) return router.back();

    if (result.silent) {
      // Sending silence comes back as a confident, invented transcript.
      setError(t.record.silent);
      setStep("error");
      void api.logEvent("silent_recording", { seconds: result.seconds });
      return;
    }

    setStep("analysing");
    try {
      const accepted = await api.submitVoice(result.blob, filenameFor(result.mimeType));
      setEntryId(accepted.id);
      const settled = await pollUntilSettled<Entry>(() => api.getEntry(accepted.id));

      if (settled.status === "awaiting_review") {
        setTranscript(settled.raw_transcript ?? "");
        setStep("review");
      } else if (settled.status === "failed") {
        setError(translateServerMessage(settled.error, t) || t.record.errorTitle);
        setStep("error");
      } else {
        router.replace(`/today/result?entry=${accepted.id}`);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.record.errorTitle);
      setStep("error");
    }
  }

  async function confirm() {
    if (!entryId || !transcript.trim()) return;
    setStep("analysing");
    try {
      await api.confirmTranscript(entryId, transcript.trim());
      await pollUntilSettled<Entry>(() => api.getEntry(entryId));
      router.replace(`/today/result?entry=${entryId}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.record.errorTitle);
      setStep("error");
    }
  }

  async function submitText() {
    if (!transcript.trim()) return;
    setStep("analysing");
    try {
      const accepted = await api.submitText(transcript.trim());
      await pollUntilSettled<Entry>(() => api.getEntry(accepted.id));
      router.replace(`/today/result?entry=${accepted.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.record.errorTitle);
      setStep("error");
    }
  }

  const primary =
    "w-full rounded-[6px] bg-sunrise py-[19px] font-mono text-[12px] uppercase tracking-[0.12em] text-bone press";
  const secondary =
    "w-full py-2 text-center font-mono text-[12px] text-label transition-colors hover:text-bone";

  if (step === "recording") {
    return (
      <div className="enter flex min-h-dvh flex-col items-center justify-center gap-10 px-[34px]">
        <p className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-sunrise">
          {t.record.listening}
        </p>

        <Levels level={recorder.level} />

        <p className="font-display text-[52px] font-medium tracking-[-0.03em] tabular-nums">
          {Math.floor(recorder.seconds / 60)}:
          {String(recorder.seconds % 60).padStart(2, "0")}
        </p>

        <p className="max-w-[250px] text-center text-[17px] text-dim">{t.record.calm}</p>

        {recorder.error && (
          <p className="max-w-[280px] text-center text-[15px] text-error">
            {t.errors[recorder.error]}
          </p>
        )}

        <div
          className="mt-auto w-full max-w-[320px] pb-10"
          style={{ paddingBottom: "calc(40px + env(safe-area-inset-bottom))" }}
        >
          <button onClick={finishRecording} className={primary}>
            {t.record.done}
          </button>
          <button
            onClick={() => {
              recorder.reset();
              router.back();
            }}
            className={`${secondary} mt-[18px]`}
          >
            {t.record.cancel}
          </button>
        </div>
      </div>
    );
  }

  if (step === "analysing") {
    return (
      <div className="enter flex min-h-dvh flex-col justify-center px-[26px]">
        <p className="label">{t.record.analysing}</p>
        <div className="mt-6 space-y-3" aria-hidden>
          {["86%", "64%", "74%"].map((width) => (
            <div key={width} className="h-[10px] rounded-[2px] bg-line" style={{ width }} />
          ))}
        </div>
        <p className="mt-8 max-w-[320px] text-[16px] text-dim">{t.record.analysingHint}</p>
      </div>
    );
  }

  if (step === "error") {
    return (
      <div className="enter flex min-h-dvh flex-col justify-center px-[26px]">
        <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-error">
          {t.record.errorTitle}
        </p>
        <p className="mt-3 text-[17px] text-dim">{error ?? t.record.errorBody}</p>
        <div className="mt-10 w-full max-w-[320px]">
          <button onClick={() => setStep("recording")} className={primary}>
            {t.record.retry}
          </button>
          <button onClick={() => router.push("/today")} className={`${secondary} mt-[18px]`}>
            {t.record.later}
          </button>
        </div>
      </div>
    );
  }

  // review and writing share a shape: a block of text the person can correct.
  const isReview = step === "review";
  return (
    <div className="enter flex min-h-dvh flex-col px-[26px] pt-10">
      <p className="label">{isReview ? t.record.reviewLabel : t.record.writeLabel}</p>
      <p className="mt-3 max-w-[42ch] text-[17px] text-dim">
        {isReview ? t.record.reviewHint : t.record.writeHint}
      </p>

      <textarea
        autoFocus={!isReview}
        value={transcript}
        onChange={(e) => setTranscript(e.target.value)}
        placeholder={isReview ? undefined : t.record.writePlaceholder}
        className="mt-8 min-h-[220px] flex-1 resize-none border-0 bg-transparent font-mono text-[13.5px] leading-[2] text-bone outline-none placeholder:text-label"
      />

      <div
        className="w-full pt-6"
        style={{ paddingBottom: "calc(34px + env(safe-area-inset-bottom))" }}
      >
        <button
          onClick={isReview ? confirm : submitText}
          disabled={!transcript.trim()}
          className={`${primary} disabled:opacity-40`}
        >
          {isReview ? t.record.analyse : t.record.save}
        </button>
        <button
          onClick={() => (isReview ? setStep("recording") : router.push("/today"))}
          className={`${secondary} mt-[18px]`}
        >
          {isReview ? t.record.recordAgain : t.record.cancel}
        </button>
      </div>
    </div>
  );
}
