"""Progress screen endpoints. Ticket 04 adds only PATCH /api/goal; /api/progress,
/api/progress/monthly and /api/pairs/{id}/hide come with the progress tickets."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..deps import CurrentUser, Db
from ..models import Criterion, Goal
from ..schemas import GoalOut, GoalPatch
from ..services.errors import NOT_FOUND, api_error
from ..time_utils import local_today

router = APIRouter(prefix="/api", tags=["progress"])


@router.patch("/goal", response_model=GoalOut)
async def patch_goal(payload: GoalPatch, user: CurrentUser, db: Db) -> Goal:
    """Change the anchor goal's title, motivation or finish line from the profile.
    Only the keys present in the body change; `finish_line: null` means "no finish line"."""
    goal = (
        await db.execute(
            select(Goal)
            .options(selectinload(Goal.criteria.and_(Criterion.is_active.is_(True))))
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
        else:
            goal.finish_line = None
            goal.finish_set_on = None
    await db.commit()
    await db.refresh(goal)
    return goal
