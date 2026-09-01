"""The numbers the Today screen is built from.

All computed in SQL and Python, never by a model. Two rules shape what is in here and
what deliberately is not:

  * nothing decreases - days in the journey never fall, a thin day adds nothing rather
    than taking something away;
  * nothing reports absence - a personal record appears when one is set and is simply
    missing otherwise, and there is no "less than yesterday" anywhere.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Activity, Entry, Goal, Status
from ..time_utils import completed_period

HORIZON_DAYS = 14


async def _days_in_journey(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Days on which something was said. Never a streak: a gap costs nothing, it just
    does not add."""
    return (
        await db.execute(
            select(func.count(func.distinct(Entry.local_date))).where(
                Entry.user_id == user_id, Entry.status == Status.done.value
            )
        )
    ).scalar_one()


async def _horizon(
    db: AsyncSession, user_id: uuid.UUID, today: date, goal_id: uuid.UUID | None
) -> list[dict]:
    """One bar per day for the last fortnight, sized by how much was said."""
    start = today - timedelta(days=HORIZON_DAYS - 1)
    filters = [
        Entry.user_id == user_id,
        Entry.status == Status.done.value,
        Entry.local_date >= start,
        Entry.local_date <= today,
    ]
    if goal_id:
        filters.append(
            Entry.id.in_(select(Activity.entry_id).where(Activity.goal_id == goal_id))
        )

    rows = (
        await db.execute(
            select(
                Entry.local_date,
                func.count(Entry.id),
                func.coalesce(func.sum(func.length(Entry.raw_transcript)), 0),
            )
            .where(*filters)
            .group_by(Entry.local_date)
        )
    ).all()

    by_day = {row[0]: {"entries": row[1], "chars": int(row[2] or 0)} for row in rows}
    busiest = max((d["chars"] for d in by_day.values()), default=0)

    horizon = []
    for offset in range(HORIZON_DAYS):
        day = start + timedelta(days=offset)
        data = by_day.get(day)
        horizon.append(
            {
                "date": day.isoformat(),
                "has_entry": data is not None,
                # 0..1 against the fullest day in view, so the shape reflects effort
                # without ever implying a target was missed.
                "weight": round(data["chars"] / busiest, 3) if data and busiest else 0.0,
            }
        )
    return horizon


async def _accumulated(
    db: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID | None
) -> dict | None:
    """The person's most-used counted quantity, totalled over all time.

    Lifetime rather than per-period on purpose: this is the number that only ever grows,
    which is what makes a weak day survivable.
    """
    filters = [Activity.user_id == user_id]
    if goal_id:
        filters.append(Activity.goal_id == goal_id)

    rows = (await db.execute(select(Activity.metrics).where(*filters))).scalars().all()

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

    if not totals:
        return None
    best = max(totals.values(), key=lambda m: m["occasions"])
    total = best["total"]
    best["total"] = int(total) if float(total).is_integer() else round(total, 2)
    return best


async def _personal_record(
    db: AsyncSession, user_id: uuid.UUID, today: date, goal_id: uuid.UUID | None
) -> dict | None:
    """Set today and beaten nothing before it? Say so. Otherwise say nothing at all -
    the absence of a record is not information the person needs."""
    filters = [Activity.user_id == user_id]
    if goal_id:
        filters.append(Activity.goal_id == goal_id)

    rows = (
        await db.execute(select(Activity.local_date, Activity.metrics).where(*filters))
    ).all()

    per_day: dict[tuple[str, str], dict[date, float]] = {}
    labels: dict[tuple[str, str], tuple[str, str]] = {}
    for local_date, metrics in rows:
        for metric in metrics or []:
            name = str(metric.get("name", "")).strip()
            if not name:
                continue
            unit = str(metric.get("unit", "")).strip()
            try:
                value = float(metric.get("value", 0))
            except (TypeError, ValueError):
                continue
            key = (name.lower(), unit.lower())
            labels.setdefault(key, (name, unit))
            bucket = per_day.setdefault(key, {})
            bucket[local_date] = bucket.get(local_date, 0.0) + value

    for key, days in per_day.items():
        todays = days.get(today)
        if todays is None:
            continue
        earlier = [value for day, value in days.items() if day < today]
        # A first-ever day is not a record: there was nothing for it to beat, and
        # calling it one would be the kind of manufactured praise this product avoids.
        if not earlier or todays <= max(earlier):
            continue

        name, unit = labels[key]
        best_before = max(earlier)
        return {
            "name": name,
            "unit": unit,
            "value": int(todays) if float(todays).is_integer() else round(todays, 2),
            "previous_best": (
                int(best_before) if float(best_before).is_integer() else round(best_before, 2)
            ),
        }
    return None


async def daily_summary(
    db: AsyncSession, user_id: uuid.UUID, today: date, goal_id: uuid.UUID | None = None
) -> dict:
    goal = None
    if goal_id is None:
        goal = (
            await db.execute(
                select(Goal)
                .where(Goal.user_id == user_id, Goal.is_active.is_(True))
                .order_by(Goal.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        goal_id = goal.id if goal else None
    else:
        goal = await db.get(Goal, goal_id)

    checked_in = (
        await db.execute(
            select(Entry.id)
            .where(Entry.user_id == user_id, Entry.local_date == today)
            .limit(1)
        )
    ).scalar_one_or_none() is not None

    days_until_report = None
    if goal is not None and goal.started_on is not None:
        elapsed = (today - goal.started_on).days
        first = settings.first_report_after_days
        if elapsed < first:
            days_until_report = first - elapsed
        else:
            period = settings.report_period_days
            days_until_report = period - ((elapsed - first) % period)

    return {
        "days_in_journey": await _days_in_journey(db, user_id),
        "checked_in_today": checked_in,
        "horizon": await _horizon(db, user_id, today, goal_id),
        "accumulated": await _accumulated(db, user_id, goal_id),
        "personal_record": await _personal_record(db, user_id, today, goal_id),
        "days_until_report": days_until_report,
        "goal_title": goal.title if goal else None,
        "goal_id": str(goal_id) if goal_id else None,
        "has_completed_period": (
            goal is not None
            and goal.started_on is not None
            and completed_period(goal.started_on, today) is not None
        ),
    }
