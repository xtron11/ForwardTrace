"""The AI writes first: one short question a day, at the person's hour.

Every tick (REMINDER_TICK_MINUTES) the loop takes
people with reminders on, a channel other than "none", the opening conversation done,
whose local hour is `reminder_hour` and who have not been written to today
(`last_reminded_on`). It stays quiet when:

  * the person has already written today;
  * their last message was safety level 3 - until they write again;
  * they went OUTREACH_FAREWELL_DAYS without a word: one farewell, then nothing until
    they write;
  * OUTREACH_PAUSE_AFTER messages in a row went unanswered: then only every
    OUTREACH_PAUSE_EVERY_DAYS days.

Topic, in order: an open thread mentioned within OUTREACH_THREAD_RECENT_DAYS, the goal
after OUTREACH_ANCHOR_SILENCE_DAYS of silence, yesterday's conversation, a general
question. The model writes the text (one quote at most, as a placeholder rendered from
the database); a broken rule or a failed call means the topic's template instead.

The message is stored in the day's conversation (started_by = ai) whether or not it can
be delivered: the person sees it when they open the app. The day is not painted green
by it - only the person's own message does that (services/conversation.py, which also
resets `outreach_unanswered` and stamps `replied_at`).

State lives in the database, so a restart in the middle of a pass repeats nothing.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal
from ..models import Conversation, Fact, Goal, Message, Outreach, Thread, User
from ..time_utils import local_today, tz_of
from . import prompts, push, telegram, texts
from .events import log_event
from .llm import LLMError, complete_json

log = logging.getLogger(__name__)


@dataclass
class Topic:
    kind: str  # thread | anchor | yesterday | general | farewell
    thread: Thread | None = None
    goal: Goal | None = None
    yesterday: Conversation | None = None
    # Facts the model may point to with a placeholder.
    facts: list[Fact] = field(default_factory=list)


@dataclass(slots=True)
class _LastWord:
    """The person's latest message: when, on which local day, at what safety level."""

    at: datetime
    day: date
    safety_level: int


def _aware(moment: datetime) -> datetime:
    # SQLite hands timestamps back without a zone; they are stored in UTC.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


async def _last_word(db: AsyncSession, user_id: uuid.UUID) -> _LastWord | None:
    row = (
        await db.execute(
            select(Message.created_at, Message.safety_level, Conversation.local_date)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(Message.user_id == user_id, Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    return _LastWord(at=_aware(row[0]), day=row[2], safety_level=row[1] or 0)


def _silent_days(user: User, last: _LastWord | None, today: date) -> int:
    """Days since the person last wrote; never wrote - since registration."""
    if last is not None:
        return (today - last.day).days
    created = _aware(user.created_at) if user.created_at else datetime.now(timezone.utc)
    return (today - created.astimezone(tz_of(user.timezone)).date()).days


# ------------------------------------------------------------------ the topic


async def _facts(db: AsyncSession, query, limit: int = 3) -> list[Fact]:
    return list(
        (
            await db.execute(
                query.where(Fact.flagged_at.is_(None))
                .order_by(Fact.local_date.desc(), Fact.created_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


async def pick_topic(db: AsyncSession, user: User, today: date) -> Topic:
    """What today's first message is about, by the brief's priority."""
    since = today - timedelta(days=settings.outreach_thread_recent_days)
    thread = (
        await db.execute(
            select(Thread)
            .where(
                Thread.user_id == user.id,
                Thread.status == "open",
                Thread.last_mentioned_on.is_not(None),
                Thread.last_mentioned_on >= since,
            )
            .order_by(Thread.last_mentioned_on.desc(), Thread.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if thread is not None:
        facts = await _facts(db, select(Fact).where(Fact.user_id == user.id, Fact.thread_id == thread.id))
        return Topic("thread", thread=thread, facts=facts)

    last = await _last_word(db, user.id)
    goal = (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user.id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if goal is not None and _silent_days(user, last, today) >= settings.outreach_anchor_silence_days:
        facts = await _facts(db, select(Fact).where(Fact.user_id == user.id), limit=2)
        return Topic("anchor", goal=goal, facts=facts)

    yesterday = (
        await db.execute(
            select(Conversation).where(
                Conversation.user_id == user.id,
                Conversation.local_date == today - timedelta(days=1),
                Conversation.counts_for_limit.is_(True),
            )
        )
    ).scalar_one_or_none()
    if yesterday is not None:
        facts = await _facts(
            db,
            select(Fact).where(Fact.user_id == user.id, Fact.local_date == yesterday.local_date),
        )
        return Topic("yesterday", yesterday=yesterday, facts=facts)

    return Topic("general")


# ------------------------------------------------------------------ the text


def _template(user: User, topic: Topic) -> str:
    locale = user.locale
    if topic.kind == "thread" and topic.thread is not None:
        return texts.t(locale, "outreach.thread", title=topic.thread.title)
    if topic.kind == "anchor" and topic.goal is not None:
        return texts.t(locale, "outreach.anchor", goal=topic.goal.title)
    if topic.kind == "yesterday":
        return texts.t(locale, "outreach.yesterday")
    if topic.kind == "farewell":
        return texts.t(locale, "outreach.farewell")
    return texts.t(locale, "outreach.general")


def _breaks_rules(segments: list[dict], used: list[str]) -> list[str]:
    """What is wrong with the model's message: "empty", "length", "questions",
    "quotes", "banned". Quotes are the person's words and do not count as length."""
    from .conversation import BANNED

    prose = "".join(s["text"] for s in segments if s["type"] == "text")
    problems = []
    if not prose.strip():
        problems.append("empty")
    if len(prose.split()) > settings.outreach_max_words:
        problems.append("length")
    if prose.count("?") != 1:
        problems.append("questions")
    if len(used) > 1:
        problems.append("quotes")
    lowered = prose.lower()
    if any(phrase in lowered for phrase in BANNED):
        problems.append("banned")
    return problems


@dataclass(slots=True)
class _Written:
    content_raw: str
    segments: list[dict]
    quick_replies: list[str]
    used_fact_ids: list[str]
    model_name: str | None
    template: bool


def _from_template(user: User, topic: Topic) -> _Written:
    text = _template(user, topic)
    return _Written(text, [{"type": "text", "text": text}], [], [], None, True)


async def _write(db: AsyncSession, user: User, topic: Topic, today: date) -> _Written:
    if topic.kind == "farewell":
        return _from_template(user, topic)

    details = []
    if topic.thread is not None:
        details.append(f"Open difficulty: {topic.thread.title} (last mentioned {topic.thread.last_mentioned_on})")
    if topic.goal is not None:
        details.append(f"Their goal: {topic.goal.title}")
        if topic.goal.why_text:
            details.append(f'Why it matters to them, in their words: "{topic.goal.why_text}"')
        if topic.goal.finish_line:
            details.append(f"Their finish line: {topic.goal.finish_line}")
    if topic.yesterday is not None and topic.yesterday.summary:
        details.append(f"Yesterday in one line: {topic.yesterday.summary}")

    system = prompts.outreach_system(
        user.locale,
        topic=topic.kind,
        skill=user.skill or (topic.goal.title if topic.goal else None),
        details=details,
        facts=[f'[{f.id}] {f.local_date.isoformat()} {f.type}: "{f.quote}"' for f in topic.facts],
        max_words=settings.outreach_max_words,
    )
    try:
        result = await complete_json(
            system, prompts.outreach_user_prompt(today.isoformat()), prompts.OUTREACH_SCHEMA
        )
    except LLMError:
        log.warning("outreach model failed for %s; using the template", user.id)
        return _from_template(user, topic)

    from .conversation import ReplyRenderer

    text = result.data.get("text") if isinstance(result.data, dict) else None
    renderer = ReplyRenderer({str(f.id): f for f in topic.facts})
    renderer.feed(text if isinstance(text, str) else "")
    rendered = renderer.finish()
    problems = _breaks_rules(rendered.segments, rendered.used_fact_ids)
    if problems:
        await log_event(db, user, "outreach_rule_violation", {"topic": topic.kind, "rules": problems})
        return _from_template(user, topic)

    quick = result.data.get("quick_replies") or []
    quick = [q.strip()[:80] for q in quick if isinstance(q, str) and q.strip()]
    return _Written(
        rendered.content_raw,
        rendered.segments,
        quick[: settings.max_quick_replies],
        rendered.used_fact_ids,
        result.model,
        False,
    )


def plain_text(locale: str | None, segments: list[dict]) -> str:
    """Segments as one line for a push or a Telegram message: no placeholders, quotes
    in «» (Russian) or “” (English)."""
    russian = (locale or "").startswith("ru")
    parts = []
    for segment in segments:
        if segment.get("type") == "quote":
            quote = segment.get("quote", "")
            parts.append(f"«{quote}»" if russian else f"“{quote}”")
        else:
            parts.append(segment.get("text", ""))
    return "".join(parts).strip()


# ------------------------------------------------------------------ delivery


async def deliver(db: AsyncSession, user: User, outreach: Outreach, text_plain: str) -> bool:
    """Push or Telegram, by the row's channel. False when there is nowhere to deliver
    or delivery failed; the message stays in the conversation either way."""
    path = f"/today?o={outreach.id}"
    try:
        if outreach.channel == "telegram":
            if not (telegram.enabled() and user.telegram_chat_id):
                return False
            return await telegram.send_message(
                user.telegram_chat_id,
                text_plain,
                telegram.app_link(path),
                button_text=texts.t(user.locale, "outreach.reply_button"),
            )
        if outreach.channel == "push":
            delivered = await push.send_to_user(
                db,
                user.id,
                {
                    "title": texts.t(user.locale, "outreach.push_title"),
                    "body": text_plain,
                    "url": path,
                    "tag": f"ft-{outreach.id}",
                },
            )
            return delivered > 0
    except Exception:  # noqa: BLE001 - one person's broken channel must not stop the pass
        log.exception("outreach %s: delivery failed", outreach.id)
    return False


# ------------------------------------------------------------------ one pass


async def _farewell_sent_since(db: AsyncSession, user_id: uuid.UUID, since: datetime | None) -> bool:
    query = select(Outreach.id).where(Outreach.user_id == user_id, Outreach.topic == "farewell")
    if since is not None:
        query = query.where(Outreach.sent_at > since)
    return (await db.execute(query.limit(1))).first() is not None


async def _decide(db: AsyncSession, user: User, today: date) -> Topic | None:
    """The topic to write about today, or None to stay quiet."""
    last = await _last_word(db, user.id)
    if last is not None and last.day >= today:
        return None  # they have already written today
    if last is not None and last.safety_level >= 3:
        return None  # until the person writes again

    silent = _silent_days(user, last, today)
    if silent >= settings.outreach_farewell_days:
        if await _farewell_sent_since(db, user.id, last.at if last else None):
            return None
        return Topic("farewell")

    if user.outreach_unanswered >= settings.outreach_pause_after and user.last_reminded_on:
        if (today - user.last_reminded_on).days < settings.outreach_pause_every_days:
            return None

    return await pick_topic(db, user, today)


async def _find_day(db: AsyncSession, user_id: uuid.UUID, today: date) -> Conversation | None:
    return (
        await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id, Conversation.local_date == today
            )
        )
    ).scalar_one_or_none()


async def _day_conversation(db: AsyncSession, user: User, today: date) -> Conversation:
    user_id = user.id
    conversation = await _find_day(db, user_id, today)
    if conversation is None:
        conversation = Conversation(
            user_id=user_id, local_date=today, kind="daily", started_by="ai"
        )
        try:
            # A savepoint: losing the race rolls back only this insert, so `user` and
            # everything else in the session stay loaded.
            async with db.begin_nested():
                db.add(conversation)
        except IntegrityError:
            # The person opened the app at this very moment and created the day.
            conversation = await _find_day(db, user_id, today)
            if conversation is None:
                raise
    # Nothing from the person yet (checked before): the AI is the one starting it.
    conversation.started_by = "ai"
    return conversation


async def _write_to(db: AsyncSession, user: User, now: datetime) -> bool:
    today = local_today(user.timezone, now)
    topic = await _decide(db, user, today)
    if topic is None:
        return False

    written = await _write(db, user, topic, today)
    conversation = await _day_conversation(db, user, today)
    message = Message(
        conversation_id=conversation.id,
        user_id=user.id,
        role="assistant",
        source="outreach",
        content_raw=written.content_raw,
        content=written.segments,
        quick_replies=written.quick_replies or None,
        used_fact_ids=written.used_fact_ids or None,
        intent="normal",
        model_name=written.model_name,
        created_at=now,
    )
    db.add(message)
    await db.flush()
    row = Outreach(
        user_id=user.id,
        conversation_id=conversation.id,
        message_id=message.id,
        topic=topic.kind,
        thread_id=topic.thread.id if topic.thread is not None else None,
        channel=user.outreach_channel,
        sent_at=now,
        delivered=False,
    )
    db.add(row)
    user.last_reminded_on = today
    user.outreach_unanswered = (user.outreach_unanswered or 0) + 1
    # Committed before delivery: a crash while sending cannot send it twice.
    await db.commit()

    row.delivered = await deliver(db, user, row, plain_text(user.locale, written.segments))
    await log_event(
        db,
        user,
        "outreach_sent",
        {
            "outreach_id": str(row.id),
            "topic": row.topic,
            "delivered": row.delivered,
            "template": written.template,
        },
    )
    await db.commit()
    return True


async def run_once(now: datetime | None = None) -> int:
    """One pass. Returns how many people were written to (delivered or not)."""
    moment = now or datetime.now(timezone.utc)
    written = 0
    async with SessionLocal() as db:
        candidates = (
            await db.execute(
                select(User.id, User.timezone, User.reminder_hour, User.last_reminded_on).where(
                    User.is_active.is_(True),
                    User.deleted_at.is_(None),
                    User.reminders_on.is_(True),
                    # The opening conversation is still going: a daily message would
                    # start a "daily" day and cut it off.
                    User.first_conversation_done.is_(True),
                    User.outreach_channel != "none",
                )
            )
        ).all()
    due = []
    for user_id, tz_name, hour, last_reminded_on in candidates:
        local = moment.astimezone(tz_of(tz_name))
        if local.hour == hour and last_reminded_on != local.date():
            due.append(user_id)

    for user_id in due:
        # A session per person: one failure rolls back only that person.
        try:
            async with SessionLocal() as db:
                user = await db.get(User, user_id)
                if user is not None and await _write_to(db, user, moment):
                    written += 1
        except Exception:  # noqa: BLE001 - one person must not stop the others
            log.exception("outreach to %s failed", user_id)
    if written:
        log.info("the AI wrote first to %s people", written)
    return written


async def loop() -> None:
    """Started in the app's lifespan, cancelled at shutdown. Runs at once and then every
    REMINDER_TICK_MINUTES; a pass repeated after a restart sends nothing twice."""
    log.info("outreach loop started, every %s minutes", settings.reminder_tick_minutes)
    while True:
        try:
            await run_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - a loop that dies silently stops writing
            log.exception("outreach pass failed; continuing")
        await asyncio.sleep(settings.reminder_tick_minutes * 60)
