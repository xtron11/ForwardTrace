"""Matching what someone intended against what they actually said.

There is no completion flag anywhere in here. A task is never marked done or failed:
the entry either speaks to it or it does not, and the person reads the comparison and
decides for themselves. Marking things failed is what the products they left behind do.

The same rule as everywhere else applies - a match must carry a verbatim quote, and the
quote is checked against the transcript before anything is stored.
"""

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Task, TaskMention
from . import prompts, verify
from .llm import LLMError, complete_json

log = logging.getLogger(__name__)


async def active_tasks(db: AsyncSession, user_id: uuid.UUID, on: date) -> list[Task]:
    """Tasks whose span covers this day."""
    rows = await db.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status == "active",
            Task.starts_on <= on,
            Task.ends_on >= on,
        )
        .order_by(Task.created_at)
    )
    return list(rows.scalars().all())


async def match_entry(
    db: AsyncSession,
    user_id: uuid.UUID,
    entry_id: uuid.UUID,
    transcript: str,
    local_date: date,
    locale: str | None = None,
) -> int:
    """Record which intentions this entry speaks to. Returns how many matched."""
    tasks = await active_tasks(db, user_id, local_date)
    if not tasks:
        return 0

    try:
        result = await complete_json(
            system=prompts.TASK_MATCH_SYSTEM + prompts._write_in(locale),
            user=prompts.task_match_user_prompt(
                [{"id": str(t.id), "text": t.text} for t in tasks], transcript
            ),
            schema=prompts.TASK_MATCH_SCHEMA,
        )
    except LLMError as exc:
        # A failed match is not worth failing the check-in over: the facts are already
        # extracted and stored, and this is a comparison on top of them.
        log.warning("task matching failed for entry %s: %s", entry_id, exc)
        return 0

    valid = {str(t.id): t for t in tasks}
    transcript_norm = verify.normalize(transcript)
    stored = 0

    for match in result.data.get("matches", []):
        task_id = str(match.get("task_id", ""))
        quote = (match.get("quote") or "").strip()
        if task_id not in valid:
            continue
        if not verify.quote_supported(quote, transcript_norm):
            # Telling someone they did a thing they did not say is worse than saying
            # nothing, so an unverifiable match is dropped rather than softened.
            log.info("dropped unverifiable task match on entry %s", entry_id)
            continue

        db.add(
            TaskMention(
                task_id=uuid.UUID(task_id),
                entry_id=entry_id,
                local_date=local_date,
                evidence=quote[:400],
            )
        )
        stored += 1

    return stored


async def task_summary(db: AsyncSession, task: Task) -> dict:
    """Days touched out of days spanned, plus the evidence. No verdict."""
    mentions = (
        (
            await db.execute(
                select(TaskMention)
                .where(TaskMention.task_id == task.id)
                .order_by(TaskMention.local_date)
            )
        )
        .scalars()
        .all()
    )
    span_days = (task.ends_on - task.starts_on).days + 1
    return {
        "id": str(task.id),
        "text": task.text,
        "starts_on": task.starts_on.isoformat(),
        "ends_on": task.ends_on.isoformat(),
        "span_days": span_days,
        "days_touched": len({m.local_date for m in mentions}),
        "evidence": [
            {"date": m.local_date.isoformat(), "quote": m.evidence} for m in mentions
        ],
    }


def should_suggest(user, today: date, active_count: int) -> bool:
    """Only when there is nothing on: an intention already in play is reason enough to
    come back, and a second prompt on top of it is noise."""
    if active_count > 0:
        return False
    if user.tasks_declined_on is None:
        return True
    return (today - user.tasks_declined_on).days >= settings.task_suggestion_cooldown_days
