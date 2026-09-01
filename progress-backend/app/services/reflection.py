"""The answer a person gets straight after telling you about their day.

The product's own author records his day into a general-purpose assistant every evening
and does not use his own product. His reason: the assistant gives him back his original
motivation and notices what has changed since earlier conversations.

This does that, with one difference that is the whole point. An assistant remembers
loosely and can invent what you said. Here every claim about the past carries a date and
a verbatim quote, and the quote is checked against the actual entry before the person
sees a word of it.

Nothing here praises. A person praised for every day stops believing the praise, and
then stops believing everything else the product tells them.
"""

import json
import logging
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Entry, Goal, Status
from . import prompts, verify
from .llm import LLMError, complete_json

log = logging.getLogger(__name__)

# How far back to offer the model material from.
LOOKBACK_DAYS = 21
# Entries from the very beginning, for "you did not know where to go, and now...".
EARLIEST_ENTRIES = 3

# Flattery and diagnosis, caught after the fact rather than merely forbidden in the
# prompt. Both languages, because the prompt is English and the output is not.
BANNED = (
    "молодец", "отлично", "так держать", "прекрасно", "здорово", "браво",
    "горжусь", "восхищ", "потрясающ", "невероятн", "ты справляешься",
    "не сдавайся", "верь в себя", "у тебя всё получится",
    "выгорание", "прокрастинац", "синдром самозванца", "боишься неудачи",
    "тревожность", "депресс", "перфекционизм",
    "well done", "great job", "keep it up", "keep going", "amazing", "incredible",
    "proud of you", "you're doing great", "you've got this", "don't give up",
    "burnout", "impostor syndrome", "afraid of failure", "procrastination",
)


def _is_banned(text: str) -> bool:
    lowered = text.lower()
    return "!" in text or any(phrase in lowered for phrase in BANNED)


async def _history(db: AsyncSession, user_id: uuid.UUID, today: date) -> dict:
    """Material for the model, and the entries its quotes will be checked against."""
    since = today - timedelta(days=LOOKBACK_DAYS)

    recent = (
        (
            await db.execute(
                select(Entry)
                .where(
                    Entry.user_id == user_id,
                    Entry.status == Status.done.value,
                    Entry.local_date >= since,
                    Entry.local_date < today,
                )
                .order_by(Entry.local_date.desc())
            )
        )
        .scalars()
        .all()
    )

    earliest = (
        (
            await db.execute(
                select(Entry)
                .where(Entry.user_id == user_id, Entry.status == Status.done.value)
                .order_by(Entry.local_date)
                .limit(EARLIEST_ENTRIES)
            )
        )
        .scalars()
        .all()
    )

    goal = (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user_id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    # Repeated friction, with how often and when. Counted here rather than left to the
    # model, which would guess at "you keep saying this".
    friction: dict[str, list[str]] = {}
    for entry in recent:
        for item in entry.friction or []:
            text = (item.get("text") or "").strip()
            if text:
                friction.setdefault(text, []).append(entry.local_date.isoformat())

    return {
        "goal": goal.title if goal else None,
        "why": goal.why_text if goal else None,
        "earliest": [
            {"date": e.local_date.isoformat(), "said": e.raw_transcript}
            for e in earliest
        ],
        "recent": [
            {
                "date": e.local_date.isoformat(),
                "said": e.raw_transcript,
                "mood": e.mood,
            }
            for e in recent[:10]
        ],
        "recurring_friction": [
            {"what": text, "times": len(dates), "dates": dates}
            for text, dates in sorted(friction.items(), key=lambda kv: -len(kv[1]))
            if len(dates) > 1
        ][:5],
        # Everything the quotes will be checked against, by date.
        "_entries_by_date": {
            e.local_date.isoformat(): (e.raw_transcript or "")
            for e in list(recent) + list(earliest)
        },
    }


def _build_prompt(today_said: str, history: dict, numbers: dict) -> str:
    block = {
        "today_they_said": today_said,
        "their_goal": history["goal"],
        "why_they_started": history["why"],
        "their_first_entries": history["earliest"],
        "recent_entries": history["recent"],
        "difficulties_that_keep_returning": history["recurring_friction"],
        "counted_for_them": numbers,
    }
    return json.dumps(block, ensure_ascii=False, indent=2)


def _validate(data: dict, entries_by_date: dict[str, str]) -> list[dict]:
    """Drop anything unverifiable. An empty result is a normal outcome."""
    if data.get("say_nothing"):
        return []

    kept = []
    for item in data.get("paragraphs") or []:
        text = (item.get("text") or "").strip()
        if not text or _is_banned(text):
            continue

        ref_date = (item.get("reference_date") or "").strip()
        ref_quote = (item.get("reference_quote") or "").strip()

        # No reference: a paragraph purely about today, which needs no checking.
        if not ref_date and not ref_quote:
            kept.append({"text": text[:900], "reference": None})
            continue

        source = entries_by_date.get(ref_date)
        if source is None:
            # A date the person never wrote on. Telling them they said something on a
            # day they said nothing is the exact failure this whole product avoids.
            log.info("reflection: dropped a paragraph citing an unknown date %s", ref_date)
            continue
        if not verify.quote_supported(ref_quote, verify.normalize(source)):
            log.info("reflection: dropped a paragraph with an unverifiable quote")
            continue

        kept.append(
            {
                "text": text[:900],
                "reference": {"date": ref_date, "quote": ref_quote[:400]},
            }
        )
        if len(kept) >= 3:
            break

    return kept


async def reflect(
    db: AsyncSession,
    user_id: uuid.UUID,
    transcript: str,
    today: date,
    numbers: dict,
    locale: str | None = None,
) -> list[dict]:
    """Returns paragraphs to show, possibly none. Never raises."""
    if len(transcript.strip()) < 20:
        return []

    history = await _history(db, user_id, today)

    try:
        result = await complete_json(
            system=prompts.REFLECTION_SYSTEM + prompts._write_in(locale),
            user=prompts.reflection_user_prompt(
                _build_prompt(transcript, history, numbers)
            ),
            schema=prompts.REFLECTION_SCHEMA,
        )
    except LLMError as exc:
        # The facts are already extracted and stored; this sits on top of them and
        # must not cost the person their check-in.
        log.warning("reflection failed: %s", exc)
        return []

    return _validate(result.data, history["_entries_by_date"])
