"use client";

import type { Goal } from "@/lib/types";
import { useT } from "@/lib/useT";

/** The goal, why it matters, and the finish line (or "just growing"). The recent
 *  "level" facts join it on the full Progress screen. */
export function FinishPath({ goal }: { goal: Goal }) {
  const { t } = useT();
  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="label">{t.progress.goal}</p>
        <p className="mt-1">{goal.title}</p>
      </div>
      {goal.why_text && (
        <div>
          <p className="label">{t.progress.why}</p>
          <p className="mt-1">
            <span className="said">«{goal.why_text}»</span>
          </p>
        </div>
      )}
      <div>
        <p className="label">{t.progress.finish}</p>
        <p className="mt-1">{goal.finish_line ?? t.progress.noFinish}</p>
      </div>
    </div>
  );
}
