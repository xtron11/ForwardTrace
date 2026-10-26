"""The Progress screen and the monthly summary.

`progress_for` assembles the screen from stored data, without a model: the goal, the
last facts about the person's level, "then -> now" cards, threads, and the newest
summary they have not opened yet. Hidden cards and cards built on a fact the person
marked "this is not accurate" never appear.

The monthly summary is built by `monthly_loop` once an hour. On the 1st of a month, once
the person's local time reaches CLOSE_DAY_HOUR, the month that ended is summarised:

  * code counts the numbers (days with a conversation, closed threads, new cards, level
    facts) and picks up to MONTHLY_MAX_PAIRS cards with the longest time between "then"
    and "now" and one open thread;
  * below MONTHLY_MIN_CONVERSATIONS conversations *and* MONTHLY_MIN_PAIRS new cards the
    summary is `thin` and no model is called;
  * otherwise the model writes three short fields (intro, open_struggle, next_step).
    A quote in them is a `{{quote:<fact_id>}}` placeholder; code keeps only ids it
    offered, and renders the quote from the database each time the summary is read, so
    a fact marked inaccurate later disappears from an old summary too;
  * a model error, or a percentage in the text, makes the row `failed`; the next pass
    on that same day tries again. A `done` or `thin` row is never rebuilt (unique
    `(user_id, month)`).

Once a summary is ready the person gets a push or a Telegram message
(`outreach.topic = "monthly"`). It is not a message in the conversation, so it does not
count as the AI writing first.
"""

import asyncio
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..config import settings
from ..db import SessionLocal
from ..models import Conversation, Fact, Goal, MonthlySummary, Outreach, Pair, Thread, User
from ..schemas import FactOut, MonthlyContentOut, MonthlySummaryOut, PairOut, ProgressOut, ThreadOut
from ..time_utils import tz_of
from . import outreach, prompts, texts
from .events import log_event
from .llm import LLMError, complete_json

log = logging.getLogger(__name__)

SHOWN_STATUSES = ("done", "thin")
_FIELDS = ("intro", "open_struggle", "next_step")
_ANY_PLACEHOLDER = re.compile(r"\{\{[^{}]*\}\}")
_ID_IN_PLACEHOLDER = re.compile(r"^\s*quote\s*:\s*([0-9a-fA-F-]{32,36})\s*$")
_PLACEHOLDER_IDS = re.compile(r"\{\{\s*quote\s*:\s*([0-9a-fA-F-]{32,36})\s*\}\}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ the screen


def month_key(month: date) -> str:
    return f"{month.year:04d}-{month.month:02d}"


async def _active_goal(db: AsyncSession, user_id: uuid.UUID) -> Goal | None:
    return (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user_id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _visible_pairs(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    ids: list[uuid.UUID] | None = None,
    between: tuple[date, date] | None = None,
) -> list[tuple[Pair, Fact, Fact]]:
    """Cards the person may see, newest first (by the date of the "now" fact)."""
    then, now = aliased(Fact), aliased(Fact)
    stmt = (
        select(Pair, then, now)
        .join(then, Pair.then_fact_id == then.id)
        .join(now, Pair.now_fact_id == now.id)
        .where(
            Pair.user_id == user_id,
            Pair.hidden_at.is_(None),
            then.flagged_at.is_(None),
            now.flagged_at.is_(None),
        )
        .order_by(now.local_date.desc(), Pair.created_at.desc())
    )
    if ids is not None:
        stmt = stmt.where(Pair.id.in_(ids))
    if between is not None:
        stmt = stmt.where(now.local_date >= between[0], now.local_date <= between[1])
    return [tuple(row) for row in (await db.execute(stmt)).all()]


def _pair_out(pair: Pair, then: Fact, now: Fact) -> PairOut:
    return PairOut(
        id=pair.id,
        theme=pair.theme,
        recalled=pair.recalled,
        source=pair.source,
        then=FactOut.model_validate(then),
        now=FactOut.model_validate(now),
    )


async def _threads(db: AsyncSession, user_id: uuid.UUID, status: str) -> list[Thread]:
    order = (
        (func.coalesce(Thread.last_mentioned_on, Thread.opened_on).desc(), Thread.created_at.desc())
        if status == "open"
        else (Thread.closed_on.desc(), Thread.created_at.desc())
    )
    return list(
        (
            await db.execute(
                select(Thread).where(Thread.user_id == user_id, Thread.status == status).order_by(*order)
            )
        ).scalars()
    )


async def progress_for(db: AsyncSession, user: User) -> ProgressOut:
    """Everything the Progress screen shows, from stored data only."""
    goal = await _active_goal(db, user.id)
    level_facts = list(
        (
            await db.execute(
                select(Fact)
                .where(Fact.user_id == user.id, Fact.type == "level", Fact.flagged_at.is_(None))
                .order_by(Fact.local_date.desc(), Fact.created_at.desc())
                .limit(settings.level_facts_shown)
            )
        ).scalars()
    )
    pairs = [_pair_out(*row) for row in await _visible_pairs(db, user.id)]
    unseen = (
        await db.execute(
            select(MonthlySummary)
            .where(
                MonthlySummary.user_id == user.id,
                MonthlySummary.status.in_(SHOWN_STATUSES),
                MonthlySummary.viewed_at.is_(None),
            )
            .order_by(MonthlySummary.month.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return ProgressOut(
        goal=goal,
        level_facts=[FactOut.model_validate(f) for f in level_facts],
        pairs=pairs,
        open_threads=[ThreadOut.model_validate(t) for t in await _threads(db, user.id, "open")],
        closed_threads=[ThreadOut.model_validate(t) for t in await _threads(db, user.id, "closed")],
        monthly=await monthly_out(db, user, unseen) if unseen is not None else None,
    )


# ------------------------------------------------------------------ reading a summary


async def _render_fields(db: AsyncSession, user_id: uuid.UUID, content: dict) -> dict[str, list[dict]]:
    """The stored text with placeholders -> segments. A quote is filled in from the
    database; one whose fact is gone, flagged or not this person's is dropped."""
    from .conversation import ReplyRenderer

    wanted: set[str] = set()
    for name in _FIELDS:
        wanted.update(m.lower() for m in _PLACEHOLDER_IDS.findall(content.get(name) or ""))
    known: dict[str, Fact] = {}
    if wanted:
        ids = []
        for raw in wanted:
            try:
                ids.append(uuid.UUID(raw))
            except ValueError:
                continue
        facts = (
            await db.execute(
                select(Fact).where(
                    Fact.id.in_(ids), Fact.user_id == user_id, Fact.flagged_at.is_(None)
                )
            )
        ).scalars()
        known = {str(f.id): f for f in facts}
    rendered = {}
    for name in _FIELDS:
        renderer = ReplyRenderer(known)
        renderer.feed(content.get(name) or "")
        rendered[name] = renderer.finish().segments
    return rendered


async def monthly_out(db: AsyncSession, user: User, row: MonthlySummary) -> MonthlySummaryOut:
    """The summary as the API shows it. `stats` carries the code-counted numbers plus the
    cards (`pairs`), the threads closed that month (`closed`) and the motivation quote
    (`why_text`), resolved now so hidden or inaccurate things are left out."""
    stored = dict(row.stats or {})
    pair_ids = [uuid.UUID(i) for i in stored.pop("pair_ids", [])]
    thread_ids = [uuid.UUID(i) for i in stored.pop("closed_thread_ids", [])]
    cards = {p.id: (p, t, n) for p, t, n in await _visible_pairs(db, user.id, ids=pair_ids)}
    threads = {}
    if thread_ids:
        threads = {
            t.id: t
            for t in (
                await db.execute(
                    select(Thread).where(
                        Thread.id.in_(thread_ids), Thread.user_id == user.id, Thread.status == "closed"
                    )
                )
            ).scalars()
        }
    goal = await _active_goal(db, user.id)
    stats = {
        **stored,
        "pairs": [_pair_out(*cards[i]).model_dump(mode="json") for i in pair_ids if i in cards],
        "closed": [
            ThreadOut.model_validate(threads[i]).model_dump(mode="json")
            for i in thread_ids
            if i in threads
        ],
        "why_text": goal.why_text if goal is not None else None,
    }
    content = None
    if row.content:
        content = MonthlyContentOut(**await _render_fields(db, user.id, row.content))
    return MonthlySummaryOut(
        month=month_key(row.month),
        status=row.status,
        stats=stats,
        content=content,
        viewed_at=row.viewed_at,
    )


# ------------------------------------------------------------------ building a summary


def _clean(raw: object, offered: set[str]) -> str:
    """The model's text with every placeholder for a fact it was not given removed."""
    text = raw if isinstance(raw, str) else ""

    def keep(match: re.Match) -> str:
        found = _ID_IN_PLACEHOLDER.match(match.group(0)[2:-2])
        if found:
            try:
                fid = str(uuid.UUID(found.group(1)))
            except ValueError:
                return ""
            if fid in offered:
                return f"<<keep:{fid}>>"
        return ""

    text = _ANY_PLACEHOLDER.sub(keep, text)
    # Stray braces are not text anyone should read; kept placeholders are restored after.
    text = text.replace("{{", "").replace("}}", "")
    text = re.sub(r"<<keep:([0-9a-f-]{36})>>", lambda m: "{{quote:" + m.group(1) + "}}", text)
    return re.sub(r" {2,}", " ", text).strip()


def _fact_line(fact: Fact) -> str:
    return f'[{fact.id}] {fact.local_date.isoformat()} {fact.type}: "{fact.quote}"'


async def _write(
    user: User, month: date, stats: dict, cards: list[tuple[Pair, Fact, Fact]],
    thread: Thread | None, thread_facts: list[Fact], goal: Goal | None,
) -> dict[str, str] | None:
    """Ask the model for the three fields. None when the call fails or the text breaks a
    rule (percentages and scores are never allowed)."""
    facts: dict[str, Fact] = {}
    for _, then, now in cards:
        facts[str(then.id)], facts[str(now.id)] = then, now
    for fact in thread_facts:
        facts[str(fact.id)] = fact
    counted = (
        f"days with a conversation: {stats['days']}; difficulties closed: {stats['closed_threads']}; "
        f"new before-and-after cards: {stats['new_pairs']}; level facts: {stats['level_facts']}"
    )
    system = prompts.monthly_system(
        user.locale,
        skill=user.skill or (goal.title if goal else None),
        finish_line=goal.finish_line if goal else None,
        month=month_key(month),
        stats=counted,
        pairs=[
            f'{pair.theme}: then [{then.id}] "{then.quote}" ({then.local_date}) -> '
            f'now [{now.id}] "{now.quote}" ({now.local_date})'
            for pair, then, now in cards
        ],
        thread=thread.title if thread is not None else None,
        facts=[_fact_line(f) for f in facts.values()],
    )
    try:
        result = await complete_json(system, prompts.monthly_user_prompt(month_key(month)), prompts.MONTHLY_SCHEMA)
    except LLMError:
        log.warning("monthly summary: the model failed for %s", user.id)
        return None
    data = result.data if isinstance(result.data, dict) else {}
    offered = set(facts)
    written = {name: _clean(data.get(name), offered) for name in _FIELDS}
    if thread is None:
        written["open_struggle"] = ""
    if not written["intro"] or not written["next_step"]:
        log.warning("monthly summary: the model left a field empty for %s", user.id)
        return None
    if any("%" in (data.get(name) or "") for name in _FIELDS if isinstance(data.get(name), str)):
        log.warning("monthly summary: percentages in the text for %s", user.id)
        return None
    return written


async def _gather(db: AsyncSession, user: User, month: date) -> dict:
    end = (month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    days = await db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(
            Conversation.user_id == user.id,
            Conversation.counts_for_limit.is_(True),
            Conversation.local_date >= month,
            Conversation.local_date <= end,
        )
    )
    closed = list(
        (
            await db.execute(
                select(Thread)
                .where(
                    Thread.user_id == user.id,
                    Thread.status == "closed",
                    Thread.closed_on >= month,
                    Thread.closed_on <= end,
                )
                .order_by(Thread.closed_on)
            )
        ).scalars()
    )
    level_facts = await db.scalar(
        select(func.count())
        .select_from(Fact)
        .where(
            Fact.user_id == user.id,
            Fact.type == "level",
            Fact.flagged_at.is_(None),
            Fact.local_date >= month,
            Fact.local_date <= end,
        )
    )
    in_month = await _visible_pairs(db, user.id, between=(month, end))
    # The longest time between "then" and "now" first.
    ranked = sorted(in_month, key=lambda row: (row[2].local_date - row[1].local_date).days, reverse=True)
    return {
        "days": days or 0,
        "closed": closed,
        "level_facts": level_facts or 0,
        "new_pairs": len(in_month),
        "cards": ranked[: settings.monthly_max_pairs],
    }


async def _notify(db: AsyncSession, user: User, month: date) -> None:
    """"Summary for {month} is ready" by push or Telegram. A person with no channel gets
    nothing; the summary waits on the Progress screen."""
    if not (user.reminders_on and user.outreach_channel != "none" and user.first_conversation_done):
        return
    moment = _now()
    row = Outreach(
        user_id=user.id,
        topic="monthly",
        channel=user.outreach_channel,
        sent_at=moment,
        delivered=False,
    )
    db.add(row)
    # Committed before sending: a crash while sending cannot send it twice.
    await db.commit()
    text = texts.t(user.locale, "monthly.ready", month=texts.month_name(user.locale, month.month))
    row.delivered = await outreach.deliver(db, user, row, text)
    await log_event(
        db, user, "outreach_sent",
        {"outreach_id": str(row.id), "topic": "monthly", "delivered": row.delivered, "template": True},
    )
    await db.commit()


async def build_monthly(user_id: uuid.UUID, month: date) -> MonthlySummary | None:
    """Build (or retry) the summary of `month` (its first day) for one person.

    None when the person did not talk that month. A `done` or `thin` summary is returned
    as it is; a `failed` one is tried again. Own session, safe to repeat."""
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or user.deleted_at is not None:
            return None
        existing = (
            await db.execute(
                select(MonthlySummary).where(
                    MonthlySummary.user_id == user_id, MonthlySummary.month == month
                )
            )
        ).scalar_one_or_none()
        if existing is not None and existing.status != "failed":
            return existing

        found = await _gather(db, user, month)
        if found["days"] == 0:
            return None
        cards = found["cards"]
        stats = {
            "days": found["days"],
            "conversations": found["days"],
            "closed_threads": len(found["closed"]),
            "new_pairs": found["new_pairs"],
            "level_facts": found["level_facts"],
            "pair_ids": [str(pair.id) for pair, _, _ in cards],
            "closed_thread_ids": [str(t.id) for t in found["closed"]],
        }

        thin = (
            found["days"] < settings.monthly_min_conversations
            and found["new_pairs"] < settings.monthly_min_pairs
        )
        content = None
        if thin:
            status = "thin"
        else:
            goal = await _active_goal(db, user_id)
            thread = (await _threads(db, user_id, "open") or [None])[0]
            thread_facts: list[Fact] = []
            if thread is not None:
                thread_facts = list(
                    (
                        await db.execute(
                            select(Fact)
                            .where(Fact.thread_id == thread.id, Fact.flagged_at.is_(None))
                            .order_by(Fact.local_date.desc(), Fact.created_at.desc())
                            .limit(2)
                        )
                    ).scalars()
                )
            content = await _write(user, month, stats, cards, thread, thread_facts, goal)
            status = "done" if content is not None else "failed"

        if existing is None:
            row = MonthlySummary(user_id=user_id, month=month, status=status, stats=stats, content=content)
            db.add(row)
        else:
            row = existing
            row.status, row.stats, row.content = status, stats, content
        try:
            await db.commit()
        except IntegrityError:
            # Another worker built it a moment ago.
            await db.rollback()
            return (
                await db.execute(
                    select(MonthlySummary).where(
                        MonthlySummary.user_id == user_id, MonthlySummary.month == month
                    )
                )
            ).scalar_one_or_none()

        if status in SHOWN_STATUSES:
            try:
                await _notify(db, user, month)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - the summary is saved; the notice is a courtesy
                log.exception("monthly summary: notification to %s failed", user_id)
        return row


# ------------------------------------------------------------------ the loop


async def monthly_once(now: datetime | None = None) -> int:
    """One pass. For each person whose local date is the 1st and whose local hour has
    reached CLOSE_DAY_HOUR, build the summary of the month that just ended unless it is
    already done. Returns how many summaries were completed (done or thin)."""
    moment = now or _now()
    async with SessionLocal() as db:
        people = (
            await db.execute(
                select(User.id, User.timezone).where(
                    User.is_active.is_(True), User.deleted_at.is_(None)
                )
            )
        ).all()
    built = 0
    for user_id, tz_name in people:
        local = moment.astimezone(tz_of(tz_name))
        if local.day != 1 or local.hour < settings.close_day_hour:
            continue
        month = (local.date() - timedelta(days=1)).replace(day=1)
        try:
            async with SessionLocal() as db:
                status = await db.scalar(
                    select(MonthlySummary.status).where(
                        MonthlySummary.user_id == user_id, MonthlySummary.month == month
                    )
                )
            if status in SHOWN_STATUSES:
                continue
            row = await build_monthly(user_id, month)
            if row is not None and row.status in SHOWN_STATUSES:
                built += 1
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - one person must not stop the others
            log.exception("monthly summary for %s failed", user_id)
    if built:
        log.info("built %s monthly summaries", built)
    return built


async def monthly_loop() -> None:
    """Started in the app's lifespan, cancelled at shutdown. State is in the database,
    so a restart repeats nothing."""
    log.info("monthly summary loop started, every %s minutes", settings.monthly_tick_minutes)
    while True:
        try:
            await monthly_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - a loop that dies silently stops summarising
            log.exception("monthly summary pass failed; continuing")
        await asyncio.sleep(settings.monthly_tick_minutes * 60)
