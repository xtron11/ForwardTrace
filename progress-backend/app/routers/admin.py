"""Admin surface for the concierge phase.

While there are ten users, you want to read every transcript, see which facts the
verifier threw away, and occasionally hand-write a report to test whether a *better*
report changes retention. These endpoints exist for exactly that.
"""

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ..deps import AdminUser, CurrentUser, Db
from ..models import Activity, Entry, Event, Goal, Report, Status, User
from ..schemas import EventIn, ReportOut

router = APIRouter(prefix="/api", tags=["admin"])


class HandWrittenReport(BaseModel):
    content: dict


@router.post("/events", status_code=201)
async def log_event(payload: EventIn, user: CurrentUser, db: Db) -> dict:
    """Client-side research telemetry: recording_started, report_opened, checkin_abandoned."""
    db.add(Event(user_id=user.id, type=payload.type, payload=payload.payload))
    await db.commit()
    return {"ok": True}


@router.get("/admin/overview")
async def overview(admin: AdminUser, db: Db) -> dict:
    """One glance at whether the experiment is alive."""
    users = (await db.execute(select(func.count(User.id)))).scalar_one()
    entries = (await db.execute(select(func.count(Entry.id)))).scalar_one()
    failed = (
        await db.execute(select(func.count(Entry.id)).where(Entry.status == Status.failed.value))
    ).scalar_one()
    dropped = (await db.execute(select(func.sum(Entry.dropped_facts)))).scalar_one() or 0
    avg_stt = (await db.execute(select(func.avg(Entry.stt_ms)))).scalar_one()
    avg_llm = (await db.execute(select(func.avg(Entry.llm_ms)))).scalar_one()

    ratings = (
        await db.execute(
            select(Report.feedback_rating, func.count(Report.id))
            .where(Report.feedback_rating.isnot(None))
            .group_by(Report.feedback_rating)
        )
    ).all()

    per_user = (
        await db.execute(
            select(User.email, func.count(Entry.id))
            .join(Entry, Entry.user_id == User.id, isouter=True)
            .group_by(User.email)
            .order_by(func.count(Entry.id).desc())
        )
    ).all()

    return {
        "users": users,
        "entries": entries,
        "failed_entries": failed,
        "facts_rejected_by_verifier": int(dropped),
        "avg_stt_ms": round(avg_stt) if avg_stt else None,
        "avg_llm_ms": round(avg_llm) if avg_llm else None,
        "feedback_distribution": {str(r): c for r, c in ratings},
        "entries_per_user": [{"email": e, "entries": c} for e, c in per_user],
    }


@router.get("/admin/entries")
async def admin_entries(admin: AdminUser, db: Db, limit: int = 100) -> list[dict]:
    """Every transcript next to what was extracted from it. Read these by hand, weekly."""
    rows = (
        await db.execute(
            select(Entry).order_by(Entry.created_at.desc()).limit(min(limit, 500))
        )
    ).scalars().all()

    output = []
    for entry in rows:
        activities = (
            await db.execute(select(Activity).where(Activity.entry_id == entry.id))
        ).scalars().all()
        output.append(
            {
                "id": str(entry.id),
                "user_id": str(entry.user_id),
                "local_date": entry.local_date.isoformat(),
                "status": entry.status,
                "source": entry.source,
                "transcript": entry.raw_transcript,
                "audio_path": entry.audio_path,
                "stt_ms": entry.stt_ms,
                "llm_ms": entry.llm_ms,
                "stt_cost_usd": entry.stt_cost_usd,
                "llm_cost_usd": entry.llm_cost_usd,
                "llm_calls": entry.llm_calls,
                "llm_input_tokens": entry.llm_input_tokens,
                "llm_cached_tokens": entry.llm_cached_tokens,
                "llm_output_tokens": entry.llm_output_tokens,
                "dropped_facts": entry.dropped_facts,
                "error": entry.error,
                "activities": [
                    {
                        "category": a.category,
                        "minutes": a.minutes,
                        "minutes_explicit": a.minutes_explicit,
                        "details": a.details,
                        "quote": a.quote,
                    }
                    for a in activities
                ],
                "wins": entry.wins,
                "friction": entry.friction,
            }
        )
    return output


@router.put("/admin/reports/{report_id}/content", response_model=ReportOut)
async def hand_write_report(
    report_id: uuid.UUID, payload: HandWrittenReport, admin: AdminUser, db: Db
) -> Report:
    """Override a generated report with one you wrote yourself.

    This is the concierge lever: before automating the analysis, confirm that a genuinely
    good report is something people want. If a hand-written report also gets a shrug, the
    problem is the product, not the model.
    """
    report = await db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    report.content = payload.content
    report.status = Status.done.value
    report.generated_by = "human"
    report.error = None
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/admin/feedback")
async def admin_feedback(admin: AdminUser, db: Db) -> list[dict]:
    rows = (
        await db.execute(
            select(Report, User.email, Goal.title)
            .join(User, User.id == Report.user_id)
            .join(Goal, Goal.id == Report.goal_id, isouter=True)
            .where(Report.feedback_rating.isnot(None))
            .order_by(Report.feedback_at.desc())
        )
    ).all()
    return [
        {
            "report_id": str(report.id),
            "email": email,
            "goal": title,
            "period": f"{report.period_start} to {report.period_end}",
            "generated_by": report.generated_by,
            "rating": report.feedback_rating,
            "text": report.feedback_text,
        }
        for report, email, title in rows
    ]
