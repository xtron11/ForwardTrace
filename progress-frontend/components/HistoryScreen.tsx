"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { DayCard } from "@/components/DayCard";
import { Button, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { describeError } from "@/lib/i18n";
import type { Day, SearchHit } from "@/lib/types";
import { useT } from "@/lib/useT";

const PAGE = 30;

/** The days with conversations, newest first, and a search over the person's messages. */
export function HistoryScreen() {
  const { t, locale } = useT();
  const [days, setDays] = useState<Day[] | null>(null);
  const [more, setMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const latest = useRef("");

  const loadFirst = useCallback(async () => {
    setError(null);
    try {
      const page = await api.listDays(undefined, PAGE);
      setDays(page);
      setMore(page.length === PAGE);
    } catch (err) {
      setError(describeError(err, t));
    }
  }, [t]);

  useEffect(() => {
    void loadFirst();
  }, [loadFirst]);

  async function loadMore() {
    if (!days?.length) return;
    setLoadingMore(true);
    try {
      const page = await api.listDays(days[days.length - 1].local_date, PAGE);
      setDays([...days, ...page]);
      setMore(page.length === PAGE);
    } catch (err) {
      setError(describeError(err, t));
    }
    setLoadingMore(false);
  }

  // Search as the person types, after a short pause; only the newest answer is kept.
  useEffect(() => {
    const q = query.trim();
    latest.current = q;
    if (!q) {
      setHits(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timer = setTimeout(async () => {
      try {
        const found = await api.search(q);
        if (latest.current === q) setHits(found);
      } catch (err) {
        if (latest.current === q) setError(describeError(err, t));
      }
      if (latest.current === q) setSearching(false);
    }, 350);
    return () => clearTimeout(timer);
  }, [query, t]);

  const searchingNow = query.trim().length > 0;

  return (
    <section className="enter pt-2">
      <h1 className="text-[length:var(--text-base)]">{t.history.title}</h1>

      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t.history.searchPlaceholder}
        aria-label={t.history.searchLabel}
        className="field mt-3"
      />

      {error && (
        <p className="mt-3 text-[length:var(--text-small)] text-error" role="alert">
          {error}
        </p>
      )}

      {searchingNow ? (
        <div className="mt-2">
          {searching && !hits && <Spinner label={t.shell.loading} />}
          {hits && hits.length === 0 && <p className="mt-4 text-dim">{t.history.noResults}</p>}
          {hits?.map((hit) => (
            <Link
              key={hit.message_id}
              href={`/history/${hit.local_date}`}
              className="press block border-b border-line py-3 hover:bg-surface"
            >
              <p className="label">{formatDay(hit.local_date, locale, { day: "numeric", month: "long", year: "numeric" })}</p>
              <p className="mt-1 text-muted">{hit.snippet}</p>
            </Link>
          ))}
        </div>
      ) : days === null ? (
        !error && (
          <div className="mt-6">
            <Spinner label={t.shell.loading} />
          </div>
        )
      ) : days.length === 0 ? (
        <div className="mt-8">
          <p className="text-muted">{t.history.empty}</p>
          <Link href="/today" className="mt-3 inline-block text-sunrise underline underline-offset-4">
            {t.history.emptyCta}
          </Link>
        </div>
      ) : (
        <div className="mt-2">
          {days.map((day) => (
            <DayCard key={day.local_date} day={day} />
          ))}
          {more && (
            <Button className="mt-4" variant="quiet" onClick={() => void loadMore()} disabled={loadingMore}>
              {t.history.more}
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
