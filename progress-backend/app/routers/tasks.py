"""Tasks: things the person decided to do, for a span of days they chose.

No completion endpoint exists on purpose. Nothing here marks a task done or failed -
the comparison between intention and what was said is shown, and the person judges it.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import Goal, Task
from ..schemas import TaskCreate, TaskOut, TaskSuggestionsOut, TaskUpdate
from ..services import prompts
from ..services.llm import LLMError, complete_json
from ..services.tasks import active_tasks, should_suggest, task_summary
from ..time_utils import local_today

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


async def _count_active(db, user_id: uuid.UUID, today: date) -> int:
    return (
        await db.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.status == "active",
                Task.ends_on >= today,
            )
        )
    ).scalar_one()


@router.get("", response_model=list[TaskOut])
async def list_tasks(user: CurrentUser, db: Db, include_closed: bool = False) -> list[dict]:
    """What is on today, with how it has gone so far."""
    today = local_today(user.timezone)
    query = select(Task).where(Task.user_id == user.id).order_by(Task.created_at.desc())
    if not include_closed:
        query = query.where(Task.status == "active", Task.ends_on >= today)

    tasks = (await db.execute(query)).scalars().all()
    return [
        {**await task_summary(db, task), "status": task.status, "source": task.source}
        for task in tasks
    ]


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(payload: TaskCreate, user: CurrentUser, db: Db) -> dict:
    today = local_today(user.timezone)

    if await _count_active(db, user.id, today) >= settings.max_active_tasks:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{settings.max_active_tasks} is the limit. Past that, matching what you "
                "said against what you intended stops being reliable."
            ),
        )

    if payload.goal_id is not None:
        goal = (
            await db.execute(
                select(Goal).where(Goal.id == payload.goal_id, Goal.user_id == user.id)
            )
        ).scalar_one_or_none()
        if goal is None:
            raise HTTPException(status_code=404, detail="Goal not found")

    task = Task(
        user_id=user.id,
        goal_id=payload.goal_id,
        text=payload.text.strip(),
        source=payload.source,
        starts_on=today,
        ends_on=today + timedelta(days=payload.days - 1),
    )
    db.add(task)
    # Taking something on clears any earlier "not now".
    user.tasks_declined_on = None
    await db.commit()
    await db.refresh(task)
    return {**await task_summary(db, task), "status": task.status, "source": task.source}


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID, payload: TaskUpdate, user: CurrentUser, db: Db
) -> dict:
    task = (
        await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    data = payload.model_dump(exclude_unset=True)
    if "text" in data and data["text"]:
        task.text = data["text"].strip()
    if "extend_days" in data and data["extend_days"]:
        task.ends_on = task.ends_on + timedelta(days=data["extend_days"])
    if data.get("close"):
        # Closing is not failing. The record of what happened stays exactly as it was.
        task.status = "closed"
        task.closed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(task)
    return {**await task_summary(db, task), "status": task.status, "source": task.source}


@router.post("/decline", status_code=204)
async def decline_suggestions(user: CurrentUser, db: Db) -> None:
    """Not now. Nothing is suggested again for a few days."""
    user.tasks_declined_on = local_today(user.timezone)
    await db.commit()


@router.get("/suggestions", response_model=TaskSuggestionsOut)
async def suggestions(user: CurrentUser, db: Db) -> TaskSuggestionsOut:
    """Ideas drawn from their own recent friction, offered only when nothing is on."""
    today = local_today(user.timezone)
    active = await _count_active(db, user.id, today)

    if not should_suggest(user, today, active):
        return TaskSuggestionsOut(should_ask=False, suggestions=[])

    goal = (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user.id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if goal is None:
        return TaskSuggestionsOut(should_ask=False, suggestions=[])

    from ..models import Entry

    recent = (
        (
            await db.execute(
                select(Entry)
                .where(Entry.user_id == user.id, Entry.status == "done")
                .order_by(Entry.local_date.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    friction = [f.get("text", "") for e in recent for f in (e.friction or [])][:6]

    try:
        result = await complete_json(
            system=prompts.TASK_SUGGEST_SYSTEM + prompts._write_in(user.locale),
            user=prompts.task_suggest_user_prompt(goal.title, goal.why_text, friction),
            schema=prompts.TASK_SUGGEST_SCHEMA,
        )
    except LLMError:
        # Better to offer nothing than to invent something generic.
        return TaskSuggestionsOut(should_ask=True, suggestions=[])

    ideas = [str(t).strip() for t in result.data.get("suggestions", []) if str(t).strip()]
    return TaskSuggestionsOut(should_ask=True, suggestions=ideas[:3])
