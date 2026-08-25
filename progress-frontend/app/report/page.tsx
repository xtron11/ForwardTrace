"use client";

import { useCallback, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { Button, Eyebrow, Notice, Spinner } from "@/components/ui";
import { ApiError, api, pollUntilSettled } from "@/lib/api";
import type { Goal, Report } from "@/lib/types";
import { useT } from "@/lib/useT";



export default function ReportPage() {
  return (
    <Shell>
      <ReportView />
    </Shell>
  );
}

function ReportView() {
  const { t, locale } = useT();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [goalId, setGoalId] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notReady, setNotReady] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const active = (await api.listGoals()).filter((g) => g.is_active);
        setGoals(active);
        setGoalId((current) => current ?? active[0]?.id ?? null);
      } catch {
        /* the report still works without the switcher */
      }
    })();
  }, []);

  // Each goal has its own report for the same week, so switching reloads.
  useEffect(() => {
    void (async () => {
      setLoading(true);
      setReport(null);
      setError(null);
      try {
        const all = await api.listReports();
        const match = goalId ? all.find((r) => r.goal_id === goalId) : all[0];
        setReport(match ?? null);
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 404)) {
          setError(err instanceof ApiError ? err.message : t.report.loadFailed);
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [goalId]);

  const generate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    setNotReady(null);
    try {
      const created = await api.generateReport(goalId ? { goal_id: goalId } : {});
      const settled = await pollUntilSettled(() => api.getReport(created.id));
      setReport(settled);
      if (settled.status === "failed") setError(settled.error ?? t.report.buildFailed);
    } catch (err) {
      if (err instanceof ApiError && err.status === 425) setNotReady(err.message);
      else setError(err instanceof ApiError ? err.message : t.report.buildFailed);
    } finally {
      setGenerating(false);
    }
  }, []);

  const switcher =
    goals.length > 1 ? (
      <div className="mb-8 flex flex-wrap gap-2" role="tablist" aria-label="Goal">
        {goals.map((g) => (
          <button
            key={g.id}
            role="tab"
            aria-selected={g.id === goalId}
            onClick={() => setGoalId(g.id)}
            title={g.title}
            className={`max-w-[16rem] truncate rounded-sm border px-3 py-1.5 font-mono text-[12px] transition-colors ${
              g.id === goalId
                ? "border-signal bg-signal-dim text-ink"
                : "border-rule bg-card text-muted hover:text-ink"
            }`}
          >
            {g.title}
          </button>
        ))}
      </div>
    ) : null;

  if (loading) return <Spinner label={t.report.loading} />;

  if (!report || report.status === "failed") {
    return (
      <div>
        {switcher}
        <h1 className="text-[2.1rem]">{t.report.noneTitle}</h1>
        <p className="mt-3 max-w-[46ch] text-[16px] text-muted">
{t.report.noneLede}
        </p>
        {report?.error && <div className="mt-5"><Notice>{report.error}</Notice></div>}
        {notReady && <div className="mt-5"><Notice>{notReady}</Notice></div>}
        {error && <div className="mt-5"><Notice tone="error">{error}</Notice></div>}
        <div className="mt-8">
          <Button onClick={generate} disabled={generating}>
            {generating ? t.report.building : t.report.build}
          </Button>
        </div>
      </div>
    );
  }

  if (report.status !== "done" || !report.content || !report.stats) {
    return <Spinner label={t.report.building} />;
  }

  const { content, stats } = report;
  const start = new Date(`${report.period_start}T12:00:00`);
  const end = new Date(`${report.period_end}T12:00:00`);
  const thinTime = stats.categories.some((c) => c.time_coverage < 0.6);

  return (
    <div className="rise">
      {switcher}
      <Eyebrow>
        {start.toLocaleDateString(locale, { month: "short", day: "numeric" })} —{" "}
        {end.toLocaleDateString(locale, { month: "short", day: "numeric" })}
        {report.generated_by === "human" && t.report.byHand}
      </Eyebrow>

      <h1 className="mt-4 text-[2.3rem]">
{stats.goal_title ? t.report.titleForGoal(stats.goal_title) : t.report.title}
      </h1>

      {/* Coverage, stated plainly. Not a streak, not a score. */}
      <div className="mt-8 flex items-center gap-3">
        <div className="flex gap-1.5" aria-hidden>
          {Array.from({ length: stats.period_days }).map((_, i) => (
            <span
              key={i}
              className={`h-6 w-6 rounded-[2px] border ${
                i < stats.days_logged ? "border-signal bg-signal" : "border-rule bg-card"
              }`}
            />
          ))}
        </div>
        <p className="font-mono text-[12px] text-muted">
{t.report.daysLogged(stats.days_logged, stats.period_days)}
        </p>
      </div>

      <section className="mt-12">
        <Eyebrow>{t.report.whatYouDid}</Eyebrow>
        <p className="mt-3 text-[18px] leading-relaxed">{content.what_you_did}</p>

        <div className="mt-6 space-y-2">
          {stats.categories.map((cat) => (
            <div
              key={cat.category}
              className="flex items-baseline justify-between border-b border-rule pb-2"
            >
              <span className="text-[17px]">{cat.category}</span>
              <span className="font-mono text-[13px] text-muted">
                {cat.total_minutes > 0 ? cat.total_human : "—"} ·{" "}
                {t.report.sessions(cat.sessions)} · {cat.days_active}d
              </span>
            </div>
          ))}
        </div>

        {thinTime && (
          <p className="mt-4 font-mono text-[12px] leading-relaxed text-muted">
{t.report.coverageWarning}
          </p>
        )}
      </section>

      {stats.metrics && stats.metrics.length > 0 && (
        <section className="mt-12">
          <Eyebrow>{t.report.countedThisWeek}</Eyebrow>
          <div className="mt-4 space-y-2">
            {stats.metrics.map((m) => (
              <div
                key={`${m.name}-${m.unit}`}
                className="flex items-baseline justify-between border-b border-rule pb-2"
              >
                <span className="text-[17px]">{m.name}</span>
                <span className="font-mono text-[13px]">
                  <span className="text-ink">{m.total}</span>
                  <span className="text-muted">
                    {" "}
                    {m.unit} · {t.report.onDays(m.occasions)}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {content.what_changed.length > 0 && (
        <section className="mt-12">
          <Eyebrow>{t.report.whatChanged}</Eyebrow>
          <div className="mt-4 space-y-7">
            {content.what_changed.map((item) => (
              <div key={item.text}>
                <p className="font-display text-[21px] leading-snug">{item.text}</p>
                <p className="mt-2 border-l-2 border-rule pl-3 text-[15px] italic text-muted">
                  {item.evidence}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {content.criteria_progress.length > 0 && (
        <section className="mt-12">
          <Eyebrow>{t.report.againstCriteria}</Eyebrow>
          {stats.criteria_changed_midperiod && (
            <p className="mt-2 font-mono text-[12px] text-muted">
{t.report.criteriaChanged}
            </p>
          )}
          <div className="mt-4 space-y-3">
            {content.criteria_progress.map((item) => (
              <div key={item.criterion_id} className="card p-4">
                <div className="flex items-baseline justify-between gap-4">
                  <p className="text-[17px]">
                    {content.criteria_labels[item.criterion_id] ?? "—"}
                  </p>
                  <span
                    className={`shrink-0 font-mono text-[11px] uppercase tracking-[0.1em] ${
                      item.status === "no_evidence" ? "text-muted" : "text-signal"
                    }`}
                  >
                    {t.report[item.status]}
                  </span>
                </div>
                {item.evidence && (
                  <p className="mt-2 text-[15px] italic text-muted">{item.evidence}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {content.pattern.text && (
        <section className="mt-12">
          <Eyebrow>{t.report.patternLabel(content.pattern.confidence)}</Eyebrow>
          <p className="mt-3 text-[18px] leading-relaxed">{content.pattern.text}</p>
        </section>
      )}

      {content.friction && (
        <section className="mt-12">
          <Eyebrow>{t.report.friction}</Eyebrow>
          <p className="mt-3 text-[18px] leading-relaxed">{content.friction}</p>
        </section>
      )}

      {content.recommendation && (
        <section className="mt-12">
          <Eyebrow>{t.report.recommendation}</Eyebrow>
          <p className="mt-3 text-[18px] leading-relaxed">{content.recommendation}</p>
        </section>
      )}

      {content.closing && (
        <section className="mt-14 border-t border-rule pt-8">
          <p className="font-display text-[24px] leading-snug">{content.closing}</p>
        </section>
      )}

      <Feedback report={report} onSaved={setReport} t={t} />
    </div>
  );
}

function Feedback({
  report,
  onSaved,
  t,
}: {
  report: Report;
  onSaved: (r: Report) => void;
  t: ReturnType<typeof useT>["t"];
}) {
  const RATINGS = [
    { value: 4, label: t.report.rating4 },
    { value: 3, label: t.report.rating3 },
    { value: 2, label: t.report.rating2 },
    { value: 1, label: t.report.rating1 },
  ];
  const [rating, setRating] = useState<number | null>(report.feedback_rating);
  const [text, setText] = useState(report.feedback_text ?? "");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(report.feedback_rating !== null);
  const [error, setError] = useState<string | null>(null);

  async function save(value: number, note: string) {
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.sendFeedback(report.id, value, note));
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.report.feedbackFailed);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-16 border-t border-rule pt-8">
      <Eyebrow>{t.report.feedbackTitle}</Eyebrow>

      <div className="mt-4 flex flex-wrap gap-2">
        {RATINGS.map((option) => (
          <button
            key={option.value}
            onClick={() => {
              setRating(option.value);
              void save(option.value, text);
            }}
            disabled={saving}
            aria-pressed={rating === option.value}
            className={`rounded-sm border px-4 py-2 text-[15px] transition-colors ${
              rating === option.value
                ? "border-signal bg-signal-dim"
                : "border-rule bg-card hover:border-ink"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {rating !== null && (
        <div className="mt-5">
          <label className="block">
            <span className="eyebrow mb-1.5 block">{t.report.feedbackPrompt}</span>
            <textarea
              className="field min-h-[100px] resize-y"
              value={text}
              placeholder={t.report.feedbackPlaceholder}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <div className="mt-3 flex items-center gap-4">
            <Button variant="quiet" onClick={() => save(rating, text)} disabled={saving}>
              {saving ? t.report.sending : t.report.send}
            </Button>
            {done && !saving && <span className="text-[14px] text-muted">{t.report.saved}</span>}
          </div>
        </div>
      )}

      {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}
    </section>
  );
}
