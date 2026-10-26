"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { addDays, formatDay, weekStart, weekdayShort } from "@/lib/dates";
import { useT } from "@/lib/useT";

/** How far back the strip can be swiped, in weeks. */
const MAX_WEEKS_BACK = 104;
const SWIPE_PX = 48;

/**
 * The week above the conversation. Days that counted are green, today is ringed, days
 * to come are dimmed. Swiping (or the arrows) turns the weeks; each week is fetched
 * from /api/calendar when first needed, the one before it ahead of time.
 *
 *  - green day: opens that day in the history
 *  - today: scrolls to the conversation
 *  - an earlier empty day: says there was no conversation
 */
export function WeekStrip({
  today,
  refreshKey,
  onToday,
}: {
  today: string;
  /** Changes whenever the person has talked, so the current week is fetched again. */
  refreshKey: number;
  onToday: () => void;
}) {
  const { t, locale } = useT();
  const router = useRouter();
  const [offset, setOffset] = useState(0); // weeks back from the current one
  const [active, setActive] = useState<Record<string, boolean>>({});
  const [hint, setHint] = useState<string | null>(null);
  const loaded = useRef(new Set<string>());
  const trackRef = useRef<HTMLDivElement>(null);
  const touch = useRef<{ x: number; y: number } | null>(null);
  const direction = useRef(0);
  const firstRender = useRef(true);

  const thisWeek = weekStart(today);
  const start = addDays(thisWeek, -7 * offset);
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));

  const load = useCallback(async (monday: string, force = false) => {
    if (!force && loaded.current.has(monday)) return;
    loaded.current.add(monday);
    try {
      const rows = await api.calendar(monday, addDays(monday, 6));
      setActive((prev) => ({ ...prev, ...Object.fromEntries(rows.map((d) => [d.local_date, d.active])) }));
    } catch {
      loaded.current.delete(monday);
    }
  }, []);

  useEffect(() => {
    void load(start);
    void load(addDays(start, -7));
  }, [start, load]);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    void load(thisWeek, true);
  }, [refreshKey, thisWeek, load]);

  // The slide: new week comes in from the side the person swiped towards.
  useEffect(() => {
    const dir = direction.current;
    if (!dir || !trackRef.current?.animate) return;
    trackRef.current.animate(
      [
        { transform: `translateX(${dir * 36}px)`, opacity: 0 },
        { transform: "translateX(0)", opacity: 1 },
      ],
      { duration: 220, easing: "cubic-bezier(.16,1,.3,1)" },
    );
  }, [offset]);

  useEffect(() => {
    if (!hint) return;
    const timer = setTimeout(() => setHint(null), 3000);
    return () => clearTimeout(timer);
  }, [hint]);

  function turn(delta: number) {
    // delta +1 = one week back (the new week enters from the left).
    const next = Math.min(MAX_WEEKS_BACK, Math.max(0, offset + delta));
    if (next === offset) return;
    direction.current = delta > 0 ? -1 : 1;
    setHint(null);
    setOffset(next);
  }

  function pick(day: string) {
    if (day > today) return;
    if (day === today) {
      onToday();
      return;
    }
    if (active[day]) {
      void api.logEvent("week_strip_day_opened");
      router.push(`/history/${day}`);
      return;
    }
    setHint(t.today.emptyDay);
  }

  return (
    <section aria-label={t.today.weekStrip} className="pt-1">
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          onClick={() => turn(1)}
          aria-label={t.today.prevWeek}
          className="press -m-2 p-2 text-label hover:text-bone"
        >
          ‹
        </button>
        <p className="label">{formatDay(start, locale, { month: "long", year: "numeric" })}</p>
        <button
          type="button"
          onClick={() => turn(-1)}
          disabled={offset === 0}
          aria-label={t.today.nextWeek}
          className="press -m-2 p-2 text-label hover:text-bone disabled:opacity-30"
        >
          ›
        </button>
      </div>

      <div
        ref={trackRef}
        className="grid touch-pan-y grid-cols-7 gap-1"
        onTouchStart={(e) => {
          const p = e.touches[0];
          touch.current = { x: p.clientX, y: p.clientY };
        }}
        onTouchEnd={(e) => {
          const from = touch.current;
          touch.current = null;
          if (!from) return;
          const p = e.changedTouches[0];
          const dx = p.clientX - from.x;
          if (Math.abs(dx) >= SWIPE_PX && Math.abs(p.clientY - from.y) < Math.abs(dx)) {
            turn(dx > 0 ? 1 : -1);
          }
        }}
      >
        {days.map((day) => {
          const isToday = day === today;
          const future = day > today;
          const green = !!active[day];
          return (
            <button
              key={day}
              type="button"
              onClick={() => pick(day)}
              aria-current={isToday ? "date" : undefined}
              aria-disabled={future || undefined}
              aria-label={`${formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })}`}
              className={`flex min-w-0 flex-col items-center gap-1 rounded-md py-1.5 transition-colors ${
                future ? "opacity-40" : "press"
              }`}
            >
              <span className="label tracking-normal">{weekdayShort(day, locale)}</span>
              <span
                className={`flex h-9 w-9 items-center justify-center rounded-full font-display text-[length:var(--text-small)] ${
                  green ? "bg-active text-on-accent" : "text-bone"
                } ${isToday ? "ring-2 ring-sunrise ring-offset-2 ring-offset-ink" : ""}`}
              >
                {Number(day.slice(8))}
              </span>
            </button>
          );
        })}
      </div>

      <p className="mt-1 h-5 text-center text-[length:var(--text-small)] text-dim" role="status">
        {hint}
      </p>
    </section>
  );
}
