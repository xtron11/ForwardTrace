"""Progress screen endpoints: GET /api/progress, GET /api/progress/monthly,
POST /api/pairs/{id}/hide, PATCH /api/goal."""

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from ..deps import CurrentUser, Db
from ..models import Goal, MonthlySummary, Pair
from ..schemas import GoalOut, GoalPatch, MonthlySummaryOut, ProgressOut
from ..services import progress as progress_service
from ..services.events import log_event
from ..services.errors import NOT_FOUND, api_error
from ..time_utils import local_today

router = APIRouter(prefix="/api", tags=["progress"])


@router.get("/progress", response_model=ProgressOut)
async def get_progress(user: CurrentUser, db: Db) -> ProgressOut:
    """The Progress screen: goal and finish line, the latest level facts, before-and-after
    cards, threads, and the newest monthly summary not opened yet. No model is called."""
    return await progress_service.progress_for(db, user)


@router.get("/progress/monthly", response_model=MonthlySummaryOut)
async def get_monthly(
    user: CurrentUser, db: Db, month: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
) -> MonthlySummaryOut:
    """One month's summary. The first open stamps `viewed_at`; a month without a ready
    summary (none built, or a failed one) is 404."""
    first = date(int(month[:4]), int(month[5:]), 1)
    row = (
        await db.execute(
            select(MonthlySummary).where(
                MonthlySummary.user_id == user.id,
                MonthlySummary.month == first,
                MonthlySummary.status.in_(progress_service.SHOWN_STATUSES),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise api_error(404, NOT_FOUND, "There is no summary for that month.")
    if row.viewed_at is None:
        row.viewed_at = datetime.now(timezone.utc)
        await log_event(db, user, "monthly_summary_viewed", {"month": month})
        await db.commit()
    return await progress_service.monthly_out(db, user, row)


@router.post("/pairs/{pair_id}/hide", status_code=204)
async def hide_pair(pair_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    """Hide a before-and-after card. Repeating it changes nothing."""
    pair = await db.get(Pair, pair_id)
    if pair is None or pair.user_id != user.id:
        raise api_error(404, NOT_FOUND, "Card not found.")
    if pair.hidden_at is None:
        pair.hidden_at = datetime.now(timezone.utc)
        await log_event(db, user, "pair_hidden", {"pair_id": str(pair.id)})
        await db.commit()
    return Response(status_code=204)


@router.patch("/goal", response_model=GoalOut)
async def patch_goal(payload: GoalPatch, user: CurrentUser, db: Db) -> Goal:
    """Change the anchor goal's title, motivation or finish line from the profile.
    Only the keys present in the body change; `finish_line: null` means "no finish line"."""
    goal = (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user.id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if goal is None:
        raise api_error(404, NOT_FOUND, "There is no goal yet.")

    sent = payload.model_fields_set
    if "title" in sent:
        title = (payload.title or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail="The title is empty.")
        goal.title = title
    if "why_text" in sent:
        # The person's own words typed here, not a quote from a message.
        goal.why_text = (payload.why_text or "").strip() or None
        goal.why_message_id = None
    if "finish_line" in sent:
        finish = (payload.finish_line or "").strip()
        if finish:
            goal.finish_line = finish
            goal.finish_set_on = local_today(user.timezone)
            await log_event(db, user, "finish_set", {"where": "profile"})
        else:
            goal.finish_line = None
            goal.finish_set_on = None
    await db.commit()
    await db.refresh(goal)
    return goal
