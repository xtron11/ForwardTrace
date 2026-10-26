"""The day's conversation: one message in, one streamed reply out.

`prepare_message` runs every check that must answer before the stream starts (plain
JSON errors); `stream_reply` then yields Server-Sent Events. The reply itself is
produced by a separate asyncio task with its own database session, feeding a queue
the stream reads: a closed tab stops the reading, not the reply, which is finished
and saved all the same (spec story R002.1).

The model never writes a quote. It writes {{quote:<fact_id>}} for a fact it was
given; `ReplyRenderer` replaces that with the verified quote from the database and
silently drops any id it was not given.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal
from ..models import Conversation, Fact, Goal, Message, Outreach, Pair, Thread, User
from ..schemas import ConversationOut, MessageOut
from ..time_utils import local_today
from . import audio as audio_store
from . import costs, first_conversation, limits, memory, prompts, safety, texts
from .errors import (
    EMAIL_NOT_VERIFIED,
    EMPTY_TEXT,
    LLM_FAILED,
    NO_SPEECH,
    REPLY_IN_PROGRESS,
    STT_FAILED,
    TEXT_TOO_LONG,
    api_error,
)
from .events import log_event
from .llm import LLMError, stream_chat
from .stt import transcribe

log = logging.getLogger(__name__)

# Flattery and diagnosis, caught after the reply rather than merely forbidden in the
# prompt. Both languages (formal and informal Russian), because the prompt is English
# and the reply is not.
BANNED = (
    "молодец", "отлично", "так держать", "прекрасно", "здорово", "браво",
    "горжусь", "восхищ", "потрясающ", "невероятн", "ты справляешься",
    "вы справляетесь", "не сдавайся", "не сдавайтесь", "верь в себя", "верьте в себя",
    "у тебя всё получится", "у вас всё получится",
    "выгорание", "прокрастинац", "синдром самозванца", "боишься неудачи",
    "боитесь неудачи", "тревожность", "депресс", "перфекционизм",
    "well done", "great job", "keep it up", "keep going", "amazing", "incredible",
    "proud of you", "you're doing great", "you've got this", "don't give up",
    "burnout", "impostor syndrome", "afraid of failure", "procrastination",
)

# "Up to 3 pairs" (brief, "Кажется, я стою на месте"). A constant, not a setting:
# config.py is outside ticket 08; moving it there is a one-line follow-up.
PLATEAU_MAX_PAIRS = 3

FIRST_STATE = {"step": "skill", "retries": 0, "no_finish": False, "just_started": False}

# Conversations with a reply being written right now. In-process: one worker.
_busy: set[uuid.UUID] = set()
# Strong references, so a reply task outlives a closed stream without being collected.
_tasks: set[asyncio.Task] = set()


def _now() -> datetime:
    # Set in Python, not by the database: SQLite's now() has one-second resolution and
    # a message and its reply must still sort in the order they were written.
    return datetime.now(timezone.utc)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# ------------------------------------------------------------------ the day


async def _active_goal(db: AsyncSession, user_id: uuid.UUID) -> Goal | None:
    return (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user_id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _day(db: AsyncSession, user_id: uuid.UUID, day: date) -> Conversation | None:
    return (
        await db.execute(
            select(Conversation).where(
                Conversation.user_id == user_id, Conversation.local_date == day
            )
        )
    ).scalar_one_or_none()


async def get_or_create_today(db: AsyncSession, user: User) -> Conversation:
    """Today's conversation in the person's time zone, created on first touch.

    Someone who has not finished the first conversation gets `kind=first` again on a
    new day, continuing from the saved step (spec §1.6); with no conversation at all
    it starts over with the greeting.
    """
    today = local_today(user.timezone)
    existing = await _day(db, user.id, today)
    if existing is not None:
        return existing

    conversation = Conversation(
        user_id=user.id, local_date=today, kind="daily", started_by="user"
    )
    greeting = False
    if not user.first_conversation_done:
        conversation.kind = "first"
        previous = (
            await db.execute(
                select(Conversation)
                .where(Conversation.user_id == user.id, Conversation.kind == "first")
                .order_by(Conversation.local_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if previous is not None and previous.state:
            conversation.state = dict(previous.state)
        else:
            conversation.state = dict(FIRST_STATE)
            greeting = True
        conversation.started_by = "ai"

    db.add(conversation)
    try:
        await db.flush()
    except IntegrityError:
        # Two requests created the day at once; the other one won.
        await db.rollback()
        existing = await _day(db, user.id, today)
        if existing is None:
            raise
        return existing

    if greeting:
        text = texts.t(user.locale, "first.greeting")
        db.add(
            Message(
                conversation_id=conversation.id,
                user_id=user.id,
                role="assistant",
                source="text",
                content_raw=text,
                content=[{"type": "text", "text": text}],
                quick_replies=texts.quick(user.locale, "first.skills"),
                created_at=_now(),
            )
        )
    await db.commit()
    return conversation


async def messages_of(db: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    return list(
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at, Message.id)
            )
        ).scalars()
    )


async def conversation_out(
    db: AsyncSession, user: User, conversation: Conversation
) -> ConversationOut:
    messages = await messages_of(db, conversation.id)
    return ConversationOut(
        id=conversation.id,
        local_date=conversation.local_date,
        kind=conversation.kind,
        started_by=conversation.started_by,
        state=conversation.state,
        messages=[MessageOut.model_validate(m) for m in messages],
        limit=await limits.limit_status(db, user, local_today(user.timezone)),
    )


def is_busy(conversation_id: uuid.UUID) -> bool:
    return conversation_id in _busy


# ------------------------------------------------------------------ before the stream


@dataclass
class PreparedMessage:
    """Everything the reply task needs, by id: it opens its own session."""

    user_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    source: Literal["text", "voice"]
    text: str | None = None
    audio_path: str | None = None
    audio_mime: str | None = None
    started: bool = False
    # "I think I'm standing still" by the button: no message from the person, only a
    # reply; the day is not counted (spec §1.10).
    plateau_only: bool = False


async def prepare_message(
    db: AsyncSession, user: User, *, text: str | None, audio: UploadFile | None
) -> PreparedMessage:
    """Every check that answers with a plain JSON error, in the order of the brief.
    Raises HTTPException (services/errors.py codes)."""
    if settings.require_verified_email and not user.email_verified:
        raise api_error(403, EMAIL_NOT_VERIFIED, "Confirm your email address first.")

    if audio is None:
        text = (text or "").strip()
        if not text:
            raise api_error(422, EMPTY_TEXT, "The message is empty.")
        if len(text) > settings.max_text_chars:
            raise api_error(
                422, TEXT_TOO_LONG, f"The message is longer than {settings.max_text_chars} characters."
            )
    else:
        # The type is refused before anything is written or spent.
        audio_store.extension_for(audio.content_type)

    conversation = await get_or_create_today(db, user)
    if conversation.id in _busy:
        raise api_error(409, REPLY_IN_PROGRESS, "A reply is still being written.")
    await limits.ensure_can_message(db, user, conversation, conversation.local_date)

    message_id = uuid.uuid4()
    prepared = PreparedMessage(
        user_id=user.id,
        conversation_id=conversation.id,
        message_id=message_id,
        source="voice" if audio is not None else "text",
        text=text if audio is None else None,
    )
    if audio is not None:
        prepared.audio_path, prepared.audio_mime = await audio_store.save_message_audio(
            audio, user.id, message_id
        )
    if conversation.id in _busy:  # a second request got here while the file was written
        audio_store.delete_files([prepared.audio_path])
        raise api_error(409, REPLY_IN_PROGRESS, "A reply is still being written.")
    _busy.add(conversation.id)
    return prepared


async def prepare_plateau(db: AsyncSession, user: User) -> PreparedMessage:
    """The checks before a plateau reply by the button: a confirmed email and no reply
    already being written. No limit check - it is available to everyone (spec §1.10)."""
    if settings.require_verified_email and not user.email_verified:
        raise api_error(403, EMAIL_NOT_VERIFIED, "Confirm your email address first.")
    conversation = await get_or_create_today(db, user)
    if conversation.id in _busy:
        raise api_error(409, REPLY_IN_PROGRESS, "A reply is still being written.")
    _busy.add(conversation.id)
    return PreparedMessage(
        user_id=user.id,
        conversation_id=conversation.id,
        message_id=uuid.uuid4(),
        source="text",
        plateau_only=True,
    )


def release_if_unstarted(prepared: PreparedMessage) -> None:
    """For a stream that never ran (the client vanished before the first byte): free
    the conversation and drop the saved recording."""
    if not prepared.started:
        _busy.discard(prepared.conversation_id)
        audio_store.delete_files([prepared.audio_path])


# ------------------------------------------------------------------ rendering


_OPEN, _CLOSE = "{{", "}}"
_META = prompts.META_SEPARATOR
_PLACEHOLDER = re.compile(r"^\s*quote\s*:\s*([0-9a-fA-F-]{32,36})\s*$")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_MARKERS = (_OPEN, _META)


@dataclass(slots=True)
class RenderedReply:
    content_raw: str
    segments: list[dict]
    used_fact_ids: list[str]
    meta: dict


def quote_segment(fact: Fact, *, recalled: bool = False) -> dict:
    """A quote as stored in messages.content and sent as the `quote` event (spec §1.7)."""
    return {
        "type": "quote",
        "fact_id": str(fact.id),
        "quote": fact.quote,
        "local_date": fact.local_date.isoformat(),
        "recalled": recalled,
        "message_id": str(fact.message_id) if fact.message_id else None,
        "audio_start_ms": fact.audio_start_ms,
        "audio_end_ms": fact.audio_end_ms,
    }


def _held_suffix(text: str) -> int:
    """Length of the longest end of `text` that could be the start of a marker."""
    for size in range(min(len(text), len(_META) - 1), 0, -1):
        tail = text[-size:]
        if any(marker.startswith(tail) for marker in _MARKERS):
            return size
    return 0


class ReplyRenderer:
    """Turns the model's stream into `delta` and `quote` events.

    Text before `{{` streams as it comes; `{{ ... }}` is held until it closes and
    becomes a quote from `known`, or nothing. A `{{` that never closes is dropped with
    everything after it. Nothing after <<<META>>> is streamed: it is parsed by
    `finish()`, and a broken META means no quick replies and intent "normal".
    """

    def __init__(self, known: dict[str, Fact], recalled: set[str] | None = None):
        self.known = {str(k).lower(): v for k, v in known.items()}
        self.recalled = {str(r).lower() for r in (recalled or ())}
        self._buf = ""
        self._mode: Literal["text", "placeholder", "meta"] = "text"
        self._meta: list[str] = []
        self._raw: list[str] = []
        self._segments: list[dict] = []
        self._used: list[str] = []
        self._ws = ""  # trailing whitespace not streamed yet
        self._flushed = False

    def feed(self, chunk: str) -> list[tuple[str, dict]]:
        if self._mode == "meta":
            self._meta.append(chunk)
            return []
        self._buf += chunk
        return self._drain(final=False)

    def flush(self) -> list[tuple[str, dict]]:
        """The end of the stream: release held text, drop an unclosed placeholder."""
        if self._flushed:
            return []
        self._flushed = True
        if self._mode == "meta":
            return []
        return self._drain(final=True)

    def finish(self) -> RenderedReply:
        self.flush()
        segments = [s for s in self._segments if s["type"] != "text" or s["text"]]
        return RenderedReply(
            content_raw="".join(self._raw).strip(),
            segments=segments,
            used_fact_ids=list(self._used),
            meta=self._parse_meta(),
        )

    # -- internals

    def _put(self, text: str, events: list) -> None:
        events.append(("delta", {"text": text}))
        if self._segments and self._segments[-1]["type"] == "text":
            self._segments[-1]["text"] += text
        else:
            self._segments.append({"type": "text", "text": text})

    def _text(self, text: str, events: list) -> None:
        """Stream text. Whitespace at the very start is dropped; whitespace at the end
        waits for what follows, so a reply never ends (or meets a dropped
        placeholder) with a dangling space."""
        if not self._segments:
            text = text.lstrip()
            self._ws = ""
        text = self._ws + text
        core = text.rstrip()
        self._ws = text[len(core):]
        if core:
            self._put(core, events)

    def _before_quote(self, events: list) -> None:
        if self._ws and self._segments:
            self._put(self._ws, events)
        self._ws = ""

    def _to_meta(self, rest: str) -> None:
        self._mode = "meta"
        self._meta.append(rest)
        self._buf = ""

    def _drain(self, *, final: bool) -> list[tuple[str, dict]]:
        events: list[tuple[str, dict]] = []
        while True:
            buf = self._buf
            if self._mode == "text":
                at_open, at_meta = buf.find(_OPEN), buf.find(_META)
                if at_meta >= 0 and (at_open < 0 or at_meta < at_open):
                    before = buf[:at_meta]
                    self._raw.append(before)
                    self._text(before, events)
                    self._to_meta(buf[at_meta + len(_META):])
                    return events
                if at_open >= 0:
                    before = buf[:at_open]
                    self._raw.append(before)
                    self._text(before, events)
                    self._buf = buf[at_open:]
                    self._mode = "placeholder"
                    continue
                held = 0 if final else _held_suffix(buf)
                ready = buf[: len(buf) - held]
                self._raw.append(ready)
                self._text(ready, events)
                self._buf = buf[len(ready):]
                return events

            # placeholder: the buffer starts with "{{"
            at_close, at_meta = buf.find(_CLOSE, len(_OPEN)), buf.find(_META)
            if at_meta >= 0 and (at_close < 0 or at_meta < at_close):
                self._to_meta(buf[at_meta + len(_META):])  # cut off by META: dropped
                return events
            if at_close < 0:
                if final:
                    self._buf = ""  # never closed: dropped whole
                return events
            inner = buf[len(_OPEN):at_close]
            self._buf = buf[at_close + len(_CLOSE):]
            self._mode = "text"
            fact = self._lookup(inner)
            if fact is not None:
                fid = str(fact.id)
                segment = quote_segment(fact, recalled=fid in self.recalled)
                self._before_quote(events)
                self._segments.append(segment)
                events.append(("quote", {k: v for k, v in segment.items() if k != "type"}))
                self._raw.append(f"{{{{quote:{fid}}}}}")
                if fid not in self._used:
                    self._used.append(fid)

    def _lookup(self, inner: str) -> Fact | None:
        match = _PLACEHOLDER.match(inner)
        if not match:
            return None
        try:
            fid = str(uuid.UUID(match.group(1)))
        except ValueError:
            return None
        return self.known.get(fid)

    def _parse_meta(self) -> dict:
        default = {"quick_replies": [], "intent": "normal"}
        raw = _FENCE.sub("", "".join(self._meta).strip())
        if not raw:
            return default
        data = None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                try:
                    data = json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    data = None
        if not isinstance(data, dict):
            return default
        replies = data.get("quick_replies")
        cleaned: list[str] = []
        if isinstance(replies, list):
            for item in replies:
                if isinstance(item, str) and item.strip():
                    cleaned.append(item.strip()[:80])
        intent = data.get("intent")
        return {
            "quick_replies": cleaned[: settings.max_quick_replies],
            "intent": intent if intent in ("normal", "plateau") else "normal",
        }


# ------------------------------------------------------------------ rules


def check_reply_rules(text: str, user_words: int) -> list[str]:
    """Violations of the reply rules: "length" (over REPLY_MAX_WORDS, or
    REPLY_MAX_WORDS_LONG when the person wrote more than REPLY_LONG_INPUT_WORDS),
    "questions" (more than one "?"), "banned" (flattery or a diagnosis)."""
    violations = []
    limit = (
        settings.reply_max_words_long
        if user_words > settings.reply_long_input_words
        else settings.reply_max_words
    )
    if len(text.split()) > limit:
        violations.append("length")
    if text.count("?") > 1:
        violations.append("questions")
    lowered = text.lower()
    if any(phrase in lowered for phrase in BANNED):
        violations.append("banned")
    return violations


# ------------------------------------------------------------------ context


@dataclass(slots=True)
class ChatContext:
    messages: list[dict]
    known: dict[str, Fact]
    recalled: set[str] = field(default_factory=set)


async def _context_facts(db: AsyncSession, user_id: uuid.UUID, text: str, limit: int) -> list[Fact]:
    """Verified facts for the reply: closest to the message by meaning, else the latest
    by date (services/memory.py). Only facts without "this is not accurate"."""
    return await memory.relevant_facts(db, user_id, text, limit)


@dataclass(slots=True)
class PlateauEvidence:
    facts: list[Fact]
    pair_lines: list[str]
    closed_lines: list[str]
    conversations: int
    # Set when there are fewer than two pieces of evidence: the reply leans on the
    # starting point and says when there will be something to compare.
    days_to_compare: int | None


async def _plateau_evidence(db: AsyncSession, user: User, today: date) -> PlateauEvidence:
    """Brief, "Кажется, я стою на месте": up to 3 "then -> now" pairs with the biggest
    gap in time, closed threads and the number of conversations; with fewer than two
    of those, the starting point (the earliest `level` facts) as well."""
    rows = (
        await db.execute(
            select(Pair).where(Pair.user_id == user.id, Pair.hidden_at.is_(None))
        )
    ).scalars().all()
    fact_ids = {f for p in rows for f in (p.then_fact_id, p.now_fact_id)}
    by_id: dict[uuid.UUID, Fact] = {}
    if fact_ids:
        by_id = {
            f.id: f
            for f in (
                await db.execute(
                    select(Fact).where(
                        Fact.id.in_(fact_ids), Fact.user_id == user.id, Fact.flagged_at.is_(None)
                    )
                )
            ).scalars()
        }
    pairs = [
        (p, by_id[p.then_fact_id], by_id[p.now_fact_id])
        for p in rows
        if p.then_fact_id in by_id and p.now_fact_id in by_id
    ]
    pairs.sort(key=lambda t: (t[2].local_date - t[1].local_date).days, reverse=True)
    pairs = pairs[:PLATEAU_MAX_PAIRS]

    closed = list(
        (
            await db.execute(
                select(Thread)
                .where(Thread.user_id == user.id, Thread.status == "closed")
                .order_by(Thread.closed_on.desc(), Thread.created_at.desc())
                .limit(settings.context_threads)
            )
        ).scalars()
    )
    conversations = (
        await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.user_id == user.id, Conversation.counts_for_limit.is_(True)
            )
        )
    ).scalar_one()

    facts: list[Fact] = []
    for _, then, now in pairs:
        facts.extend([then, now])
    pair_lines = [
        f"[{then.id}] {then.local_date.isoformat()} -> [{now.id}] {now.local_date.isoformat()} "
        f"({(now.local_date - then.local_date).days} days apart): {pair.theme}"
        for pair, then, now in pairs
    ]
    closed_lines = [
        f"{t.title} (open {t.opened_on.isoformat()}, closed "
        f"{t.closed_on.isoformat() if t.closed_on else 'recently'})"
        for t in closed
    ]

    days_to_compare = None
    if len(pairs) + len(closed) < 2:
        start = list(
            (
                await db.execute(
                    select(Fact)
                    .where(Fact.user_id == user.id, Fact.flagged_at.is_(None), Fact.type == "level")
                    .order_by(Fact.local_date, Fact.created_at)
                    .limit(2)
                )
            ).scalars()
        )
        facts.extend(f for f in start if f not in facts)
        first_day = (
            await db.execute(
                select(func.min(Conversation.local_date)).where(
                    Conversation.user_id == user.id, Conversation.counts_for_limit.is_(True)
                )
            )
        ).scalar_one()
        since_start = (today - first_day).days if first_day else 0
        days_to_compare = (
            settings.pair_min_days - since_start
            if since_start < settings.pair_min_days
            else settings.pair_min_days
        )
        days_to_compare = max(days_to_compare, 1)
    return PlateauEvidence(facts, pair_lines, closed_lines, conversations, days_to_compare)


def _plain(message: Message) -> str:
    """What a stored message said, for the model's history."""
    if message.content_raw:
        return message.content_raw
    parts = []
    for segment in message.content or []:
        if segment.get("type") == "quote":
            parts.append(f"«{segment.get('quote', '')}»")
        else:
            parts.append(segment.get("text", ""))
    return "".join(parts)


async def build_context(
    db: AsyncSession,
    user: User,
    conversation: Conversation,
    text: str,
    *,
    mode: Literal["normal", "plateau"] = "normal",
    soft: bool = False,
) -> ChatContext:
    goal = await _active_goal(db, user.id)
    plateau_block: str | None = None
    if mode == "plateau":
        # Only the evidence, instead of the usual facts, open threads and past days.
        evidence = await _plateau_evidence(db, user, conversation.local_date)
        threads: list[Thread] = []
        facts = evidence.facts
        plateau_block = prompts.plateau_note(
            pairs=evidence.pair_lines,
            closed=evidence.closed_lines,
            conversations=evidence.conversations,
            days_to_compare=evidence.days_to_compare,
        )
    else:
        threads = list(
            (
                await db.execute(
                    select(Thread)
                    .where(Thread.user_id == user.id, Thread.status == "open")
                    .order_by(
                        func.coalesce(Thread.last_mentioned_on, Thread.opened_on).desc(),
                        Thread.created_at.desc(),
                    )
                    .limit(settings.context_threads)
                )
            ).scalars()
        )
        facts = await _context_facts(db, user.id, text, settings.context_facts)
    history = await messages_of(db, conversation.id)

    known: dict[str, Fact] = {str(f.id): f for f in facts}
    # Quotes already used today stay renderable when the history mentions them.
    used_today = {
        fid for m in history if m.role == "assistant" for fid in (m.used_fact_ids or [])
    } - set(known)
    if used_today:
        ids = []
        for fid in used_today:
            try:
                ids.append(uuid.UUID(fid))
            except ValueError:
                continue
        for fact in (
            await db.execute(
                select(Fact).where(
                    Fact.id.in_(ids), Fact.user_id == user.id, Fact.flagged_at.is_(None)
                )
            )
        ).scalars():
            known[str(fact.id)] = fact

    recalled: set[str] = set()
    if known:
        fact_ids = [f.id for f in known.values()]
        for then_id, now_id in (
            await db.execute(
                select(Pair.then_fact_id, Pair.now_fact_id).where(
                    Pair.user_id == user.id,
                    Pair.recalled.is_(True),
                    (Pair.then_fact_id.in_(fact_ids)) | (Pair.now_fact_id.in_(fact_ids)),
                )
            )
        ).all():
            recalled.update({str(then_id), str(now_id)})
        recalled &= set(known)

    days = [] if mode == "plateau" else list(
        (
            await db.execute(
                select(Conversation)
                .where(
                    Conversation.user_id == user.id,
                    Conversation.local_date < conversation.local_date,
                    Conversation.summary.is_not(None),
                )
                .order_by(Conversation.local_date.desc())
                .limit(settings.context_days)
            )
        ).scalars()
    )

    system = prompts.chat_system(
        user.locale,
        skill=user.skill or (goal.title if goal else None),
        anchor_quote=goal.why_text if goal else None,
        finish_line=goal.finish_line if goal else None,
        threads=[f"[{t.id}] {t.title} (open since {t.opened_on.isoformat()})" for t in threads],
        facts=[
            f"[{f.id}] {f.local_date.isoformat()} {f.type}: \"{f.quote}\""
            for f in known.values()
        ],
        days=[f"{c.local_date.isoformat()}: {c.summary}" for c in reversed(days)],
        max_words=settings.reply_max_words,
        soft=soft,
        plateau=mode == "plateau",
        plateau_block=plateau_block,
    )
    messages = [{"role": "system", "content": system}]
    for message in history:
        content = _plain(message)
        if content:
            messages.append(
                {"role": "user" if message.role == "user" else "assistant", "content": content}
            )
    return ChatContext(messages=messages, known=known, recalled=recalled)


# ------------------------------------------------------------------ the stream


def stream_reply(prepared: PreparedMessage, *, plateau: bool = False):
    """SSE lines for one message: user_message -> delta/quote... -> done, or error.

    Returns an async iterator. The work runs in its own task, so stopping the
    iteration (a closed connection) does not stop the reply from being saved.
    """
    prepared.started = True
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    task = asyncio.create_task(_run_reply(prepared, queue, plateau))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)

    async def read():
        while True:
            item = await queue.get()
            if item is None:
                return
            yield item

    return read()


async def _run_reply(prepared: PreparedMessage, queue: asyncio.Queue, plateau: bool) -> None:
    def emit(event: str, data: dict) -> None:
        queue.put_nowait(sse(event, data))

    try:
        async with SessionLocal() as db:
            await _reply(db, prepared, emit, plateau)
    except Exception:  # noqa: BLE001 - the stream must always end with an event
        log.exception("reply for conversation %s failed", prepared.conversation_id)
        emit("error", {"code": LLM_FAILED, "message": "The reply could not be written."})
    finally:
        _busy.discard(prepared.conversation_id)
        queue.put_nowait(None)


async def _reply(db: AsyncSession, prepared: PreparedMessage, emit, plateau: bool) -> None:
    user = await db.get(User, prepared.user_id)
    conversation = await db.get(Conversation, prepared.conversation_id)
    if user is None or conversation is None:
        audio_store.delete_files([prepared.audio_path])
        emit("error", {"code": LLM_FAILED, "message": "The conversation is gone."})
        return

    if prepared.plateau_only:
        await _plateau_reply(db, user, conversation, emit)
        return

    # 2. The person's message: voice is transcribed first, synchronously.
    message = Message(
        id=prepared.message_id,
        conversation_id=conversation.id,
        user_id=user.id,
        role="user",
        source=prepared.source,
    )
    with costs.track() as stt_usage:
        if prepared.source == "voice":
            try:
                result = await transcribe(prepared.audio_path, prepared.audio_mime, user.locale)
            except Exception:  # noqa: BLE001 - STTError or anything the provider threw
                log.exception("speech-to-text failed for message %s", prepared.message_id)
                audio_store.delete_files([prepared.audio_path])
                emit("error", {"code": STT_FAILED, "message": "Speech recognition failed."})
                return
            text = (result.text or "").strip()
            if len(text) < settings.no_speech_min_chars:
                audio_store.delete_files([prepared.audio_path])
                emit("error", {"code": NO_SPEECH, "message": "No speech detected in the recording."})
                return
            message.words = result.words or None
            message.audio_path = prepared.audio_path
            message.audio_mime = prepared.audio_mime
            message.audio_seconds = result.seconds
            message.detected_language = result.language
            message.stt_ms = result.elapsed_ms
        else:
            text = prepared.text or ""
    message.content_raw = text
    message.content = [{"type": "text", "text": text}]
    message.created_at = _now()
    costs.charge_message(message, stt_usage)
    db.add(message)

    # 3. The day counts; the AI's unanswered streak ends; today's outreach is answered.
    conversation.counts_for_limit = True
    user.outreach_unanswered = 0
    unanswered = (
        await db.execute(
            select(Outreach).where(
                Outreach.conversation_id == conversation.id, Outreach.replied_at.is_(None)
            )
        )
    ).scalars().all()
    for row in unanswered:
        row.replied_at = _now()
        await log_event(
            db, user, "outreach_replied",
            {"outreach_id": str(row.id), "topic": row.topic, "message_id": str(message.id)},
        )
    await log_event(
        db,
        user,
        "message_sent",
        {
            "message_id": str(message.id),
            "source": message.source,
            "words": len(text.split()),
            "kind": conversation.kind,
        },
    )
    await db.commit()
    emit(
        "user_message",
        {
            "id": str(message.id),
            "content": text,
            "source": message.source,
            "detected_language": message.detected_language,
        },
    )

    started = time.perf_counter()
    with costs.track() as usage:
        # 5. Safety comes before everything else, the first conversation included.
        checked = await safety.safety_check(text, user.locale)
        if checked.failed:
            await log_event(db, user, "safety_check_failed", {"message_id": str(message.id)})
        message.safety_level = checked.level
        conversation.safety_level = max(conversation.safety_level or 0, checked.level)
        if checked.level >= 2:
            await log_event(
                db,
                user,
                "safety_flag",
                {
                    "level": checked.level,
                    "message_id": str(message.id),
                    "conversation_id": str(conversation.id),
                },
            )
        await db.commit()

        # 4. The first conversation has its own scenario (services/first_conversation.py);
        #    at level 2-3 the step stays where it was and the safety reply answers
        #    (story R093.1).
        if checked.level < 2 and first_conversation.in_first_conversation(user, conversation):
            await _first_reply(db, user, conversation, message, emit, usage, started)
            return

        if checked.level >= 3:
            await _template_reply(db, user, conversation, emit, usage, started)
            return

        if checked.level == 2:
            history = await messages_of(db, conversation.id)
            context = ChatContext(messages=safety.level2_messages(user.locale, history), known={})
            await _stream_and_save(
                db, user, conversation, emit, context,
                usage=usage, started=started, user_words=len(text.split()), safety_reply=True,
            )
            return

        # 10. The previous reply's intent=plateau makes this one a plateau reply.
        previous = (
            await db.execute(
                select(Message.intent)
                .where(
                    Message.conversation_id == conversation.id,
                    Message.role == "assistant",
                    Message.id != message.id,
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        mode = "plateau" if plateau or previous == "plateau" else "normal"
        if plateau:
            await log_event(db, user, "plateau_triggered", {"conversation_id": str(conversation.id)})

        # 6. Context; level 1 makes it gentler.
        context = await build_context(
            db, user, conversation, text, mode=mode, soft=checked.level == 1
        )
        await db.commit()
        await _stream_and_save(
            db, user, conversation, emit, context,
            usage=usage, started=started, user_words=len(text.split()),
            suggest_help=checked.level == 1,
        )


async def _log_ai_reply(
    db: AsyncSession, user: User, answer: Message, *, kind: str = "model"
) -> None:
    await log_event(
        db,
        user,
        "ai_reply",
        {
            "message_id": str(answer.id),
            "kind": kind,  # model | first | safety_template
            "intent": answer.intent,
            "with_quote": bool(answer.used_fact_ids),
            "llm_ms": answer.llm_ms,
            "cost_usd": answer.cost_usd,
        },
    )


async def _plateau_reply(db: AsyncSession, user: User, conversation: Conversation, emit) -> None:
    """'I think I'm standing still' by the button: only the assistant's reply, and the
    day is not counted. A day that already reached safety level 2-3 keeps that
    protocol."""
    started = time.perf_counter()
    level = conversation.safety_level or 0
    with costs.track() as usage:
        if level >= 3:
            await _template_reply(db, user, conversation, emit, usage, started)
            return
        history = await messages_of(db, conversation.id)
        if level == 2:
            context = ChatContext(messages=safety.level2_messages(user.locale, history), known={})
            await _stream_and_save(
                db, user, conversation, emit, context,
                usage=usage, started=started, user_words=0, safety_reply=True,
            )
            return
        await log_event(db, user, "plateau_triggered", {"conversation_id": str(conversation.id)})
        last_said = next((m.content_raw for m in reversed(history) if m.role == "user"), "")
        context = await build_context(db, user, conversation, last_said or "", mode="plateau")
        await db.commit()
        await _stream_and_save(
            db, user, conversation, emit, context, usage=usage, started=started, user_words=0
        )


async def _template_reply(
    db: AsyncSession, user: User, conversation: Conversation, emit, usage, started: float
) -> None:
    """Level 3: the template with help contacts, never a model."""
    text = safety.level3_text(user)
    answer = Message(
        conversation_id=conversation.id,
        user_id=user.id,
        role="assistant",
        source="text",
        content_raw=text,
        content=[{"type": "text", "text": text}],
        quick_replies=[],
        used_fact_ids=[],
        intent="normal",
        model_name=None,
        llm_ms=int((time.perf_counter() - started) * 1000),
        created_at=_now(),
    )
    costs.charge_message(answer, usage)  # the safety check itself
    db.add(answer)
    await db.flush()
    await _log_ai_reply(db, user, answer, kind="safety_template")
    await db.commit()
    emit("delta", {"text": text})
    emit(
        "done",
        {"message_id": str(answer.id), "quick_replies": [], "used_fact_ids": [], "intent": "normal"},
    )


async def _stream_and_save(
    db: AsyncSession,
    user: User,
    conversation: Conversation,
    emit,
    context: ChatContext,
    *,
    usage,
    started: float,
    user_words: int,
    safety_reply: bool = False,
    suggest_help: bool = False,
) -> None:
    """Steps 7-9 and 11: stream the model's reply through the renderer, save it, check
    the rules, say `done`. A level-2 reply (`safety_reply`) has no quick replies and
    never turns the next reply into a plateau one."""
    renderer = ReplyRenderer(context.known, recalled=context.recalled)
    try:
        async for chunk in stream_chat(context.messages):
            for event, data in renderer.feed(chunk):
                emit(event, data)
    except LLMError:
        log.exception("chat model failed for conversation %s", conversation.id)
        emit("error", {"code": LLM_FAILED, "message": "The model failed to reply."})
        return
    for event, data in renderer.flush():
        emit(event, data)
    reply = renderer.finish()
    if not reply.segments:
        emit("error", {"code": LLM_FAILED, "message": "The model returned an empty reply."})
        return
    meta = {"quick_replies": [], "intent": "normal"} if safety_reply else reply.meta
    prose = "".join(s["text"] for s in reply.segments if s["type"] == "text")

    # Level 1 on many recent days: one soft line about a doctor or a psychologist,
    # at most once per SAFETY_HELP_COOLDOWN_DAYS.
    segments, content_raw = reply.segments, reply.content_raw
    if suggest_help and await safety.should_suggest_help(db, user, conversation.local_date):
        tail = "\n\n" + texts.t(user.locale, "safety.suggest_help")
        emit("delta", {"text": tail})
        if segments[-1]["type"] == "text":
            segments[-1] = {"type": "text", "text": segments[-1]["text"] + tail}
        else:
            segments.append({"type": "text", "text": tail})
        content_raw += tail
        await log_event(db, user, "safety_suggest_help", {"conversation_id": str(conversation.id)})

    # 9. Save the reply, then say it is done.
    answer = Message(
        conversation_id=conversation.id,
        user_id=user.id,
        role="assistant",
        source="text",
        content_raw=content_raw,
        content=segments,
        quick_replies=meta["quick_replies"],
        used_fact_ids=reply.used_fact_ids,
        intent=meta["intent"],
        model_name=settings.chat_model or settings.openai_model,
        llm_ms=int((time.perf_counter() - started) * 1000),
        created_at=_now(),
    )
    costs.charge_message(answer, usage)
    db.add(answer)
    await db.flush()
    await _log_ai_reply(db, user, answer, kind="safety" if safety_reply else "model")

    # 11. Rules are checked after the fact: a streamed reply cannot be taken back.
    violations = check_reply_rules(prose, user_words)
    if violations:
        await log_event(
            db,
            user,
            "reply_rule_violation",
            {"message_id": str(answer.id), "rules": violations, "words": len(prose.split())},
        )
    await db.commit()
    emit(
        "done",
        {
            "message_id": str(answer.id),
            "quick_replies": meta["quick_replies"],
            "used_fact_ids": reply.used_fact_ids,
            "intent": meta["intent"],
        },
    )


async def _first_reply(
    db: AsyncSession,
    user: User,
    conversation: Conversation,
    message: Message,
    emit,
    usage,
    started: float,
) -> None:
    """One step of the first conversation: the reply is ready text, sent as one `delta`
    per text piece (a single one unless a quote sits inside) and `quote` events. Runs
    inside the caller's cost tracking (`usage`), which already holds the safety check."""
    reply = await first_conversation.first_conversation_step(db, user, conversation, message)
    segments = reply.text_segments
    answer = Message(
        conversation_id=conversation.id,
        user_id=user.id,
        role="assistant",
        source="text",
        content_raw="".join(
            s["text"] if s["type"] == "text" else f"{{{{quote:{s['fact_id']}}}}}" for s in segments
        ),
        content=segments,
        quick_replies=reply.quick_replies[: settings.max_quick_replies],
        used_fact_ids=reply.used_fact_ids,
        intent="normal",
        model_name=settings.openai_model,
        llm_ms=int((time.perf_counter() - started) * 1000),
        created_at=_now(),
    )
    costs.charge_message(answer, usage)
    db.add(answer)
    await db.flush()
    await _log_ai_reply(db, user, answer, kind="first")
    await db.commit()
    for segment in segments:
        if segment["type"] == "text":
            emit("delta", {"text": segment["text"]})
        else:
            emit("quote", {k: v for k, v in segment.items() if k != "type"})
    emit(
        "done",
        {
            "message_id": str(answer.id),
            "quick_replies": answer.quick_replies,
            "used_fact_ids": reply.used_fact_ids,
            "intent": "normal",
        },
    )
