"use client";

import { useCallback, useEffect, useState } from "react";

import { ReminderSettings } from "@/components/Reminders";
import { Shell } from "@/components/Shell";
import { Button, Eyebrow, Field, Notice, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import type { Goal } from "@/lib/types";
import { useT } from "@/lib/useT";

const MAX_GOALS = 5;

export default function GoalsPage() {
  return (
    <Shell>
      <Goals />
    </Shell>
  );
}

function Goals() {
  const { t } = useT();
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    try {
      setGoals(await api.listGoals());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.goals.loadFailed);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <Notice tone="error">{error}</Notice>;
  if (!goals) return <Spinner label={t.timeline.loading} />;

  const active = goals.filter((g) => g.is_active);
  const archived = goals.filter((g) => !g.is_active);

  return (
    <div>
      <h1 className="text-[2.1rem]">{t.goals.title}</h1>
      <p className="mt-3 max-w-[46ch] text-[16px] text-muted">
{t.goals.lede}
      </p>

      <div className="mt-10 space-y-4">
        {active.map((goal) =>
          editing === goal.id ? (
            <GoalEditor
              key={goal.id}
              goal={goal}
              onDone={async () => {
                setEditing(null);
                await load();
              }}
              onCancel={() => setEditing(null)}
            />
          ) : (
            <GoalCard
              key={goal.id}
              goal={goal}
              onEdit={() => setEditing(goal.id)}
              onArchived={load}
            />
          ),
        )}
      </div>

      {adding ? (
        <div className="mt-4">
          <GoalEditor
            onDone={async () => {
              setAdding(false);
              await load();
            }}
            onCancel={() => setAdding(false)}
          />
        </div>
      ) : (
        <div className="mt-8">
          <Button
            variant="quiet"
            onClick={() => setAdding(true)}
            disabled={active.length >= MAX_GOALS}
          >
{t.goals.addGoal}
          </Button>
          <p className="mt-3 max-w-[44ch] text-[13px] text-muted">
{active.length >= MAX_GOALS ? t.goals.atLimit : t.goals.addHint}
          </p>
        </div>
      )}

      {archived.length > 0 && (
        <div className="mt-14 border-t border-rule pt-6">
          <Eyebrow>{t.goals.archived}</Eyebrow>
          <ul className="mt-3 space-y-2">
            {archived.map((goal) => (
              <li key={goal.id} className="flex items-baseline justify-between gap-4">
                <span className="text-[16px] text-muted">{goal.title}</span>
                <button
                  onClick={async () => {
                    await api.updateGoal(goal.id, { is_active: true });
                    await load();
                  }}
                  className="font-mono text-[12px] text-signal underline underline-offset-4"
                >
{t.goals.reactivate}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[13px] text-muted">
{t.goals.archivedNote}
          </p>
        </div>
      )}
    </div>
  );
}

function GoalCard({
  goal,
  onEdit,
  onArchived,
}: {
  goal: Goal;
  onEdit: () => void;
  onArchived: () => Promise<void>;
}) {
  const { t } = useT();
  const [busy, setBusy] = useState(false);

  return (
    <div className="card p-5">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-[20px]">{goal.title}</h2>
        <div className="flex shrink-0 gap-3">
          <button
            onClick={onEdit}
            className="font-mono text-[12px] text-muted underline underline-offset-4 hover:text-ink"
          >
            {t.goals.edit}
          </button>
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              await api.updateGoal(goal.id, { is_active: false });
              await onArchived();
            }}
            className="font-mono text-[12px] text-muted underline underline-offset-4 hover:text-ink"
          >
            {t.goals.archive}
          </button>
        </div>
      </div>

      {goal.why_text && (
        <p className="mt-2 text-[16px] italic text-muted">&ldquo;{goal.why_text}&rdquo;</p>
      )}

      {goal.criteria.length > 0 && (
        <>
          <div className="mt-4 border-t border-rule pt-3">
            <Eyebrow>{t.goals.progressMeans}</Eyebrow>
          </div>
          <ul className="mt-2 space-y-1">
            {goal.criteria.map((c) => (
              <li key={c.id} className="text-[15px] before:mr-2 before:text-muted before:content-['—']">
                {c.text}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function GoalEditor({
  goal,
  onDone,
  onCancel,
}: {
  goal?: Goal;
  onDone: () => Promise<void>;
  onCancel: () => void;
}) {
  const { t } = useT();
  const [title, setTitle] = useState(goal?.title ?? "");
  const [why, setWhy] = useState(goal?.why_text ?? "");
  const [criteria, setCriteria] = useState<string[]>(goal?.criteria.map((c) => c.text) ?? []);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggesting, setSuggesting] = useState(false);

  async function suggest() {
    setSuggesting(true);
    setError(null);
    try {
      const { criteria: ideas } = await api.suggestCriteria(title.trim(), why.trim() || undefined);
      setCriteria((prev) => [...prev, ...ideas.filter((i) => !prev.includes(i))]);
    } catch {
      setError(t.goals.suggestFailed);
    } finally {
      setSuggesting(false);
    }
  }

  async function save() {
    setBusy(true);
    setError(null);
    const payload = {
      title: title.trim(),
      why_text: why.trim() || undefined,
      criteria: criteria.map((text) => ({ text, source: "user" })),
    };
    try {
      if (goal) await api.updateGoal(goal.id, payload);
      else await api.createGoal({ ...payload, why_source: "text" });
      await onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t.goals.saveFailed);
      setBusy(false);
    }
  }

  return (
    <div className="card p-5">
      <div className="space-y-4">
        <Field label={goal ? t.goals.goalLabel : t.goals.newGoal}>
          <input
            className="field"
            autoFocus
            value={title}
            placeholder={t.goals.goalPlaceholder}
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>

        <Field label={t.goals.whyLabel}>
          <textarea
            className="field min-h-[80px] resize-y"
            value={why}
            placeholder={t.goals.whyPlaceholder}
            onChange={(e) => setWhy(e.target.value)}
          />
        </Field>

        <div>
          <Eyebrow>{t.goals.progressMeans}</Eyebrow>
          <ul className="mt-2 space-y-2">
            {criteria.map((text) => (
              <li key={text} className="flex items-center justify-between gap-3">
                <span className="text-[15px]">{text}</span>
                <button
                  onClick={() => setCriteria((prev) => prev.filter((c) => c !== text))}
                  aria-label={`Remove ${text}`}
                  className="font-mono text-[12px] text-muted hover:text-alert"
                >
                  {t.goals.remove}
                </button>
              </li>
            ))}
          </ul>

          <div className="mt-3 flex gap-2">
            <input
              className="field"
              value={draft}
              placeholder={t.goals.criterionPlaceholder}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && draft.trim()) {
                  e.preventDefault();
                  setCriteria((prev) => [...prev, draft.trim()]);
                  setDraft("");
                }
              }}
            />
            <Button
              variant="quiet"
              disabled={!draft.trim()}
              onClick={() => {
                setCriteria((prev) => [...prev, draft.trim()]);
                setDraft("");
              }}
            >
              {t.goals.add}
            </Button>
          </div>

          <button
            onClick={suggest}
            disabled={!title.trim() || suggesting}
            className="mt-3 text-[14px] text-signal underline underline-offset-4 disabled:text-muted disabled:no-underline"
          >
            {suggesting ? t.goals.thinking : t.goals.suggestForMe}
          </button>
        </div>

        {goal && (
          <p className="text-[13px] text-muted">
{t.goals.editNote}
          </p>
        )}

        {error && <Notice tone="error">{error}</Notice>}

        <div className="flex gap-3 pt-1">
          <Button onClick={save} disabled={busy || !title.trim() || criteria.length === 0}>
            {busy ? t.goals.saving : goal ? t.goals.saveChanges : t.goals.createGoal}
          </Button>
          <Button variant="quiet" onClick={onCancel}>
            {t.goals.cancel}
          </Button>
        </div>
      </div>
    </div>
  );
}
