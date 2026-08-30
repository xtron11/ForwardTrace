"""Queries behind the admin panel.

These answer research questions, not "show me a table". The one that matters most is
retention by day: someone who signed up and stopped after one entry and someone who has
logged six days in a row are the same row in a user count, and completely different
signals about whether the product works.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Activity,
    Entry,
    Event,
    Goal,
    PushSubscription,
    Report,
    Status,
    Task,
    User,
)


async def retention(db: AsyncSession) -> dict:
    """How far people get. Day three is the number to watch: it is the first report,
    and anyone who stops before it never sees what they were producing input for."""
    rows = (
        await db.execute(
            select(User.id, User.created_at, func.count(func.distinct(Entry.local_date)))
            .join(Entry, (Entry.user_id == User.id) & (Entry.status == Status.done.value), isouter=True)
            .group_by(User.id, User.created_at)
        )
    ).all()

    buckets = {"signed_up": 0, "day_1": 0, "day_2": 0, "day_3": 0, "day_5": 0, "day_7": 0}
    for _, _, days in rows:
        buckets["signed_up"] += 1
        for threshold, key in ((1, "day_1"), (2, "day_2"), (3, "day_3"), (5, "day_5"), (7, "day_7")):
            if days >= threshold:
                buckets[key] += 1

    # Only count people who have had time to reach a given day, or the funnel punishes
    # you for having signed someone up yesterday.
    now = datetime.now(timezone.utc)
    mature = {key: 0 for key in ("day_1", "day_2", "day_3", "day_5", "day_7")}
    for _, created_at, _ in rows:
        age = (now - created_at.replace(tzinfo=timezone.utc)).days if created_at else 0
        for threshold, key in ((1, "day_1"), (2, "day_2"), (3, "day_3"), (5, "day_5"), (7, "day_7")):
            if age >= threshold:
                mature[key] += 1

    return {"counts": buckets, "eligible": mature}


async def health_numbers(db: AsyncSession) -> dict:
    """Is the machinery working, and what is it costing."""
    entries = (await db.execute(select(func.count(Entry.id)))).scalar_one()
    failed = (
        await db.execute(select(func.count(Entry.id)).where(Entry.status == Status.failed.value))
    ).scalar_one()
    voice = (
        await db.execute(select(func.count(Entry.id)).where(Entry.source == "voice"))
    ).scalar_one()
    dropped = (await db.execute(select(func.sum(Entry.dropped_facts)))).scalar_one() or 0
    edited = (
        await db.execute(select(func.count(Entry.id)).where(Entry.transcript_edited.is_(True)))
    ).scalar_one()
    avg_stt = (await db.execute(select(func.avg(Entry.stt_ms)))).scalar_one()
    avg_llm = (await db.execute(select(func.avg(Entry.llm_ms)))).scalar_one()
    audio_seconds = (await db.execute(select(func.sum(Entry.audio_seconds)))).scalar_one() or 0
    reports = (await db.execute(select(func.count(Report.id)))).scalar_one()

    return {
        "entries": entries,
        "failed": failed,
        "voice_entries": voice,
        "facts_rejected": int(dropped),
        # How often the transcript needed fixing: the honest measure of speech-to-text
        # quality, rather than an impression of it.
        "transcripts_edited": edited,
        "avg_stt_ms": round(avg_stt) if avg_stt else None,
        "avg_llm_ms": round(avg_llm) if avg_llm else None,
        "audio_minutes": round(audio_seconds / 60, 1),
        "reports": reports,
        # Two model calls per entry (extraction, task matching) plus one per report.
        "model_calls": voice * 2 + reports,
    }


async def reminder_effect(db: AsyncSession) -> dict:
    """Did the nudge bring anyone back?

    A reminder goes out only to people who have not checked in that day, so an entry
    afterwards on the same local date is the closest thing to an answer available
    without an experiment.
    """
    reminded = (
        await db.execute(
            select(User.id, User.last_reminded_on).where(User.last_reminded_on.isnot(None))
        )
    ).all()

    followed = 0
    for user_id, day in reminded:
        entry = (
            await db.execute(
                select(Entry.id)
                .where(Entry.user_id == user_id, Entry.local_date == day)
                .limit(1)
            )
        ).scalar_one_or_none()
        if entry is not None:
            followed += 1

    subscriptions = (await db.execute(select(func.count(PushSubscription.id)))).scalar_one()
    subscribers = (
        await db.execute(select(func.count(func.distinct(PushSubscription.user_id))))
    ).scalar_one()

    return {
        "devices": subscriptions,
        "people_subscribed": subscribers,
        "last_reminded": len(reminded),
        "checked_in_after": followed,
    }


async def user_rows(db: AsyncSession) -> list[dict]:
    """One line per person: enough to see who is alive and who went quiet."""
    users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    today = date.today()
    out = []

    for user in users:
        days = (
            await db.execute(
                select(func.count(func.distinct(Entry.local_date))).where(
                    Entry.user_id == user.id, Entry.status == Status.done.value
                )
            )
        ).scalar_one()
        last = (
            await db.execute(
                select(func.max(Entry.local_date)).where(Entry.user_id == user.id)
            )
        ).scalar_one()
        goal = (
            await db.execute(
                select(Goal.title)
                .where(Goal.user_id == user.id, Goal.is_active.is_(True))
                .order_by(Goal.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        reports = (
            await db.execute(select(func.count(Report.id)).where(Report.user_id == user.id))
        ).scalar_one()
        rated = (
            await db.execute(
                select(func.avg(Report.feedback_rating)).where(
                    Report.user_id == user.id, Report.feedback_rating.isnot(None)
                )
            )
        ).scalar_one()

        out.append(
            {
                "id": str(user.id),
                "email": user.email,
                "name": user.display_name,
                "locale": user.locale,
                "timezone": user.timezone,
                "joined": user.created_at.date().isoformat() if user.created_at else "",
                "goal": goal,
                "days_logged": days,
                "last_entry": last.isoformat() if last else None,
                "silent_for": (today - last).days if last else None,
                "reports": reports,
                "avg_rating": round(float(rated), 1) if rated else None,
            }
        )
    return out


async def user_detail(db: AsyncSession, user_id: uuid.UUID) -> dict | None:
    """Everything about one person on one page - for the interview on day seven."""
    user = await db.get(User, user_id)
    if user is None:
        return None

    goals = (
        (await db.execute(select(Goal).where(Goal.user_id == user_id).order_by(Goal.created_at)))
        .scalars()
        .all()
    )
    entries = (
        (
            await db.execute(
                select(Entry)
                .where(Entry.user_id == user_id)
                .order_by(Entry.local_date.desc(), Entry.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    reports = (
        (
            await db.execute(
                select(Report).where(Report.user_id == user_id).order_by(Report.period_start.desc())
            )
        )
        .scalars()
        .all()
    )
    tasks = (
        (await db.execute(select(Task).where(Task.user_id == user_id).order_by(Task.created_at.desc())))
        .scalars()
        .all()
    )

    entry_rows = []
    for entry in entries:
        activities = (
            (await db.execute(select(Activity).where(Activity.entry_id == entry.id)))
            .scalars()
            .all()
        )
        entry_rows.append(
            {
                "id": str(entry.id),
                "date": entry.local_date.isoformat(),
                "status": entry.status,
                "source": entry.source,
                "language": entry.detected_language,
                "transcript": entry.raw_transcript,
                # Shown side by side so a mangled word is visible at a glance.
                "stt_transcript": entry.stt_transcript,
                "edited": entry.transcript_edited,
                "audio_path": entry.audio_path,
                "seconds": entry.audio_seconds,
                "stt_ms": entry.stt_ms,
                "llm_ms": entry.llm_ms,
                "dropped": entry.dropped_facts,
                "error": entry.error,
                "mood": entry.mood,
                "wins": entry.wins or [],
                "friction": entry.friction or [],
                "activities": [
                    {
                        "category": a.category,
                        "minutes": a.minutes,
                        "explicit": a.minutes_explicit,
                        "details": a.details or [],
                        "metrics": a.metrics or [],
                        "quote": a.quote,
                        "goal_id": str(a.goal_id) if a.goal_id else None,
                    }
                    for a in activities
                ],
            }
        )

    events = (
        (
            await db.execute(
                select(Event).where(Event.user_id == user_id).order_by(Event.created_at.desc()).limit(40)
            )
        )
        .scalars()
        .all()
    )

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.display_name,
            "locale": user.locale,
            "timezone": user.timezone,
            "joined": user.created_at.isoformat() if user.created_at else "",
            "reminders_on": user.reminders_on,
            "reminder_hour": user.reminder_hour,
            "intake": user.intake,
        },
        "goals": [
            {"id": str(g.id), "title": g.title, "why": g.why_text, "active": g.is_active,
             "started_on": g.started_on.isoformat() if g.started_on else None}
            for g in goals
        ],
        "entries": entry_rows,
        "reports": [
            {
                "id": str(r.id),
                "period": f"{r.period_start} — {r.period_end}",
                "status": r.status,
                "by": r.generated_by,
                "rating": r.feedback_rating,
                "feedback": r.feedback_text,
                "content": r.content,
                "stats": r.stats,
            }
            for r in reports
        ],
        "tasks": [
            {"text": t.text, "status": t.status, "source": t.source,
             "span": f"{t.starts_on} — {t.ends_on}"}
            for t in tasks
        ],
        "events": [
            {"type": e.type, "at": e.created_at.isoformat() if e.created_at else "", "payload": e.payload}
            for e in events
        ],
    }


async def feedback_rows(db: AsyncSession) -> list[dict]:
    """Ratings with what people actually wrote. The written part is the research."""
    rows = (
        await db.execute(
            select(Report, User.email, Goal.title)
            .join(User, User.id == Report.user_id)
            .join(Goal, Goal.id == Report.goal_id, isouter=True)
            .where(Report.feedback_rating.isnot(None))
            .order_by(Report.feedback_at.desc())
        )
    ).all()

    labels = {4: "точно про меня", 3: "частично", 2: "не узнал себя", 1: "мало данных"}
    return [
        {
            "report_id": str(report.id),
            "user_id": str(report.user_id),
            "email": email,
            "goal": title,
            "period": f"{report.period_start} — {report.period_end}",
            "by": report.generated_by,
            "rating": report.feedback_rating,
            "label": labels.get(report.feedback_rating or 0, "—"),
            "text": report.feedback_text,
            "at": report.feedback_at.date().isoformat() if report.feedback_at else "",
        }
        for report, email, title in rows
    ]


async def recent_entries(db: AsyncSession, limit: int = 40) -> list[dict]:
    """The weekly read: what people said, next to what was taken from it."""
    entries = (
        (await db.execute(select(Entry).order_by(Entry.created_at.desc()).limit(limit)))
        .scalars()
        .all()
    )
    out = []
    for entry in entries:
        user = await db.get(User, entry.user_id)
        activities = (
            (await db.execute(select(Activity).where(Activity.entry_id == entry.id)))
            .scalars()
            .all()
        )
        out.append(
            {
                "id": str(entry.id),
                "user_id": str(entry.user_id),
                "email": user.email if user else "",
                "date": entry.local_date.isoformat(),
                "status": entry.status,
                "language": entry.detected_language,
                "edited": entry.transcript_edited,
                "dropped": entry.dropped_facts,
                "transcript": entry.raw_transcript,
                "activities": [
                    {
                        "category": a.category,
                        "minutes": a.minutes,
                        "explicit": a.minutes_explicit,
                        "metrics": a.metrics or [],
                        "quote": a.quote,
                    }
                    for a in activities
                ],
            }
        )
    return out
