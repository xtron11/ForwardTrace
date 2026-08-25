import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import Goal, Report, Status
from ..schemas import FeedbackIn, ReportGenerateIn, ReportOut
from ..services.reports import generate_report_task
from ..time_utils import completed_period, local_today, period_bounds

router = APIRouter(prefix="/api/reports", tags=["reports"])


async def _active_goal(db, user, goal_id: uuid.UUID | None) -> Goal:
    query = select(Goal).where(Goal.user_id == user.id)
    if goal_id:
        query = query.where(Goal.id == goal_id)
    else:
        query = query.where(Goal.is_active.is_(True)).order_by(Goal.created_at.desc())
    goal = (await db.execute(query.limit(1))).scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="No goal found")
    return goal


@router.post("", response_model=ReportOut, status_code=202)
async def generate(
    payload: ReportGenerateIn, background: BackgroundTasks, user: CurrentUser, db: Db
) -> Report:
    """Create (or return) the report for a period.

    A report is generated once and stored. Re-requesting returns the same text: the
    report is a research artefact, and a document that rewrites itself on every refresh
    is neither trustworthy nor comparable across users.
    """
    goal = await _active_goal(db, user, payload.goal_id)
    today = local_today(user.timezone)

    if payload.period_end:
        start, end = period_bounds(payload.period_end)
    else:
        window = completed_period(goal.started_on or today, today)
        if window is None:
            raise HTTPException(
                status_code=425,
                detail=f"The first {settings.report_period_days}-day period is not over yet.",
            )
        start, end = window

    existing = (
        await db.execute(
            select(Report).where(
                Report.user_id == user.id,
                Report.goal_id == goal.id,
                Report.period_start == start,
            )
        )
    ).scalar_one_or_none()

    if existing and not payload.force:
        if existing.status == Status.failed.value:
            existing.status = Status.pending.value
            existing.error = None
            await db.commit()
            background.add_task(generate_report_task, existing.id)
        return existing

    if existing:
        report = existing
        report.status = Status.pending.value
        report.content = None
        report.error = None
    else:
        report = Report(
            user_id=user.id,
            goal_id=goal.id,
            period_start=start,
            period_end=end,
            status=Status.pending.value,
        )
        db.add(report)

    try:
        await db.commit()
    except IntegrityError:  # concurrent double-click
        await db.rollback()
        return (
            await db.execute(
                select(Report).where(
                    Report.user_id == user.id,
                    Report.goal_id == goal.id,
                    Report.period_start == start,
                )
            )
        ).scalar_one()

    await db.refresh(report)
    background.add_task(generate_report_task, report.id)
    return report


@router.get("", response_model=list[ReportOut])
async def list_reports(user: CurrentUser, db: Db, limit: int = 20) -> list[Report]:
    rows = await db.execute(
        select(Report)
        .where(Report.user_id == user.id)
        .order_by(Report.period_start.desc())
        .limit(min(limit, 100))
    )
    return list(rows.scalars().all())


@router.get("/latest", response_model=ReportOut)
async def latest_report(user: CurrentUser, db: Db) -> Report:
    report = (
        await db.execute(
            select(Report)
            .where(Report.user_id == user.id)
            .order_by(Report.period_start.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="No report yet")
    return report


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(report_id: uuid.UUID, user: CurrentUser, db: Db) -> Report:
    report = (
        await db.execute(
            select(Report).where(Report.id == report_id, Report.user_id == user.id)
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/{report_id}/feedback", response_model=ReportOut)
async def submit_feedback(
    report_id: uuid.UUID, payload: FeedbackIn, user: CurrentUser, db: Db
) -> Report:
    """The single most important endpoint in the MVP: it is the research instrument."""
    report = (
        await db.execute(
            select(Report).where(Report.id == report_id, Report.user_id == user.id)
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    report.feedback_rating = payload.rating
    report.feedback_text = payload.text
    report.feedback_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)
    return report
