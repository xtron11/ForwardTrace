"use client";

import { useEffect, useState } from "react";

import { FinishPath } from "@/components/FinishPath";
import { Button, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { describeError } from "@/lib/i18n";
import type { Goal } from "@/lib/types";
import { useT } from "@/lib/useT";

/** Stand-in for the full Progress screen (ticket 09): the goal and the finish line. */
export function ProgressScreen() {
  const { t } = useT();
  const [goal, setGoal] = useState<Goal | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setGoal((await api.memory()).goal);
    } catch (err) {
      setError(describeError(err, t));
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps
    void load();
  }, []);

  return (
    <section className="enter pt-2">
      <h1 className="text-[length:var(--text-base)]">{t.progress.title}</h1>
      <div className="mt-5">
        {error ? (
          <div className="flex flex-col items-start gap-3">
            <p className="text-error" role="alert">
              {error}
            </p>
            <Button variant="quiet" onClick={() => void load()}>
              {t.shell.retry}
            </Button>
          </div>
        ) : goal === undefined ? (
          <Spinner label={t.shell.loading} />
        ) : goal === null ? (
          <p className="text-dim">{t.progress.noGoal}</p>
        ) : (
          <FinishPath goal={goal} />
        )}
      </div>
      {goal && <p className="mt-8 text-[length:var(--text-small)] text-dim">{t.progress.soon}</p>}
    </section>
  );
}
