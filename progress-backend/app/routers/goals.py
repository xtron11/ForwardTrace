import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import Criterion, Goal
from ..schemas import (
    GoalCreate,
    GoalOut,
    GoalUpdate,
    SuggestCriteriaIn,
    SuggestCriteriaOut,
)
from ..services import prompts
from ..services.llm import LLMError, complete_json
from ..time_utils import local_today

router = APIRouter(prefix="/api/goals", tags=["goals"])


async def _load_goal(db, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
    goal = (
        await db.execute(
            select(Goal)
            # Only active criteria: deactivated ones are kept so old reports can still
            # resolve the ids they reference, but they are not part of the goal now.
            .options(selectinload(Goal.criteria.and_(Criterion.is_active.is_(True))))
            .where(Goal.id == goal_id, Goal.user_id == user_id)
            # Without this the identity map hands back the collection as it was loaded
            # earlier in the request, so a just-replaced criterion list looks unchanged.
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.post("/suggest-criteria", response_model=SuggestCriteriaOut)
async def suggest_criteria(payload: SuggestCriteriaIn, user: CurrentUser) -> SuggestCriteriaOut:
    """Suggestions only. The user decides what counts as progress - we never impose it."""
    try:
        result = await complete_json(
            system=prompts.criteria_system(user.locale),
            user=prompts.criteria_user_prompt(payload.title, payload.why_text),
            schema=prompts.CRITERIA_SCHEMA,
        )
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=f"Could not generate suggestions: {exc}") from exc

    items = [str(c).strip() for c in result.data.get("criteria", []) if str(c).strip()]
    return SuggestCriteriaOut(criteria=items[:4])


@router.post("", response_model=GoalOut, status_code=201)
async def create_goal(payload: GoalCreate, user: CurrentUser, db: Db) -> Goal:
    active = (
        await db.execute(
            select(func.count(Goal.id)).where(
                Goal.user_id == user.id, Goal.is_active.is_(True)
            )
        )
    ).scalar_one()
    if active >= settings.max_active_goals:
        raise HTTPException(
            status_code=409,
            detail=(
                f"You already have {settings.max_active_goals} active goals. "
                "Archive one before adding another."
            ),
        )

    goal = Goal(
        user_id=user.id,
        title=payload.title,
        why_text=payload.why_text,
        why_source=payload.why_source,
        started_on=local_today(user.timezone),
    )
    db.add(goal)
    await db.flush()

    for position, criterion in enumerate(payload.criteria):
        db.add(
            Criterion(
                goal_id=goal.id,
                text=criterion.text,
                source=criterion.source,
                position=position,
            )
        )

    await db.commit()
    return await _load_goal(db, user.id, goal.id)


@router.get("", response_model=list[GoalOut])
async def list_goals(user: CurrentUser, db: Db) -> list[Goal]:
    rows = await db.execute(
        select(Goal)
        .options(selectinload(Goal.criteria.and_(Criterion.is_active.is_(True))))
        .where(Goal.user_id == user.id)
        .order_by(Goal.created_at.desc())
        .execution_options(populate_existing=True)
    )
    return list(rows.scalars().all())


@router.get("/{goal_id}", response_model=GoalOut)
async def get_goal(goal_id: uuid.UUID, user: CurrentUser, db: Db) -> Goal:
    return await _load_goal(db, user.id, goal_id)


@router.patch("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: uuid.UUID, payload: GoalUpdate, user: CurrentUser, db: Db
) -> Goal:
    goal = await _load_goal(db, user.id, goal_id)
    data = payload.model_dump(exclude_unset=True)
    new_criteria = data.pop("criteria", None)

    for field, value in data.items():
        setattr(goal, field, value)

    if new_criteria is not None:
        # Deactivate rather than delete: old reports reference these ids.
        for existing in goal.criteria:
            existing.is_active = False
        for position, criterion in enumerate(new_criteria):
            db.add(
                Criterion(
                    goal_id=goal.id,
                    text=criterion["text"],
                    source=criterion.get("source", "user"),
                    position=position,
                )
            )

    await db.commit()
    return await _load_goal(db, user.id, goal_id)
