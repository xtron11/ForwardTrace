"""The first conversation: onboarding as a chat (brief, "Первый разговор").

Steps, kept in `conversations.state`:
    skill -> motivation -> finish -> baseline -> schedule -> done
`first_conversation_step` takes the person's message, saves what it says (skill, the
motivation quote, the finish line, "then -> now" pairs, the hour to write), and returns
the next question as ready segments. Called from `conversation._reply` before the normal
reply; the text is fixed strings from services/texts.py, the model only reads the
person's answer (`on_topic`, a short skill name, quotes, finish ideas).

The model never speaks to the person and never writes a quote the person sees: every
quote is checked with `verify.quote_supported` against the person's own message before
it is saved, and pair quotes reach the screen as facts from the database.

A step gets one softer retry when the answer is empty or off topic; after that the
conversation moves on with what it has (spec story 16).
"""

import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Conversation, Fact, Goal, Message, Pair, User
from . import memory, prompts, texts, verify
from .events import log_event
from .llm import LLMError, complete_json

log = logging.getLogger(__name__)

STEPS = ("skill", "motivation", "finish", "baseline", "schedule", "done")
DEFAULT_HOUR = 20
EVENING_HOUR = 21
TITLE_MAX = 120
OPTION_MAX = 60


@dataclass
class FirstReply:
    """What the assistant says next: text and quote segments (as stored in
    messages.content), the quick replies, and whether the conversation is complete."""

    text_segments: list[dict]
    quick_replies: list[str] = field(default_factory=list)
    done: bool = False
    used_fact_ids: list[str] = field(default_factory=list)


@dataclass
class _Ctx:
    db: AsyncSession
    user: User
    conversation: Conversation
    message: Message
    state: dict
    text: str

    @property
    def locale(self) -> str | None:
        return self.user.locale


# ------------------------------------------------------------------ small helpers


def meaningful(text: str) -> bool:
    """Something to read: at least one letter or digit (not "..." or "???")."""
    return any(ch.isalnum() for ch in text or "")


def _plain(locale: str | None, key: str, quick: list[str] | None = None, **kw) -> FirstReply:
    return FirstReply([{"type": "text", "text": texts.t(locale, key, **kw)}], quick or [])


def _options_of(key: str) -> set[str]:
    """One quick reply in every language, normalised: a button label comes back as text."""
    out = set()
    for table in (texts.RU, texts.EN):
        value = table[key]
        for item in [value] if isinstance(value, str) else value:
            out.add(verify.normalize(item))
    return out


def _is_option(text: str, key: str, index: int | None = None) -> bool:
    wanted = (
        {verify.normalize(table[key][index]) for table in (texts.RU, texts.EN)}
        if index is not None
        else _options_of(key)
    )
    return verify.normalize(text) in wanted


async def _ask(ctx: _Ctx, system: str, schema: dict) -> dict | None:
    """The step model's answer, or None when the model failed: a failure must not look
    like an off-topic answer (the person is not at fault)."""
    try:
        result = await complete_json(system, prompts.first_user_prompt(ctx.text), schema)
    except LLMError:
        log.exception("first conversation: model failed at step %s", ctx.state.get("step"))
        return None
    return result.data if isinstance(result.data, dict) else None


def _on_topic(ctx: _Ctx, data: dict | None) -> bool:
    if not meaningful(ctx.text):
        return False
    if data is None:  # the model could not say: take the person's word for it
        return True
    return bool(data.get("on_topic"))


async def _goal(ctx: _Ctx) -> Goal:
    goal = (
        await ctx.db.execute(
            select(Goal)
            .where(Goal.user_id == ctx.user.id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if goal is None:
        goal = Goal(
            id=uuid.uuid4(),
            user_id=ctx.user.id,
            title=ctx.user.skill or texts.t(ctx.locale, "first.skill_placeholder"),
            is_active=True,
            started_on=ctx.conversation.local_date,
        )
        ctx.db.add(goal)
        await ctx.db.flush()
    return goal


def _retry(ctx: _Ctx, key: str, quick: list[str] | None = None) -> FirstReply:
    ctx.state["retries"] = 1
    return _plain(ctx.locale, key, quick)


def _advance(ctx: _Ctx, step: str) -> None:
    ctx.state["step"] = step
    ctx.state["retries"] = 0


# ------------------------------------------------------------------ steps


async def _skill(ctx: _Ctx) -> FirstReply:
    data = await _ask(ctx, prompts.first_skill_system(ctx.locale), prompts.FIRST_SKILL_SCHEMA) \
        if meaningful(ctx.text) else None
    ok = _on_topic(ctx, data)
    if not ok and not ctx.state.get("retries"):
        return _retry(ctx, "first.retry.skill", texts.quick(ctx.locale, "first.skills"))

    if ok:
        title = str((data or {}).get("title") or "").strip() or ctx.text
    else:
        title = texts.t(ctx.locale, "first.skill_placeholder")
    title = title[:TITLE_MAX]
    ctx.user.skill = title
    goal = await _goal(ctx)
    goal.title = title
    _advance(ctx, "motivation")
    return _plain(ctx.locale, "first.ask_motivation")


def _finish_options(data: dict | None) -> list[str]:
    options: list[str] = []
    for item in (data or {}).get("finish_options") or []:
        if isinstance(item, str) and item.strip():
            item = item.strip()[:OPTION_MAX]
            if item not in options:
                options.append(item)
    return options[:4]


async def _motivation(ctx: _Ctx) -> FirstReply:
    data = await _ask(
        ctx,
        prompts.first_motivation_system(ctx.locale, skill=ctx.user.skill),
        prompts.FIRST_MOTIVATION_SCHEMA,
    ) if meaningful(ctx.text) else None
    if not _on_topic(ctx, data) and not ctx.state.get("retries"):
        return _retry(ctx, "first.retry.motivation")

    quote = str((data or {}).get("quote") or "").strip()
    saved = None
    if quote and verify.quote_supported(quote, verify.normalize(ctx.text)):
        goal = await _goal(ctx)
        goal.why_text = quote
        goal.why_message_id = ctx.message.id
        saved = quote
    options = _finish_options(data)
    ctx.state["finish_options"] = options
    _advance(ctx, "finish")
    quick = options + [texts.t(ctx.locale, "first.no_finish_option")]
    if saved:
        return _plain(ctx.locale, "first.ask_finish_quoted", quick, quote=saved)
    return _plain(ctx.locale, "first.ask_finish", quick)


async def _finish(ctx: _Ctx) -> FirstReply:
    if not meaningful(ctx.text) and not ctx.state.get("retries"):
        quick = list(ctx.state.get("finish_options") or []) + [
            texts.t(ctx.locale, "first.no_finish_option")
        ]
        return _retry(ctx, "first.retry.finish", quick)

    goal = await _goal(ctx)
    if not meaningful(ctx.text) or _is_option(ctx.text, "first.no_finish_option"):
        goal.finish_line = None
        goal.finish_set_on = None
        ctx.state["no_finish"] = True
    else:
        goal.finish_line = ctx.text[:300]
        goal.finish_set_on = ctx.conversation.local_date
        ctx.state["no_finish"] = False
    _advance(ctx, "baseline")
    key = "first.ask_baseline_no_finish" if ctx.state["no_finish"] else "first.ask_baseline"
    return _plain(ctx.locale, key)


async def _baseline(ctx: _Ctx) -> FirstReply:
    goal = await _goal(ctx)
    data = await _ask(
        ctx,
        prompts.first_baseline_system(
            ctx.locale, skill=ctx.user.skill, finish_line=goal.finish_line
        ),
        prompts.FIRST_BASELINE_SCHEMA,
    ) if meaningful(ctx.text) else None
    if not _on_topic(ctx, data) and not ctx.state.get("retries"):
        return _retry(ctx, "first.retry.baseline")

    data = data or {}
    if meaningful(ctx.text):
        goal.baseline_message_id = ctx.message.id
    source = verify.normalize(ctx.text)
    made: dict[str, Fact] = {}

    async def fact(kind: str, quote: str) -> Fact:
        key = verify.normalize(quote)
        if key in made:
            return made[key]
        row = Fact(
            id=uuid.uuid4(),
            user_id=ctx.user.id,
            message_id=ctx.message.id,
            origin="conversation",
            local_date=ctx.conversation.local_date,
            type=kind,
            text=quote[:300],
            quote=quote,
        )
        span = memory.align_quote(ctx.message.words, quote)
        if span is not None:
            row.audio_start_ms, row.audio_end_ms = span
        ctx.db.add(row)
        made[key] = row
        return row

    just_started = bool(data.get("just_started"))
    pairs: list[tuple[Fact, Fact]] = []
    seen: set[tuple[str, str]] = set()
    for item in [] if just_started else (data.get("pairs") or []):
        if len(pairs) >= settings.first_baseline_max_pairs:
            break
        item = item if isinstance(item, dict) else {}
        then = str(item.get("then_quote") or "").strip()
        now = str(item.get("now_quote") or "").strip()
        key = (verify.normalize(then), verify.normalize(now))
        if (
            key[0] == key[1]
            or key in seen
            or not verify.quote_supported(then, source)
            or not verify.quote_supported(now, source)
        ):
            continue
        seen.add(key)
        then_fact, now_fact = await fact("struggle", then), await fact("achievement", now)
        await ctx.db.flush()
        theme = str(item.get("theme") or "").strip()[:120] or then[:120]
        ctx.db.add(
            Pair(
                user_id=ctx.user.id,
                then_fact_id=then_fact.id,
                now_fact_id=now_fact.id,
                theme=theme,
                recalled=True,
                source="first_conversation",
            )
        )
        pairs.append((then_fact, now_fact))

    level = str(data.get("level_quote") or "").strip()
    if level and verify.quote_supported(level, source):
        await fact("level", level)
    await ctx.db.flush()

    ctx.state["just_started"] = just_started or not pairs
    _advance(ctx, "schedule")
    quick = texts.quick(ctx.locale, "first.schedule")
    if not pairs:
        reply = _plain(ctx.locale, "first.just_started", quick)
        return reply

    from .conversation import quote_segment  # lazy: conversation imports this module

    raw = texts.t(ctx.locale, "first.comparison", then="\x00T\x00", now="\x00N\x00")
    then_fact, now_fact = pairs[0]  # the first pair goes into the reply (spec 15a)
    segments: list[dict] = []
    for part in re.split(r"\x00([TN])\x00", raw):
        if part == "T":
            segments.append(quote_segment(then_fact, recalled=True))
        elif part == "N":
            segments.append(quote_segment(now_fact, recalled=True))
        elif part:
            segments.append({"type": "text", "text": part})
    return FirstReply(
        segments, quick, used_fact_ids=[str(then_fact.id), str(now_fact.id)]
    )


_HOUR = re.compile(
    r"(?<![\d:.])(\d{1,2})(?:[:.]\d{2})?(?!\d)\s*(am|pm|утра|вечера|дня|ночи)?", re.IGNORECASE
)


def parse_hour(text: str) -> int | None:
    """An hour 0-23 from "20:00", "8 pm", "в 8 вечера", "21"; None when there is none."""
    for match in _HOUR.finditer(text or ""):
        hour = int(match.group(1))
        if hour > 23:
            continue
        marker = (match.group(2) or "").lower()
        if marker in ("pm", "вечера", "дня") and hour < 12:
            hour += 12
        elif marker in ("am", "утра") and hour == 12:
            hour = 0
        elif marker == "ночи":
            hour = 0 if hour == 12 else hour + 12 if 9 <= hour <= 11 else hour
        return hour
    return None


async def _schedule(ctx: _Ctx) -> FirstReply:
    asking_end = bool(ctx.state.get("session_end"))
    hour: int | None = None
    if _is_option(ctx.text, "first.schedule", 1):  # "In the evening"
        hour = EVENING_HOUR
    elif not asking_end and _is_option(ctx.text, "first.schedule", 0):  # "After practice"
        ctx.state["session_end"] = True
        return _plain(
            ctx.locale, "first.ask_session_end", texts.quick(ctx.locale, "first.session_end_hours")
        )
    else:
        hour = parse_hour(ctx.text)

    if hour is None:
        if not ctx.state.get("retries"):
            quick = texts.quick(
                ctx.locale, "first.session_end_hours" if asking_end else "first.schedule"
            )
            return _retry(ctx, "first.retry.schedule", quick)
        hour = DEFAULT_HOUR

    ctx.user.reminder_hour = hour
    ctx.user.first_conversation_done = True
    ctx.state["session_end"] = False
    _advance(ctx, "done")
    await log_event(ctx.db, ctx.user, "first_conversation_done", {"reminder_hour": hour})
    reply = _plain(ctx.locale, "first.schedule_set", hour=hour)
    reply.done = True
    return reply


_STEPS = {
    "skill": _skill,
    "motivation": _motivation,
    "finish": _finish,
    "baseline": _baseline,
    "schedule": _schedule,
}


# ------------------------------------------------------------------ entry


def in_first_conversation(user: User, conversation: Conversation) -> bool:
    """True while this message belongs to the opening scenario."""
    state = conversation.state or {}
    return (
        conversation.kind == "first"
        and not user.first_conversation_done
        and state.get("step", "skill") in _STEPS
    )


async def first_conversation_step(
    db: AsyncSession, user: User, conversation: Conversation, message: Message
) -> FirstReply:
    """Save what the person's message says and return the next question. The caller
    stores the reply and commits."""
    from .conversation import FIRST_STATE  # lazy: conversation imports this module

    state = {**FIRST_STATE, **(conversation.state or {})}
    ctx = _Ctx(db, user, conversation, message, state, (message.content_raw or "").strip())
    reply = await _STEPS[state["step"]](ctx)
    conversation.state = dict(ctx.state)  # a new dict, so the change is noticed
    return reply
