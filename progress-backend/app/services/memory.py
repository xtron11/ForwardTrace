"""Memory: what the person said, kept as verified facts, threads and "then -> now" pairs.

`extract_memory` reads one day's messages, asks the model for facts and thread changes,
and keeps only what code can check: a quote that appears in its own message
(services/verify.py), a message of this conversation, a thread id that was offered and
is still open. Everything runs in one transaction, so a restart halfway leaves nothing
behind, and a second run finds the same quotes and adds nothing (spec story 24).

Two loops drive it: one picks conversations quiet for MEMORY_IDLE_MINUTES, the other
closes each person's day at CLOSE_DAY_HOUR local time. Both take `now`, catch and log
their failures and go on; cancellation goes through.

Search by meaning: facts carry an embedding (EMBEDDING_MODEL), cosine similarity is
computed in Python over one person's facts. Without a model, or when the request fails,
facts are found by date.
"""

import asyncio
import logging
import math
import uuid
from collections.abc import Awaitable, Callable, Iterable
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal
from ..models import Conversation, Fact, Goal, Message, Pair, Thread, User
from ..time_utils import tz_of
from . import prompts, verify
from .events import log_event
from .llm import complete_json, embed

log = logging.getLogger(__name__)

FACT_TYPES = ("achievement", "struggle", "learned", "level")
CLOSING_TYPES = ("achievement", "learned")

# Conversations being extracted right now (one worker): the two loops never run the
# same one twice at once.
_running: set[uuid.UUID] = set()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ pure helpers


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    """Cosine similarity; 0 for empty, zero or differently sized vectors (a changed
    EMBEDDING_MODEL leaves old vectors of another size behind)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def align_quote(words: list[dict] | None, quote: str) -> tuple[int, int] | None:
    """Where the quote was said: (start_ms, end_ms) of its first and last word.

    Words and quote are compared after verify.normalize (case and punctuation do not
    matter). Only an exact run of words counts: a quote that passed the fuzzy check
    but is not word for word in the recording gets no range rather than a wrong one.
    """
    target = verify.normalize(quote).split()
    if not target or not words:
        return None
    tokens: list[tuple[str, int]] = []
    for index, word in enumerate(words):
        for token in verify.normalize(str(word.get("w") or "")).split():
            tokens.append((token, index))
    n = len(target)
    for start in range(len(tokens) - n + 1):
        if all(tokens[start + k][0] == target[k] for k in range(n)):
            first, last = words[tokens[start][1]], words[tokens[start + n - 1][1]]
            try:
                return round(float(first["start"]) * 1000), round(float(last["end"]) * 1000)
            except (KeyError, TypeError, ValueError):
                return None
    return None


def _embedding_text(fact: Fact) -> str:
    # The person's own words first: the query at reply time is their message.
    return f"{fact.quote}\n{fact.text}"


# ------------------------------------------------------------------ search


async def relevant_facts(
    db: AsyncSession, user_id: uuid.UUID, text: str, limit: int
) -> list[Fact]:
    """Facts for the reply to `text`: the closest by meaning, topped up with the latest
    by date. Only facts without "this is not accurate". Without EMBEDDING_MODEL, or
    when the embedding request fails, simply the latest by date."""
    if limit <= 0:
        return []
    base = select(Fact).where(Fact.user_id == user_id, Fact.flagged_at.is_(None))
    chosen: list[Fact] = []
    if settings.embedding_model and (text or "").strip():
        query: list[float] | None = None
        try:
            [query] = await embed([text])
        except Exception:  # noqa: BLE001 - search falls back to dates, the reply goes on
            log.warning("embedding the message failed; facts by date", exc_info=True)
        if query:
            candidates = [f for f in (await db.execute(base)).scalars() if f.embedding]
            candidates.sort(key=lambda f: cosine(query, f.embedding), reverse=True)
            chosen = candidates[:limit]
    if len(chosen) < limit:
        latest = base.order_by(Fact.local_date.desc(), Fact.created_at.desc())
        if chosen:
            latest = latest.where(Fact.id.not_in([f.id for f in chosen]))
        chosen += list((await db.execute(latest.limit(limit - len(chosen)))).scalars())
    return chosen


# ------------------------------------------------------------------ pairs


async def _theme(db: AsyncSession, user_id: uuid.UUID, then: Fact, now: Fact) -> str:
    """The card's theme: the struggle's thread title, or a few words from the model."""
    fallback = (then.text or then.quote)[:120]
    if then.thread_id is not None:
        thread = await db.get(Thread, then.thread_id)
        if thread is not None and thread.title:
            return thread.title[:120]
    user = await db.get(User, user_id)
    try:
        result = await complete_json(
            prompts.pair_theme_system(user.locale if user else None),
            prompts.pair_theme_user_prompt(then.quote, now.quote),
            prompts.PAIR_THEME_SCHEMA,
        )
        theme = str(result.data.get("theme") or "").strip()
    except Exception:  # noqa: BLE001 - a card with a plainer title beats no card
        log.warning("pair theme failed; using the fact's text", exc_info=True)
        theme = ""
    return (theme or fallback)[:120]


async def make_pairs(
    db: AsyncSession,
    user_id: uuid.UUID,
    new_facts: Iterable[Fact],
    closed_threads: Iterable[Thread],
) -> list[Pair]:
    """"Then -> now" cards for what this extraction found (the caller commits).

    1. A closed thread: its opening and closing facts, PAIR_MIN_DAYS or more apart.
    2. A new achievement with an embedding: the closest struggle at least PAIR_MIN_DAYS
       older, cosine >= PAIR_MIN_SIMILARITY, not in a card yet.
    At most one new card per fact; an existing card is never made twice.
    """
    existing = (
        await db.execute(select(Pair.then_fact_id, Pair.now_fact_id).where(Pair.user_id == user_id))
    ).all()
    pairs_seen = {(then_id, now_id) for then_id, now_id in existing}
    used_then = {then_id for then_id, _ in existing}
    used_now = {now_id for _, now_id in existing}
    created: list[Pair] = []

    for thread in closed_threads:
        if thread.user_id != user_id or not (thread.opened_fact_id and thread.closed_fact_id):
            continue
        then = await db.get(Fact, thread.opened_fact_id)
        now = await db.get(Fact, thread.closed_fact_id)
        if then is None or now is None or then.user_id != user_id or now.user_id != user_id:
            continue
        if then.flagged_at is not None or now.flagged_at is not None:
            continue
        if (now.local_date - then.local_date).days < settings.pair_min_days:
            continue
        if (then.id, now.id) in pairs_seen or now.id in used_now:
            continue
        pair = Pair(
            user_id=user_id,
            then_fact_id=then.id,
            now_fact_id=now.id,
            theme=(thread.title or then.text)[:120],
            source="thread_closed",
        )
        db.add(pair)
        created.append(pair)
        pairs_seen.add((then.id, now.id))
        used_then.add(then.id)
        used_now.add(now.id)

    achievements = [
        f for f in new_facts
        if f.type == "achievement" and f.embedding and f.flagged_at is None and f.id not in used_now
    ]
    if achievements:
        struggles = [
            f
            for f in (
                await db.execute(
                    select(Fact).where(
                        Fact.user_id == user_id,
                        Fact.type == "struggle",
                        Fact.flagged_at.is_(None),
                    )
                )
            ).scalars()
            if f.embedding
        ]
        for fact in achievements:
            cutoff = fact.local_date - timedelta(days=settings.pair_min_days)
            best, best_score = None, settings.pair_min_similarity
            for struggle in struggles:
                if struggle.id in used_then or struggle.local_date > cutoff:
                    continue
                score = cosine(fact.embedding, struggle.embedding)
                if score >= best_score:
                    best, best_score = struggle, score
            if best is None:
                continue
            pair = Pair(
                user_id=user_id,
                then_fact_id=best.id,
                now_fact_id=fact.id,
                theme=await _theme(db, user_id, best, fact),
                source="similarity",
            )
            db.add(pair)
            created.append(pair)
            used_then.add(best.id)
            used_now.add(fact.id)

    if created:
        await db.flush()
    return created


# ------------------------------------------------------------------ extraction


def _index(value) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


async def extract_memory(conversation_id: uuid.UUID) -> None:
    """Facts, threads, embeddings, the day's summary and pairs for one conversation.

    Own session, one commit. Safe to run again: quotes already kept for this
    conversation (including the first conversation's) are not added twice.
    """
    if conversation_id in _running:
        return
    _running.add(conversation_id)
    try:
        async with SessionLocal() as db:
            await _extract(db, conversation_id)
    finally:
        _running.discard(conversation_id)


async def _extract(db: AsyncSession, conversation_id: uuid.UUID) -> None:
    # Taken before reading: a message sent while the model thinks is newer than this
    # mark, so the loop comes back for it.
    started = _now()
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        return
    user = await db.get(User, conversation.user_id)
    if user is None:
        return
    messages = list(
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id, Message.role == "user")
                .order_by(Message.created_at)
            )
        ).scalars()
    )
    if not messages:
        conversation.memory_extracted_at = started
        await db.commit()
        return

    goal = (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user.id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    open_threads = list(
        (
            await db.execute(
                select(Thread)
                .where(Thread.user_id == user.id, Thread.status == "open")
                .order_by(Thread.opened_on, Thread.created_at)
            )
        ).scalars()
    )
    result = await complete_json(
        prompts.memory_system(
            user.locale,
            skill=user.skill or (goal.title if goal else None),
            finish_line=goal.finish_line if goal else None,
            threads=[f"[{t.id}] {t.title} (opened {t.opened_on.isoformat()})" for t in open_threads],
        ),
        prompts.memory_user_prompt([(str(m.id), m.content_raw or "") for m in messages]),
        prompts.MEMORY_SCHEMA,
    )
    data = result.data if isinstance(result.data, dict) else {}
    day = conversation.local_date

    # 1-2. Facts: verified against their own message, aligned to the recording.
    by_id = {str(m.id): m for m in messages}
    kept: dict[str, Fact] = {}
    for fact in (
        await db.execute(
            select(Fact).where(
                Fact.user_id == user.id, Fact.message_id.in_([m.id for m in messages])
            )
        )
    ).scalars():
        kept.setdefault(verify.normalize(fact.quote), fact)

    indexed: list[Fact | None] = []
    new_facts: list[Fact] = []
    dropped = 0
    for item in data.get("facts") or []:
        item = item if isinstance(item, dict) else {}
        message = by_id.get(str(item.get("message_id") or "").strip())
        kind = item.get("type")
        text = str(item.get("text") or "").strip()
        quote = str(item.get("quote") or "").strip()
        if (
            message is None
            or kind not in FACT_TYPES
            or not text
            or not verify.quote_supported(quote, verify.normalize(message.content_raw or ""))
        ):
            dropped += 1
            indexed.append(None)
            continue
        key = verify.normalize(quote)
        if key in kept:  # said and kept before: the same fact, not a new one
            indexed.append(kept[key])
            continue
        fact = Fact(
            id=uuid.uuid4(),
            user_id=user.id,
            message_id=message.id,
            origin="conversation",
            local_date=day,
            type=kind,
            text=text[:300],
            quote=quote,
        )
        span = align_quote(message.words, quote)
        if span is not None:
            fact.audio_start_ms, fact.audio_end_ms = span
        db.add(fact)
        kept[key] = fact
        indexed.append(fact)
        new_facts.append(fact)
    await db.flush()

    def fact_at(value) -> Fact | None:
        i = _index(value)
        return indexed[i] if i is not None and 0 <= i < len(indexed) else None

    # 3. Threads: open from a verified struggle; mention and close only offered ids.
    threads = data.get("threads") if isinstance(data.get("threads"), dict) else {}
    offered = {str(t.id): t for t in open_threads}
    opened: list[tuple[Thread, Fact]] = []
    for item in threads.get("open") or []:
        item = item if isinstance(item, dict) else {}
        fact = fact_at(item.get("fact_index"))
        title = str(item.get("title") or "").strip()
        if fact is None or fact.type != "struggle" or fact.thread_id is not None or not title:
            continue
        if any(f is fact for _, f in opened):
            continue
        thread = Thread(
            id=uuid.uuid4(),
            user_id=user.id,
            title=title[:200],
            status="open",
            opened_fact_id=fact.id,
            opened_on=day,
            last_mentioned_on=day,
        )
        db.add(thread)
        opened.append((thread, fact))
    if opened:
        await db.flush()  # the thread row exists before a fact points at it
        for thread, fact in opened:
            fact.thread_id = thread.id

    def mentioned(thread: Thread) -> None:
        if thread.last_mentioned_on is None or thread.last_mentioned_on < day:
            thread.last_mentioned_on = day

    for item in threads.get("mention") or []:
        item = item if isinstance(item, dict) else {}
        thread = offered.get(str(item.get("thread_id") or "").strip())
        fact = fact_at(item.get("fact_index"))
        if thread is None or fact is None or thread.status != "open":
            continue
        if fact.thread_id is None:
            fact.thread_id = thread.id
        mentioned(thread)

    closed: list[Thread] = []
    for item in threads.get("close") or []:
        item = item if isinstance(item, dict) else {}
        thread = offered.get(str(item.get("thread_id") or "").strip())
        fact = fact_at(item.get("fact_index"))
        if thread is None or fact is None or thread.status != "open":
            continue
        if fact.type not in CLOSING_TYPES:
            continue
        thread.status = "closed"
        thread.closed_fact_id = fact.id
        thread.closed_on = day
        mentioned(thread)
        if fact.thread_id is None:
            fact.thread_id = thread.id
        closed.append(thread)

    # 4. Embeddings for the new facts, one request; a failure costs only the search.
    if new_facts and settings.embedding_model:
        try:
            vectors = await embed([_embedding_text(f) for f in new_facts])
            for fact, vector in zip(new_facts, vectors):
                fact.embedding = vector
        except Exception:  # noqa: BLE001
            log.warning(
                "embeddings failed for conversation %s; facts kept without them",
                conversation.id, exc_info=True,
            )

    # 5. The day in one line, and the mark that this conversation is done.
    summary = str(data.get("day_summary") or "").strip()
    if summary:
        conversation.summary = summary[:200]
    if dropped:
        await log_event(
            db, user, "memory_dropped_facts",
            {"conversation_id": str(conversation.id), "dropped": dropped},
        )
    await db.flush()
    await make_pairs(db, user.id, new_facts, closed)
    conversation.memory_extracted_at = started
    await db.commit()
    log.info(
        "memory: conversation %s -> %s new facts, %s dropped, %s threads opened, %s closed",
        conversation.id, len(new_facts), dropped, len(opened), len(closed),
    )


# ------------------------------------------------------------------ loops


async def _pending(*, idle_before: datetime | None = None) -> list[tuple[uuid.UUID, date, str | None]]:
    """Conversations the person wrote in whose newest message is not extracted yet:
    [(id, local_date, timezone)], optionally only those quiet since `idle_before`."""
    last = func.max(Message.created_at)
    stmt = (
        select(Conversation.id, Conversation.local_date, User.timezone)
        .join(Message, Message.conversation_id == Conversation.id)
        .join(User, User.id == Conversation.user_id)
        .where(Message.role == "user", Conversation.counts_for_limit.is_(True))
        .group_by(Conversation.id, Conversation.local_date, Conversation.memory_extracted_at,
                  User.timezone)
        .having(
            or_(
                Conversation.memory_extracted_at.is_(None),
                Conversation.memory_extracted_at < last,
            )
        )
        .order_by(Conversation.local_date)
    )
    if idle_before is not None:
        stmt = stmt.having(last <= idle_before)
    async with SessionLocal() as db:
        return [tuple(row) for row in (await db.execute(stmt)).all()]


async def _extract_each(ids: Iterable[uuid.UUID]) -> int:
    done = 0
    for conversation_id in ids:
        try:
            await extract_memory(conversation_id)
            done += 1
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - one bad day must not stop the others
            log.exception("memory extraction failed for conversation %s", conversation_id)
    return done


async def extract_due(now: datetime | None = None) -> int:
    """Extract every conversation quiet for MEMORY_IDLE_MINUTES and not done since its
    last message. Returns how many were extracted."""
    now = now or _now()
    cutoff = now - timedelta(minutes=settings.memory_idle_minutes)
    return await _extract_each(cid for cid, _, _ in await _pending(idle_before=cutoff))


async def close_day(now: datetime | None = None) -> int:
    """Close each person's past days at CLOSE_DAY_HOUR their time: a day not extracted
    yet is extracted now, quiet or not. Returns how many were extracted."""
    now = now or _now()
    due = []
    for cid, local_date, tz_name in await _pending():
        zone = tz_of(tz_name)
        closes_at = datetime.combine(
            local_date + timedelta(days=1), time(settings.close_day_hour), tzinfo=zone
        )
        if now.astimezone(zone) >= closes_at:
            due.append(cid)
    return await _extract_each(due)


async def _loop(tick: Callable[[], Awaitable[int]], label: str) -> None:
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - a loop that dies silently stops remembering
            log.exception("%s pass failed; continuing", label)
        await asyncio.sleep(settings.memory_tick_minutes * 60)


async def memory_loop() -> None:
    """Started in the app's lifespan, cancelled at shutdown."""
    await _loop(lambda: extract_due(), "memory extraction")


async def close_day_loop() -> None:
    """Started in the app's lifespan, cancelled at shutdown."""
    await _loop(lambda: close_day(), "close day")
