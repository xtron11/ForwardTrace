"""The monthly digest.

Everything here is computed, not written. The numbers come from SQL, the changes come
from weekly reports that already passed validation, and the two quotes are simply the
first and last thing the person said that month.

That last choice is deliberate. Asking a model to pick "the quote that best shows the
difference" invites it to find a story; taking the earliest and latest entry finds
nothing and shows the difference anyway, in the person's own words. If a month contains
no change, this will show that too, which is the point.

Rare on purpose: monthly, not weekly. The format works because it does not arrive often.
"""

import uuid
from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Activity, Entry, Goal, Report, Status


@dataclass(slots=True)
class MonthBounds:
    start: date
    end: date

    @classmethod
    def of(cls, year: int, month: int) -> "MonthBounds":
        return cls(date(year, month, 1), date(year, month, monthrange(year, month)[1]))


async def _entries(db: AsyncSession, user_id: uuid.UUID, bounds: MonthBounds) -> list[Entry]:
    rows = await db.execute(
        select(Entry)
        .where(
            Entry.user_id == user_id,
            Entry.status == Status.done.value,
            Entry.local_date >= bounds.start,
            Entry.local_date <= bounds.end,
        )
        .order_by(Entry.local_date, Entry.created_at)
    )
    return list(rows.scalars().all())


async def _metric_totals(
    db: AsyncSession, user_id: uuid.UUID, bounds: MonthBounds
) -> list[dict]:
    rows = (
        await db.execute(
            select(Activity.metrics).where(
                Activity.user_id == user_id,
                Activity.local_date >= bounds.start,
                Activity.local_date <= bounds.end,
            )
        )
    ).scalars().all()

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
                {"name": name, "unit": unit, "total": 0.0, "days": set()},
            )
            slot["total"] += value

    out = []
    for slot in totals.values():
        total = slot.pop("total")
        slot.pop("days", None)
        slot["total"] = int(total) if float(total).is_integer() else round(total, 2)
        out.append(slot)
    return sorted(out, key=lambda m: -m["total"])[:3]


async def _strongest_day(
    db: AsyncSession, user_id: uuid.UUID, bounds: MonthBounds
) -> dict | None:
    """The day with the most stated minutes. Ties and empty months simply return
    nothing rather than crowning an arbitrary day."""
    rows = (
        await db.execute(
            select(Activity.local_date, func.coalesce(func.sum(Activity.minutes), 0))
            .where(
                Activity.user_id == user_id,
                Activity.local_date >= bounds.start,
                Activity.local_date <= bounds.end,
            )
            .group_by(Activity.local_date)
            .order_by(func.coalesce(func.sum(Activity.minutes), 0).desc())
            .limit(1)
        )
    ).first()

    if rows is None or not rows[1]:
        return None

    day, minutes = rows
    entry = (
        await db.execute(
            select(Entry)
            .where(Entry.user_id == user_id, Entry.local_date == day)
            .order_by(Entry.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()

    quote = None
    if entry is not None:
        activity = (
            await db.execute(
                select(Activity.quote)
                .where(Activity.entry_id == entry.id, Activity.quote.isnot(None))
                .limit(1)
            )
        ).scalar_one_or_none()
        quote = activity

    return {"date": day.isoformat(), "minutes": int(minutes), "quote": quote}


async def _changes(
    db: AsyncSession, user_id: uuid.UUID, bounds: MonthBounds
) -> list[dict]:
    """Taken from the month's reports, which already passed validation. Nothing is
    written here - a change that was not good enough for a weekly report is not good
    enough for this one either."""
    reports = (
        (
            await db.execute(
                select(Report)
                .where(
                    Report.user_id == user_id,
                    Report.status == Status.done.value,
                    Report.period_end >= bounds.start,
                    Report.period_start <= bounds.end,
                )
                .order_by(Report.period_start)
            )
        )
        .scalars()
        .all()
    )

    seen: set[str] = set()
    changes: list[dict] = []
    for report in reports:
        for item in (report.content or {}).get("what_changed", []):
            text = (item.get("text") or "").strip()
            if not text or text.lower() in seen:
                continue
            seen.add(text.lower())
            changes.append({"text": text, "evidence": (item.get("evidence") or "").strip()})
    return changes[:3]


async def monthly_digest(
    db: AsyncSession, user_id: uuid.UUID, year: int, month: int
) -> dict:
    bounds = MonthBounds.of(year, month)
    entries = await _entries(db, user_id, bounds)

    goal = (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user_id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    days = sorted({e.local_date for e in entries})

    # Earliest and latest thing they said this month, side by side. No model chooses
    # these: the pair either shows a difference or it does not, and both are honest.
    first_said = entries[0].raw_transcript if entries else None
    last_said = entries[-1].raw_transcript if entries else None

    return {
        "year": year,
        "month": month,
        "period_start": bounds.start.isoformat(),
        "period_end": bounds.end.isoformat(),
        "goal_title": goal.title if goal else None,
        "goal_why": goal.why_text if goal else None,
        "days_logged": len(days),
        "days_in_month": (bounds.end - bounds.start).days + 1,
        "entries": len(entries),
        "metrics": await _metric_totals(db, user_id, bounds),
        "strongest_day": await _strongest_day(db, user_id, bounds),
        "changes": await _changes(db, user_id, bounds),
        "then": (
            {"date": entries[0].local_date.isoformat(), "said": first_said}
            if entries
            else None
        ),
        "now": (
            {"date": entries[-1].local_date.isoformat(), "said": last_said}
            if len(entries) > 1
            else None
        ),
        # A month with almost nothing in it should say so rather than dress up two
        # check-ins as a retrospective.
        "thin": len(days) < 5,
    }
