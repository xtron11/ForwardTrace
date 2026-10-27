"use client";

import { useRef, useState } from "react";

import { filenameFor, useRecorder } from "@/lib/useRecorder";
import { useT } from "@/lib/useT";

function Mic() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.7" />
      <path
        d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 12 20 4l-5 16-3.5-6.5L4 12Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden>
      <rect x="5" y="5" width="14" height="14" rx="2.5" fill="currentColor" />
    </svg>
  );
}

function mmss(total: number): string {
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

const ICON_BUTTON =
  "press flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition-colors disabled:opacity-40";

/**
 * The message box: a text field with a microphone. A recording is not sent as is: its
 * transcript lands in the field, the person checks or corrects it and sends it like
 * typed text. The recording stays with the message when the field holds one dictation;
 * after a second one it would cover only part of the text, so the message goes as text.
 * While the assistant answers, both are locked. If the microphone is blocked the notice
 * says so and the text field keeps working. A recording that came through silent is
 * not transcribed.
 */
export function Composer({
  busy,
  onSendText,
  onDictate,
  onProblem,
}: {
  busy: boolean;
  onSendText: (text: string, voiceDraftId: string | null) => void;
  /** The transcript of a recording, or null when it failed (the screen says why). */
  onDictate: (form: FormData) => Promise<{ voice_draft_id: string; text: string } | null>;
  /** A localised line to show above the box (silent recording and similar). */
  onProblem: (message: string) => void;
}) {
  const { t } = useT();
  const recorder = useRecorder();
  const [text, setText] = useState("");
  const [transcribing, setTranscribing] = useState(false);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  // Taken synchronously on "stop": a second tap while the recorder is still stopping
  // does not transcribe the recording twice.
  const stopping = useRef(false);
  // The recording behind the field's text, and how many went into it since it was empty.
  const voiceDraft = useRef<string | null>(null);
  const dictations = useRef(0);

  const recording = recorder.state === "recording" || recorder.state === "arming";

  function forgetVoice() {
    voiceDraft.current = null;
    dictations.current = 0;
  }

  function submit() {
    const value = text.trim();
    if (!value || busy || transcribing) return;
    const draftId = voiceDraft.current;
    setText("");
    forgetVoice();
    if (fieldRef.current) fieldRef.current.style.height = "auto";
    onSendText(value, draftId);
  }

  async function finishRecording() {
    if (stopping.current) return;
    stopping.current = true;
    let result;
    try {
      result = await recorder.stop();
    } finally {
      stopping.current = false;
    }
    recorder.reset();
    if (!result) return;
    if (result.silent) {
      onProblem(t.errors.silent);
      return;
    }
    const form = new FormData();
    form.append("audio", result.blob, filenameFor(result.mimeType));
    setTranscribing(true);
    const dictated = await onDictate(form);
    setTranscribing(false);
    if (!dictated) return;

    const before = text.trim();
    if (!before) forgetVoice();
    dictations.current += 1;
    voiceDraft.current = dictations.current === 1 ? dictated.voice_draft_id : null;
    setText(before ? `${before} ${dictated.text}` : dictated.text);
    // The field is back once the transcript is in: size it and put the caret at the end.
    requestAnimationFrame(() => {
      const el = fieldRef.current;
      if (!el) return;
      grow(el);
      el.focus();
      el.setSelectionRange(el.value.length, el.value.length);
    });
  }

  function grow(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }

  const micProblem =
    recorder.error === "micBlocked"
      ? t.errors.micBlocked
      : recorder.error === "noRecorder"
        ? t.errors.noRecorder
        : null;

  return (
    <div className="border-t border-line bg-ink pt-2 pb-3">
      {micProblem && (
        <p className="mb-2 text-[length:var(--text-small)] text-dim" role="status">
          {micProblem}
        </p>
      )}

      {recording ? (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => recorder.reset()}
            aria-label={t.today.cancelRecording}
            className={`${ICON_BUTTON} border border-line text-label hover:text-bone`}
          >
            ✕
          </button>
          <p className="flex flex-1 items-center gap-2 font-mono text-[length:var(--text-small)] text-bone" role="status">
            <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-error" aria-hidden />
            {t.today.recording} · {mmss(recorder.seconds)}
          </p>
          <button
            type="button"
            onClick={() => void finishRecording()}
            disabled={recorder.state !== "recording"}
            aria-label={t.today.stopRecording}
            className={`${ICON_BUTTON} bg-sunrise text-on-accent`}
          >
            <StopIcon />
          </button>
        </div>
      ) : transcribing ? (
        <p
          className="flex min-h-11 items-center gap-2 font-mono text-[length:var(--text-small)] text-dim"
          role="status"
        >
          <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-sunrise" aria-hidden />
          {t.today.transcribing}
        </p>
      ) : (
        <div className="flex items-end gap-2">
          <textarea
            ref={fieldRef}
            value={text}
            rows={1}
            disabled={busy}
            placeholder={t.today.inputPlaceholder}
            aria-label={t.today.inputPlaceholder}
            onChange={(e) => {
              setText(e.target.value);
              if (!e.target.value.trim()) forgetVoice();
              grow(e.target);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            className="min-h-11 flex-1 resize-none rounded-md border border-line bg-transparent px-3 py-2.5 text-bone placeholder:text-label focus:border-sunrise focus:outline-none disabled:opacity-50"
          />
          <button
            type="button"
            onClick={() => void recorder.start()}
            disabled={busy}
            aria-label={t.today.record}
            className={`${ICON_BUTTON} border border-line text-bone hover:border-sunrise`}
          >
            <Mic />
          </button>
          {text.trim() && (
            <button
              type="button"
              onClick={submit}
              disabled={busy}
              aria-label={t.today.send}
              className={`${ICON_BUTTON} bg-sunrise text-on-accent`}
            >
              <SendIcon />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
