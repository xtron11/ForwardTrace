"""Weekly statistics.

Every number in the report is produced here, in SQL and Python. The language model
receives these as read-only input and is forbidden from doing arithmetic. That is the
only way the totals in a report can be trusted.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Activity, Entry, Status
from ..time_utils import fmt_minutes


async def compute_stats(
    db: AsyncSession,
    user_id: uuid.UUID,
    goal_id: uuid.UUID | None,
    start: date,
    end: date,
) -> dict:
    entry_filters = [
        Entry.user_id == user_id,
        Entry.local_date >= start,
        Entry.local_date <= end,
        Entry.status == Status.done.value,
    ]
    if goal_id:
        # One check-in can span several goals now, so an entry counts toward this goal
        # when it produced any activity for it - not when the whole entry was filed here.
        entry_filters.append(
            Entry.id.in_(select(Activity.entry_id).where(Activity.goal_id == goal_id))
        )

    entries = (
        (
            await db.execute(
                select(Entry).where(*entry_filters).order_by(Entry.local_date, Entry.created_at)
            )
        )
        .scalars()
        .all()
    )

    act_filters = [
        Activity.user_id == user_id,
        Activity.local_date >= start,
        Activity.local_date <= end,
    ]
    if goal_id:
        act_filters.append(Activity.goal_id == goal_id)

    # Per-category rollup: one query, no JSONB scanning.
    rows = (
        await db.execute(
            select(
                Activity.category,
                func.coalesce(func.sum(Activity.minutes), 0),
                func.count(Activity.id),
                func.count(func.distinct(Activity.local_date)),
                func.count(Activity.minutes),  # counts non-NULL only
            )
            .where(*act_filters)
            .group_by(Activity.category)
            .order_by(func.coalesce(func.sum(Activity.minutes), 0).desc())
        )
    ).all()

    categories = [
        {
            "category": category,
            "total_minutes": int(total or 0),
            "total_human": fmt_minutes(total or 0),
            "sessions": int(sessions),
            "days_active": int(days),
            "sessions_with_time": int(timed),
            # honesty flag: if half the sessions had no stated duration, the total
            # is a floor, not a measurement, and the report must say so
            "time_coverage": round(timed / sessions, 2) if sessions else 0.0,
        }
        for category, total, sessions, days, timed in rows
    ]

    details = (
        (
            await db.execute(
                select(Activity.local_date, Activity.category, Activity.details, Activity.minutes)
                .where(*act_filters)
                .order_by(Activity.local_date)
            )
        )
        .all()
    )

    metric_rows = (
        (await db.execute(select(Activity.metrics).where(*act_filters))).scalars().all()
    )

    logged_days = sorted({e.local_date for e in entries})
    total_minutes = sum(c["total_minutes"] for c in categories)
    period_days = (end - start).days + 1

    # Wins and friction are routed per item, so a Programming report must not inherit
    # a win about the gym that happened to be in the same recording.
    def _for_goal(items: list | None) -> list:
        result = []
        for item in items or []:
            if goal_id is None or str(item.get("goal_id") or "") == str(goal_id):
                result.append(item)
        return result

    wins = [w for e in entries for w in _for_goal(e.wins)]
    friction = [f for e in entries for f in _for_goal(e.friction)]
    moods = [e.mood for e in entries if e.mood]

    return {
        "metrics": _sum_metrics(metric_rows),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "period_days": period_days,
        "days_logged": len(logged_days),
        "entries": len(entries),
        "longest_streak": _longest_streak(logged_days),
        "total_minutes": total_minutes,
        "total_human": fmt_minutes(total_minutes),
        "categories": categories,
        "moods": moods,
        "wins": [w["text"] for w in wins][:10],
        "friction": [f["text"] for f in friction][:10],
        "daily": _daily_breakdown(entries, details),
    }


def _sum_metrics(rows) -> list[dict]:
    """Add up stated quantities by name. This is the arithmetic that turns "10 new words"
    on six separate days into "60 new words this week"."""
    totals: dict[tuple[str, str], dict] = {}
    for metrics in rows:
        for metric in metrics or []:
            name = str(metric.get("name", "")).strip()
            if not name:
                continue
            unit = str(metric.get("unit", "")).strip()
            try:
                value = float(metric.get("value", 0))
            except (TypeError, ValueError):
                continue
            slot = totals.setdefault(
                (name.lower(), unit.lower()),
                {"name": name, "unit": unit, "total": 0.0, "occasions": 0},
            )
            slot["total"] += value
            slot["occasions"] += 1

    out = []
    for slot in totals.values():
        total = slot["total"]
        slot["total"] = int(total) if float(total).is_integer() else round(total, 2)
        out.append(slot)
    return sorted(out, key=lambda m: -m["occasions"])


def _longest_streak(days: list[date]) -> int:
    if not days:
        return 0
    best = run = 1
    for prev, cur in zip(days, days[1:]):
        run = run + 1 if cur - prev == timedelta(days=1) else 1
        best = max(best, run)
    return best


def _daily_breakdown(entries, details) -> list[dict]:
    by_day: dict[date, dict] = {}
    for entry in entries:
        day = by_day.setdefault(
            entry.local_date,
            {"date": entry.local_date.isoformat(), "mood": entry.mood, "items": []},
        )
        day["mood"] = day["mood"] or entry.mood

    for local_date, category, detail_list, minutes in details:
        day = by_day.setdefault(
            local_date, {"date": local_date.isoformat(), "mood": None, "items": []}
        )
        day["items"].append(
            {
                "category": category,
                "minutes": minutes,
                "details": detail_list or [],
            }
        )

    return [by_day[k] for k in sorted(by_day)]
