"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, Eyebrow, Field, Notice, Spinner } from "@/components/ui";
import { ApiError, api, isSignedIn } from "@/lib/api";
import { filenameFor, useRecorder } from "@/lib/useRecorder";
import { useT } from "@/lib/useT";

type Step = "goal" | "why" | "criteria";

export default function Setup() {
  const router = useRouter();
  const { t } = useT();
  const [ready, setReady] = useState(false);
  const [step, setStep] = useState<Step>("goal");

  const [title, setTitle] = useState("");
  const [why, setWhy] = useState("");
  const [whySource, setWhySource] = useState<"text" | "voice">("text");

  const [suggested, setSuggested] = useState<string[]>([]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [custom, setCustom] = useState("");
  const [loadingCriteria, setLoadingCriteria] = useState(false);
  const [suggestFailed, setSuggestFailed] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [transcribing, setTranscribing] = useState(false);

  const recorder = useRecorder();

  useEffect(() => {
    if (!isSignedIn()) router.replace("/login");
    else setReady(true);
  }, [router]);

  if (!ready) return <div className="min-h-dvh bg-paper" aria-hidden />;

  async function captureVoice() {
    if (recorder.state === "recording") {
      const result = await recorder.stop();
      recorder.reset();
      if (!result) return;
      setTranscribing(true);
      setError(null);
      try {
        const { text } = await api.transcribeOnce(
          result.blob,
          filenameFor(result.mimeType),
        );
        setWhy((prev) => (prev ? `${prev} ${text}` : text));
        setWhySource("voice");
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t.setup.transcribeFailed);
      } finally {
        setTranscribing(false);
      }
    } else {
      void recorder.start();
    }
  }

  async function goToCriteria() {
    setStep("criteria");
    if (suggested.length) return;
    setLoadingCriteria(true);
    setError(null);
    setSuggestFailed(null);
    try {
      const { criteria } = await api.suggestCriteria(title.trim(), why.trim() || undefined);
      setSuggested(criteria);
    } catch (err) {
      // Suggestions are a convenience, not a requirement - the user defines progress
      // either way. But say so out loud: a silently empty list is indistinguishable
      // from a feature that does not exist.
      setSuggested([]);
      setSuggestFailed(
        err instanceof ApiError && err.status === 503
          ? t.setup.suggestUnavailable503
          : t.setup.suggestUnavailable,
      );
    } finally {
      setLoadingCriteria(false);
    }
  }

  async function retrySuggestions() {
    setSuggestFailed(null);
    setLoadingCriteria(true);
    try {
      const { criteria } = await api.suggestCriteria(title.trim(), why.trim() || undefined);
      setSuggested((prev) => [...criteria.filter((c) => !prev.includes(c)), ...prev]);
    } catch {
      setSuggestFailed(t.setup.suggestRetryFailed);
    } finally {
      setLoadingCriteria(false);
    }
  }

  function toggle(text: string) {
    setChosen((prev) =>
      prev.includes(text) ? prev.filter((c) => c !== text) : [...prev, text],
    );
  }

  function addCustom() {
    const text = custom.trim();
    if (!text) return;
    setSuggested((prev) => (prev.includes(text) ? prev : [...prev, text]));
    setChosen((prev) => (prev.includes(text) ? prev : [...prev, text]));
    setCustom("");
  }

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await api.createGoal({
        title: title.trim(),
        why_text: why.trim() || undefined,
        why_source: whySource,
        criteria: chosen.map((text) => ({
          text,
          source: suggested.includes(text) ? "ai" : "user",
        })),
      });
      router.replace("/today");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.setup.saveFailed);
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-paper">
      <div className="mx-auto max-w-[560px] px-5 py-16">
        <Eyebrow>
          {t.setup.stepOf(
            step === "goal" ? t.setup.first : step === "why" ? t.setup.second : t.setup.third,
          )}
        </Eyebrow>

        {step === "goal" && (
          <div className="rise mt-5">
            <h1 className="text-[2.1rem]">{t.setup.goalTitle}</h1>
            <p className="mt-3 text-[15px] text-muted">
{t.setup.goalLede}
            </p>
            <input
              className="field mt-7 text-[18px]"
              autoFocus
              value={title}
              placeholder={t.setup.goalPlaceholder}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && title.trim() && setStep("why")}
            />
            <div className="mt-7">
              <Button onClick={() => setStep("why")} disabled={!title.trim()}>
                {t.setup.continueLabel}
              </Button>
            </div>
          </div>
        )}

        {step === "why" && (
          <div className="rise mt-5">
            <h1 className="text-[2.1rem]">{t.setup.whyTitle}</h1>
            <p className="mt-3 text-[15px] text-muted">
{t.setup.whyLede}
            </p>

            <textarea
              className="field mt-7 min-h-[130px] resize-y"
              value={why}
              placeholder={t.setup.whyPlaceholder}
              onChange={(e) => {
                setWhy(e.target.value);
                setWhySource("text");
              }}
            />

            <div className="mt-4 flex flex-wrap items-center gap-4">
              <Button variant="quiet" onClick={captureVoice} disabled={transcribing}>
                {recorder.state === "recording"
                  ? t.setup.stopAndTranscribe(recorder.seconds)
                  : t.setup.sayInstead}
              </Button>
              {transcribing && <Spinner label={t.setup.transcribing} />}
            </div>

            {recorder.error && <div className="mt-4"><Notice tone="error">{t.errors[recorder.error]}</Notice></div>}
            {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}

            <div className="mt-8 flex items-center gap-4">
              <Button onClick={goToCriteria} disabled={!why.trim()}>
                {t.setup.continueLabel}
              </Button>
              <button
                onClick={goToCriteria}
                className="text-[14px] text-muted underline underline-offset-4 hover:text-ink"
              >
{t.setup.skip}
              </button>
            </div>
          </div>
        )}

        {step === "criteria" && (
          <div className="rise mt-5">
            <h1 className="text-[2.1rem]">{t.setup.criteriaTitle}</h1>
            <p className="mt-3 text-[15px] text-muted">
{t.setup.criteriaLede}
            </p>

            <div className="mt-7 space-y-2.5">
              {loadingCriteria && <Spinner label={t.setup.drafting} />}

              {suggestFailed && !loadingCriteria && (
                <div className="pb-2">
                  <Notice>{suggestFailed}</Notice>
                  <button
                    onClick={retrySuggestions}
                    className="mt-2 text-[14px] text-signal underline underline-offset-4"
                  >
{t.setup.retrySuggestions}
                  </button>
                </div>
              )}

              {suggested.map((text) => {
                const active = chosen.includes(text);
                return (
                  <button
                    key={text}
                    onClick={() => toggle(text)}
                    aria-pressed={active}
                    className={`flex w-full items-center gap-3 rounded-sm border px-4 py-3 text-left text-[16px] transition-colors ${
                      active
                        ? "border-signal bg-signal-dim text-ink"
                        : "border-rule bg-card text-ink hover:border-ink"
                    }`}
                  >
                    <span
                      className={`inline-block h-3 w-3 shrink-0 rounded-[2px] border ${
                        active ? "border-signal bg-signal" : "border-rule"
                      }`}
                    />
                    {text}
                  </button>
                );
              })}
            </div>

            <div className="mt-5">
              <Field label={t.setup.addYourOwn}>
                <div className="flex gap-2">
                  <input
                    className="field"
                    value={custom}
                    placeholder={t.setup.criteriaPlaceholder}
                    onChange={(e) => setCustom(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addCustom();
                      }
                    }}
                  />
                  <Button variant="quiet" onClick={addCustom} disabled={!custom.trim()}>
                    {t.setup.add}
                  </Button>
                </div>
              </Field>
            </div>

            {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}

            <div className="mt-8">
              <Button onClick={finish} disabled={busy || chosen.length === 0}>
                {busy ? t.setup.saving : t.setup.start}
              </Button>
              {chosen.length === 0 && (
                <p className="mt-3 text-[13px] text-muted">{t.setup.chooseOne}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
