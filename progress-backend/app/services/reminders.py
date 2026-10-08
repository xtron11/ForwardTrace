"""The daily nudge.

The product asks for input every day and pays it back later. That gap is where people
quit, and most of them quit by forgetting rather than by deciding. A reminder is the
cheapest thing that closes it.

Two rules keep this from becoming spam, and both are here rather than in the sender:

  * nobody is reminded on a day they have already checked in;
  * nobody is reminded twice in a day, however often the loop wakes.

Runs in-process on a timer. For ten users that is right; a real queue is worth having
at the point where a second API worker is, and not before.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..models import Entry, PushSubscription, User
from ..time_utils import local_today, tz_of
from . import push

log = logging.getLogger(__name__)

MESSAGES = {
    "en": {
        "title": "How did today go?",
        "body": "Thirty seconds. What you worked on, what got in the way.",
    },
    "ru": {
        "title": "Как прошёл день?",
        "body": "Тридцать секунд. Над чем работал, что помешало.",
    },
}


def _local_hour(tz_name: str | None, now: datetime) -> int:
    return now.astimezone(tz_of(tz_name)).hour


async def _due_users(db, now: datetime) -> list[User]:
    """People whose local evening has arrived, who have a device, and who have not
    checked in today."""
    candidates = (
        (
            await db.execute(
                select(User)
                .where(User.is_active.is_(True), User.reminders_on.is_(True))
                .where(User.deleted_at.is_(None))
                .where(User.id.in_(select(PushSubscription.user_id)))
            )
        )
        .scalars()
        .all()
    )

    due = []
    for user in candidates:
        today = local_today(user.timezone, now)
        if user.last_reminded_on == today:
            continue
        if _local_hour(user.timezone, now) != user.reminder_hour:
            continue

        already = (
            await db.execute(
                select(Entry.id)
                .where(Entry.user_id == user.id, Entry.local_date == today)
                .limit(1)
            )
        ).scalar_one_or_none()
        if already is not None:
            # Reminding someone to do a thing they have done is worse than silence.
            continue

        due.append(user)
    return due


async def run_once(now: datetime | None = None) -> int:
    """One pass. Returns how many people were reminded."""
    if not settings.vapid_private_key:
        return 0

    moment = now or datetime.now(timezone.utc)
    reminded = 0

    async with SessionLocal() as db:
        for user in await _due_users(db, moment):
            text = MESSAGES.get((user.locale or "en")[:2], MESSAGES["en"])
            delivered = await push.send_to_user(
                db,
                user.id,
                {"title": text["title"], "body": text["body"], "url": "/today"},
            )
            # Mark it either way: a person whose devices have all gone stale should not
            # be retried every quarter of an hour until midnight.
            user.last_reminded_on = local_today(user.timezone, moment)
            await db.commit()
            if delivered:
                reminded += 1

    if reminded:
        log.info("reminders sent to %s people", reminded)
    return reminded


async def loop() -> None:
    """Background task started at app startup and cancelled at shutdown."""
    interval = settings.reminder_tick_minutes * 60
    log.info("reminder loop started, every %s minutes", settings.reminder_tick_minutes)
    while True:
        try:
            await asyncio.sleep(interval)
            await run_once()
        except asyncio.CancelledError:
            log.info("reminder loop stopped")
            raise
        except Exception:  # noqa: BLE001 - a scheduler that dies silently is worse
            log.exception("reminder pass failed; continuing")
