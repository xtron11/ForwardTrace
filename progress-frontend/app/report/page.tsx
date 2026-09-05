"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Shell } from "@/components/Shell";
import { TaskFromRecommendation } from "@/components/Tasks";
import { ApiError, api, pollUntilSettled } from "@/lib/api";
import { translateServerMessage } from "@/lib/serverErrors";
import type { Goal, Report } from "@/lib/types";
import { useT } from "@/lib/useT";

export default function ReportPage() {
  return (
    <Shell showSettings>
      <ReportView />
    </Shell>
  );
}

/** A hanging mono label beside a block of prose. Used for every section, so the report
 *  reads as one column of writing rather than a wall of cards. */
function Section({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[78px_1fr] gap-x-4 border-t border-line py-6">
      <span className="font-mono text-[10px] uppercase leading-[1.6] tracking-[0.16em] text-label">
        {label}
      </span>
      <div>{children}</div>
    </div>
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

  useEffect(() => {
    void (async () => {
      setLoading(true);
      setReport(null);
      setError(null);
      try {
        const all = await api.listReports();
        setReport((goalId ? all.find((r) => r.goal_id === goalId) : all[0]) ?? null);
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 404)) {
          setError(err instanceof ApiError ? err.message : t.report.loadFailed);
        }
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goalId]);

  const generate = useCallback(async () => {
    setGenerating(true);
    setError(null);
    setNotReady(null);
    try {
      const created = await api.generateReport(goalId ? { goal_id: goalId } : {});
      const settled = await pollUntilSettled(() => api.getReport(created.id));
      setReport(settled);
      if (settled.status === "failed") {
        setError(translateServerMessage(settled.error, t) || t.report.buildFailed);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 425) {
        setNotReady(translateServerMessage(err.message, t));
      } else {
        setError(err instanceof ApiError ? err.message : t.report.buildFailed);
      }
    } finally {
      setGenerating(false);
    }
  }, [goalId, t]);

  const switcher =
    goals.length > 1 ? (
      <div className="mb-6 flex flex-wrap gap-2" role="tablist">
        {goals.map((g) => (
          <button
            key={g.id}
            role="tab"
            aria-selected={g.id === goalId}
            title={g.title}
            onClick={() => setGoalId(g.id)}
            className={`max-w-[16rem] truncate border px-3 py-1.5 font-mono text-[11px] transition-colors ${
              g.id === goalId
                ? "border-sunrise text-sunrise"
                : "border-line text-label hover:text-bone"
            }`}
          >
            {g.title}
          </button>
        ))}
      </div>
    ) : null;

  if (loading) return null;

  if (!report || report.status === "failed" || !report.content || !report.stats) {
    return (
      <div className="enter pt-6">
        {switcher}
        <h1 className="font-display text-[29px] font-medium">{t.report.noneTitle}</h1>
        <p className="mt-4 max-w-[42ch] text-[17px] text-dim">{t.report.noneLede}</p>
        {report?.error && (
          <p className="mt-5 border-l-2 border-line pl-3 text-[15px] text-dim">
            {translateServerMessage(report.error, t)}
          </p>
        )}
        {notReady && (
          <p className="mt-5 border-l-2 border-line pl-3 text-[15px] text-dim">{notReady}</p>
        )}
        {error && <p className="mt-5 text-[15px] text-error">{error}</p>}
        <button
          onClick={generate}
          disabled={generating}
          className="press mt-8 w-full max-w-[320px] rounded-[6px] bg-sunrise py-[19px] font-mono text-[12px] uppercase tracking-[0.12em] text-on-accent disabled:opacity-40"
        >
          {generating ? t.report.building : t.report.build}
        </button>
      </div>
    );
  }

  const { content, stats } = report;
  const fmt = (iso: string) =>
    new Date(`${iso}T12:00:00`).toLocaleDateString(locale, {
      day: "numeric",
      month: "short",
    });

  return (
    <div className="enter pt-6 pb-10">
      {switcher}

      <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-sunrise">
        {t.nav.report} · {fmt(report.period_start)} — {fmt(report.period_end)}
        {report.generated_by === "human" && t.report.byHand}
      </p>

      <h1 className="mt-4 font-display text-[29px] font-medium leading-[1.14]">
        {content.what_you_did}
      </h1>

      {stats.is_first_report && (
        <p className="mt-4 border-l-2 border-sunrise/50 pl-3 text-[15px] text-dim">
          {t.report.firstReportNote}
        </p>
      )}

      {/* The period's figures. Amber rule above, plain rule below. */}
      <div className="mt-7 flex gap-7 border-y border-line py-[18px] [border-top-color:var(--sunrise)]">
        {stats.total_minutes > 0 && (
          <div>
            <p className="figure text-[30px]">{stats.total_human}</p>
            <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-label">
              {t.report.statTime}
            </p>
          </div>
        )}
        {stats.metrics?.[0] && (
          <div>
            <p className="figure text-[30px]">{stats.metrics[0].total}</p>
            <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-label">
              {stats.metrics[0].unit || stats.metrics[0].name}
            </p>
          </div>
        )}
        <div>
          <p className="figure text-[30px]">{stats.days_logged}</p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.14em] text-label">
            {t.report.statCount}
          </p>
        </div>
      </div>

      {content.what_changed.length > 0 && (
        <Section label={t.report.labelChanged}>
          {content.what_changed.map((item) => (
            <div key={item.text} className="mb-5 last:mb-0">
              <p className="concluded text-[19px] leading-[1.5]">{item.text}</p>
              <p className="mt-2 font-mono text-[12px] leading-[1.9] text-dim">
                {item.evidence}
              </p>
            </div>
          ))}
        </Section>
      )}

      {content.criteria_progress.length > 0 && (
        <Section label={t.report.againstCriteria}>
          {stats.criteria_changed_midperiod && (
            <p className="mb-3 font-mono text-[11px] text-label">
              {t.report.criteriaChanged}
            </p>
          )}
          {content.criteria_progress.map((item) => (
            <div key={item.criterion_id} className="mb-4 last:mb-0">
              <div className="flex items-baseline justify-between gap-4">
                <p className="text-[17px]">
                  {content.criteria_labels[item.criterion_id] ?? "—"}
                </p>
                <span
                  className={`shrink-0 font-mono text-[10px] uppercase tracking-[0.12em] ${
                    item.status === "no_evidence" ? "text-label" : "text-sunrise"
                  }`}
                >
                  {t.report[item.status]}
                </span>
              </div>
              {item.evidence && (
                <p className="mt-1.5 font-mono text-[12px] leading-[1.9] text-dim">
                  {item.evidence}
                </p>
              )}
            </div>
          ))}
        </Section>
      )}

      {content.pattern.text && (
        <Section label={t.report.labelPattern}>
          <p className="concluded text-[19px] leading-[1.5]">{content.pattern.text}</p>
          <p className="mt-2 font-mono text-[11px] text-label">
            {t.report.confidence[content.pattern.confidence]}
          </p>
        </Section>
      )}

      {content.friction && (
        <Section label={t.report.labelFriction}>
          <p className="concluded text-[19px] leading-[1.5]">{content.friction}</p>
        </Section>
      )}

      {content.recommendation && (
        <Section label={t.report.labelNext}>
          <p className="concluded text-[19px] leading-[1.5]">{content.recommendation}</p>
          <TaskFromRecommendation text={content.recommendation} />
        </Section>
      )}

      {content.closing && (
        <div className="border-t border-line pt-7">
          <p className="font-display text-[24px] font-medium leading-[1.2]">
            {content.closing}
          </p>
        </div>
      )}

      <Feedback report={report} onSaved={setReport} />

      <Link
        href="/monthly"
        className="press mt-8 mb-4 flex items-center justify-between border-t border-line pt-6 font-mono text-[12px] uppercase tracking-[0.12em] text-label transition-colors hover:text-sunrise"
      >
        {t.monthly.open}
        <span aria-hidden>→</span>
      </Link>
    </div>
  );
}

function Feedback({
  report,
  onSaved,
}: {
  report: Report;
  onSaved: (r: Report) => void;
}) {
  const { t } = useT();
  const [rating, setRating] = useState<number | null>(report.feedback_rating);
  const [text, setText] = useState(report.feedback_text ?? "");
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(report.feedback_rating !== null);

  const options = [
    { value: 4, label: t.report.rating4 },
    { value: 3, label: t.report.rating3 },
    { value: 2, label: t.report.rating2 },
    { value: 1, label: t.report.rating1 },
  ];

  async function save(value: number, note: string) {
    setSaving(true);
    try {
      onSaved(await api.sendFeedback(report.id, value, note));
      setDone(true);
    } catch {
      /* the reading is what matters; a failed rating is not worth an alarm */
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-10 border-t border-line pt-7">
      <p className="label">{t.report.feedbackTitle}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            onClick={() => {
              setRating(option.value);
              void save(option.value, text);
            }}
            disabled={saving}
            aria-pressed={rating === option.value}
            className={`border px-4 py-2 text-[15px] transition-colors ${
              rating === option.value
                ? "border-sunrise text-sunrise"
                : "border-line text-dim hover:text-bone"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {rating !== null && (
        <div className="mt-5">
          <label className="block">
            <span className="label mb-1.5 block">{t.report.feedbackPrompt2}</span>
            <textarea
              className="field min-h-[90px] resize-y"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <div className="mt-3 flex items-center gap-4">
            <button
              onClick={() => save(rating, text)}
              disabled={saving}
              className="press border border-line px-4 py-2 font-mono text-[12px] uppercase tracking-[0.12em] text-bone"
            >
              {saving ? t.report.sending : t.report.send}
            </button>
            {done && !saving && (
              <span className="text-[14px] text-dim">{t.report.saved}</span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
