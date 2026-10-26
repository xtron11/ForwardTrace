"""The weekly conversation limit and what lifts it (trial, beta Plus).

A conversation counts once the person has sent a message in it
(`conversations.counts_for_limit`). The week runs Monday to Sunday in the person's
time zone; the trial lasts while their local date is before the local registration
date + FREE_TRIAL_DAYS.
"""

from datetime import date, timedelta, timezone

from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Conversation, User
from ..schemas import LimitOut
from ..time_utils import tz_of
from .errors import LIMIT_REACHED, api_error


def week_bounds(today: date) -> tuple[date, date]:
    """Monday and Sunday of the week `today` falls in."""
    monday = today - timedelta(days=today.weekday())
    return monday, monday + timedelta(days=6)


async def _registered_on(db: AsyncSession, user: User) -> date | None:
    if "created_at" in inspect(user).unloaded:
        await db.refresh(user, ["created_at"])
    created = user.created_at
    if created is None:
        return None
    if created.tzinfo is None:  # SQLite hands timestamps back without a zone
        created = created.replace(tzinfo=timezone.utc)
    return created.astimezone(tz_of(user.timezone)).date()


async def limit_status(db: AsyncSession, user: User, today: date) -> LimitOut:
    monday, sunday = week_bounds(today)
    used = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.user_id == user.id,
                Conversation.counts_for_limit.is_(True),
                Conversation.local_date >= monday,
                Conversation.local_date <= sunday,
            )
        )
    ).scalar_one()
    registered = await _registered_on(db, user)
    trial = registered is not None and today < registered + timedelta(days=settings.free_trial_days)
    plus = user.plus_until is not None and user.plus_until >= today
    return LimitOut(used=used, free=settings.free_conversations_per_week, plus=plus, trial=trial)


async def ensure_can_message(
    db: AsyncSession, user: User, conversation: Conversation, today: date
) -> None:
    """402 limit_reached when today is not counted yet and the week is used up.

    A conversation already counted today stays open; the trial and beta Plus
    (`plus_until >= today`) lift the limit.
    """
    if conversation.counts_for_limit:
        return None
    status = await limit_status(db, user, today)
    if status.trial or status.plus or status.used < status.free:
        return None
    raise api_error(
        402, LIMIT_REACHED, "This week's free conversations are used up."
    )
