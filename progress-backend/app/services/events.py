"""The one way v2 writes to the `events` research log.

Every event carries the same three facts about the person, so the admin numbers can be
cut by them without joins: which day since registration it is (by their local dates,
registration day = 1), their interface language and the channel the AI writes to them
through. The caller commits.
"""

from datetime import datetime, timezone

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Event, User
from ..time_utils import local_today, tz_of


def day_number(user: User, at: datetime | None = None) -> int | None:
    """1 on the local day of registration, 2 the day after, and so on."""
    if user.created_at is None:
        return None
    created = user.created_at
    if created.tzinfo is None:  # SQLite hands timestamps back without a zone
        created = created.replace(tzinfo=timezone.utc)
    registered_on = created.astimezone(tz_of(user.timezone)).date()
    return (local_today(user.timezone, at) - registered_on).days + 1


async def log_event(
    db: AsyncSession, user: User | None, type: str, payload: dict | None = None
) -> None:
    data = dict(payload or {})
    if user is not None:
        if "created_at" in inspect(user).unloaded:
            # A server default not read back yet; loading it lazily would fail in async.
            await db.refresh(user, ["created_at"])
        data.update(
            day_number=day_number(user),
            language=user.locale,
            channel=user.outreach_channel,
        )
    db.add(Event(user_id=user.id if user is not None else None, type=type, payload=data or None))
