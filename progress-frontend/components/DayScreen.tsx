"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { MessageBubble } from "@/components/MessageBubble";
import { Button, Notice, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { describeError } from "@/lib/i18n";
import type { Conversation } from "@/lib/types";
import { useT } from "@/lib/useT";

/** One day's conversation in full: voice messages play, quotes link and play, and the
 *  whole day can be deleted after a confirmation. */
export function DayScreen() {
  const { date } = useParams<{ date: string }>();
  const { t, locale } = useT();
  const router = useRouter();
  const [conv, setConv] = useState<Conversation | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setConv(null);
    setMissing(false);
    api
      .getConversation(date)
      .then((c) => !cancelled && setConv(c))
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) setMissing(true);
        else setError(describeError(err, t));
      });
    return () => {
      cancelled = true;
    };
  }, [date, t]);

  async function remove() {
    setDeleting(true);
    setError(null);
    try {
      await api.deleteConversation(date);
      router.replace("/history");
    } catch (err) {
      setError(describeError(err, t));
      setDeleting(false);
      setConfirming(false);
    }
  }

  return (
    <section className="enter pt-2">
      <Link href="/history" className="label hover:text-bone">
        ‹ {t.history.back}
      </Link>
      <h1 className="mt-2 text-[length:var(--text-base)]">
        {formatDay(date, locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
      </h1>

      {error && (
        <div className="mt-4">
          <Notice tone="error">{error}</Notice>
        </div>
      )}
      {missing && <p className="mt-6 text-dim">{t.history.notFound}</p>}
      {!conv && !missing && !error && (
        <div className="mt-6">
          <Spinner label={t.shell.loading} />
        </div>
      )}

      {conv && (
        <>
          <div className="mt-6 flex flex-col gap-5">
            {conv.messages.map((m) => (
              <MessageBubble key={m.id} message={m} currentDay={date} />
            ))}
          </div>

          <div className="mt-10 border-t border-line pt-4">
            {confirming ? (
              <div className="flex flex-col gap-3">
                <p className="text-muted">{t.history.deleteAsk}</p>
                <div className="flex gap-3">
                  <Button onClick={() => void remove()} disabled={deleting}>
                    {deleting ? t.history.deleting : t.history.deleteYes}
                  </Button>
                  <Button variant="quiet" onClick={() => setConfirming(false)} disabled={deleting}>
                    {t.history.deleteNo}
                  </Button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="press font-mono text-[length:var(--text-label)] uppercase tracking-[0.16em] text-label transition-colors hover:text-error"
              >
                {t.history.delete}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
