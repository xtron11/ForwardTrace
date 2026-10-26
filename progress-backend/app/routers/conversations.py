"""The day's conversation and everything around it: the feed of days, one day, delete,
search, a message's recording, rating a reply, "this is not accurate", threads and the
week strip's calendar.

Errors are {"detail": {"code", "message"}} (services/errors.py). Everything is
filtered by the signed-in person: someone else's row is a 404, never a 403.
"""

import json
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, func, select, update
from starlette.background import BackgroundTask

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import Conversation, Fact, Goal, Message, Outreach, Pair, Thread
from ..schemas import (
    CalendarDayOut,
    ConversationOut,
    DayOut,
    MemoryOut,
    RatingIn,
    SearchHitOut,
    ThreadBrief,
    ThreadOut,
    ThreadUpdate,
)
from ..services import audio as audio_store
from ..services import conversation as convo
from ..services.events import log_event
from ..services.errors import BAD_RANGE, NOT_FOUND, REPLY_IN_PROGRESS, api_error
from ..time_utils import local_today

router = APIRouter(prefix="/api", tags=["conversations"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _not_found(what: str):
    return api_error(404, NOT_FOUND, f"{what} not found")


# ------------------------------------------------------------------ today


@router.get("/conversations/today", response_model=ConversationOut)
async def today(user: CurrentUser, db: Db) -> ConversationOut:
    conversation = await convo.get_or_create_today(db, user)
    return await convo.conversation_out(db, user, conversation)


async def _read_message(request: Request) -> tuple[str | None, UploadFile | None]:
    """JSON {text} or multipart with `audio` (or a `text` field)."""
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("audio")
        text = form.get("text")
        audio = upload if upload is not None and hasattr(upload, "read") else None
        return (text if isinstance(text, str) else None), audio
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None, None
    text = body.get("text") if isinstance(body, dict) else None
    return (text if isinstance(text, str) else None), None


@router.post("/conversations/today/messages")
async def send_message(request: Request, user: CurrentUser, db: Db) -> StreamingResponse:
    """The person's message; the answer is a text/event-stream (see the brief's
    "Формат потока"). Errors before the stream are ordinary JSON."""
    text, audio = await _read_message(request)
    prepared = await convo.prepare_message(db, user, text=text, audio=audio)
    return StreamingResponse(
        convo.stream_reply(prepared),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
        background=BackgroundTask(convo.release_if_unstarted, prepared),
    )


@router.post("/conversations/today/plateau")
async def plateau(user: CurrentUser, db: Db) -> StreamingResponse:
    """"I think I'm standing still" by the button: a text/event-stream with only the
    assistant's reply (no `user_message`). Not limited and not counted as a day; needs
    a confirmed email; 409 reply_in_progress while a reply is being written."""
    prepared = await convo.prepare_plateau(db, user)
    return StreamingResponse(
        convo.stream_reply(prepared, plateau=True),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
        background=BackgroundTask(convo.release_if_unstarted, prepared),
    )


# ------------------------------------------------------------------ days


@router.get("/conversations", response_model=list[DayOut])
async def feed(
    user: CurrentUser,
    db: Db,
    before: date | None = None,
    limit: int = Query(default=30, ge=1, le=100),
) -> list[DayOut]:
    """Days the person talked on, newest first."""
    count = (
        select(func.count(Message.id))
        .where(Message.conversation_id == Conversation.id)
        .correlate(Conversation)
        .scalar_subquery()
    )
    query = (
        select(Conversation, count)
        .where(Conversation.user_id == user.id, Conversation.counts_for_limit.is_(True))
        .order_by(Conversation.local_date.desc())
        .limit(limit)
    )
    if before is not None:
        query = query.where(Conversation.local_date < before)
    rows = (await db.execute(query)).all()
    if not rows:
        return []

    by_conversation: dict[uuid.UUID, list[ThreadBrief]] = {c.id: [] for c, _ in rows}
    pairs = (
        await db.execute(
            select(Message.conversation_id, Thread)
            .join(Fact, Fact.message_id == Message.id)
            .join(Thread, Thread.id == Fact.thread_id)
            .where(
                Message.conversation_id.in_(list(by_conversation)),
                Thread.user_id == user.id,
                Thread.status != "deleted",
            )
            .order_by(Thread.opened_on)
        )
    ).all()
    for conversation_id, thread in pairs:
        briefs = by_conversation[conversation_id]
        if all(b.id != thread.id for b in briefs):
            briefs.append(ThreadBrief(id=thread.id, title=thread.title, status=thread.status))

    return [
        DayOut(
            local_date=c.local_date,
            summary=c.summary,
            started_by=c.started_by,
            threads=by_conversation[c.id],
            message_count=n,
        )
        for c, n in rows
    ]


async def _own_day(db, user, local_date: date) -> Conversation:
    conversation = (
        await db.execute(
            select(Conversation).where(
                Conversation.user_id == user.id, Conversation.local_date == local_date
            )
        )
    ).scalar_one_or_none()
    if conversation is None:
        raise _not_found("Conversation")
    return conversation


@router.get("/conversations/{local_date}", response_model=ConversationOut)
async def one_day(local_date: date, user: CurrentUser, db: Db) -> ConversationOut:
    conversation = await _own_day(db, user, local_date)
    return await convo.conversation_out(db, user, conversation)


@router.delete("/conversations/{local_date}", status_code=204)
async def delete_day(local_date: date, user: CurrentUser, db: Db) -> Response:
    """The day goes with its messages, recordings and facts; threads and goals that
    pointed at them keep going without the link. Explicit, because SQLite (tests)
    does not enforce foreign keys."""
    conversation = await _own_day(db, user, local_date)
    if convo.is_busy(conversation.id):
        raise api_error(409, REPLY_IN_PROGRESS, "A reply is still being written.")

    messages = list(
        (await db.execute(select(Message).where(Message.conversation_id == conversation.id))).scalars()
    )
    message_ids = [m.id for m in messages]
    audio_paths = [m.audio_path for m in messages if m.audio_path]
    fact_ids = (
        list(
            (
                await db.execute(
                    select(Fact.id).where(Fact.user_id == user.id, Fact.message_id.in_(message_ids))
                )
            ).scalars()
        )
        if message_ids
        else []
    )

    if fact_ids:
        await db.execute(
            update(Thread)
            .where(Thread.user_id == user.id, Thread.opened_fact_id.in_(fact_ids))
            .values(opened_fact_id=None)
        )
        await db.execute(
            update(Thread)
            .where(Thread.user_id == user.id, Thread.closed_fact_id.in_(fact_ids))
            .values(closed_fact_id=None)
        )
        await db.execute(
            delete(Pair).where(
                Pair.user_id == user.id,
                Pair.then_fact_id.in_(fact_ids) | Pair.now_fact_id.in_(fact_ids),
            )
        )
        await db.execute(delete(Fact).where(Fact.id.in_(fact_ids)))
    if message_ids:
        await db.execute(
            update(Goal)
            .where(Goal.user_id == user.id, Goal.why_message_id.in_(message_ids))
            .values(why_message_id=None)
        )
        await db.execute(
            update(Goal)
            .where(Goal.user_id == user.id, Goal.baseline_message_id.in_(message_ids))
            .values(baseline_message_id=None)
        )
        await db.execute(
            update(Outreach)
            .where(Outreach.user_id == user.id, Outreach.message_id.in_(message_ids))
            .values(message_id=None)
        )
        await db.execute(delete(Message).where(Message.id.in_(message_ids)))
    await db.execute(
        update(Outreach)
        .where(Outreach.user_id == user.id, Outreach.conversation_id == conversation.id)
        .values(conversation_id=None)
    )
    await db.execute(delete(Conversation).where(Conversation.id == conversation.id))
    await db.commit()
    audio_store.delete_files(audio_paths)
    return Response(status_code=204)


# ------------------------------------------------------------------ search


def _snippet(text: str, query: str, width: int = 160) -> str:
    at = text.lower().find(query.lower())
    if at < 0 or len(text) <= width:
        return text[:width]
    start = max(0, at - width // 3)
    end = min(len(text), start + width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


@router.get("/search", response_model=list[SearchHitOut])
async def search(user: CurrentUser, db: Db, q: str = Query(default="", max_length=200)) -> list[SearchHitOut]:
    """The person's own messages containing `q`, newest first."""
    q = q.strip()
    if not q:
        return []
    await log_event(db, user, "search_used", {"length": len(q)})
    await db.commit()
    rows = (
        await db.execute(
            select(Message, Conversation.local_date)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.user_id == user.id,
                Message.role == "user",
                Message.content_raw.icontains(q, autoescape=True),
            )
            .order_by(Message.created_at.desc())
            .limit(50)
        )
    ).all()
    return [
        SearchHitOut(local_date=day, message_id=m.id, snippet=_snippet(m.content_raw, q))
        for m, day in rows
    ]


# ------------------------------------------------------------------ messages, facts, threads


async def _own_message(db, user, message_id: uuid.UUID) -> Message:
    message = await db.get(Message, message_id)
    if message is None or message.user_id != user.id:
        raise _not_found("Message")
    return message


@router.get("/messages/{message_id}/audio")
async def message_audio(message_id: uuid.UUID, user: CurrentUser, db: Db) -> FileResponse:
    message = await _own_message(db, user, message_id)
    if not message.has_audio:
        raise _not_found("Recording")
    return FileResponse(
        message.audio_path,
        media_type=message.audio_mime or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post("/messages/{message_id}/rating", status_code=204)
async def rate_reply(message_id: uuid.UUID, body: RatingIn, user: CurrentUser, db: Db) -> Response:
    message = await _own_message(db, user, message_id)
    if message.role != "assistant":
        raise _not_found("Reply")
    message.rating = body.rating
    await log_event(
        db, user, "reply_rated",
        {"message_id": str(message.id), "rating": body.rating,
         "with_quote": bool(message.used_fact_ids)},
    )
    await db.commit()
    return Response(status_code=204)


@router.post("/facts/{fact_id}/flag", status_code=204)
async def flag_fact(fact_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    """"This is not accurate": the fact is never offered to the model again."""
    fact = await db.get(Fact, fact_id)
    if fact is None or fact.user_id != user.id:
        raise _not_found("Fact")
    if fact.flagged_at is None:
        fact.flagged_at = datetime.now(timezone.utc)
        await log_event(db, user, "quote_flagged", {"fact_id": str(fact.id)})
        await db.commit()
    return Response(status_code=204)


@router.patch("/threads/{thread_id}", response_model=ThreadOut)
async def update_thread(
    thread_id: uuid.UUID, body: ThreadUpdate, user: CurrentUser, db: Db
) -> Thread:
    thread = await db.get(Thread, thread_id)
    if thread is None or thread.user_id != user.id:
        raise _not_found("Thread")
    if body.title is not None:
        thread.title = body.title.strip() or thread.title
    if body.status is not None:
        thread.status = body.status
        if body.status == "closed" and thread.closed_on is None:
            thread.closed_on = local_today(user.timezone)
            await log_event(db, user, "thread_closed", {"thread_id": str(thread.id), "by": "user"})
    await db.commit()
    await db.refresh(thread)
    return thread


# ------------------------------------------------------------------ memory


@router.get("/memory", response_model=MemoryOut)
async def memory_view(user: CurrentUser, db: Db) -> MemoryOut:
    """What ForwardTrace remembers: the goal, open and closed threads, the latest facts
    (flagged ones included, marked, so the person sees what they corrected)."""
    goal = (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user.id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    open_threads = (
        await db.execute(
            select(Thread)
            .where(Thread.user_id == user.id, Thread.status == "open")
            .order_by(
                func.coalesce(Thread.last_mentioned_on, Thread.opened_on).desc(),
                Thread.created_at.desc(),
            )
        )
    ).scalars().all()
    closed_threads = (
        await db.execute(
            select(Thread)
            .where(Thread.user_id == user.id, Thread.status == "closed")
            .order_by(Thread.closed_on.desc(), Thread.created_at.desc())
        )
    ).scalars().all()
    facts = (
        await db.execute(
            select(Fact)
            .where(Fact.user_id == user.id)
            .order_by(Fact.local_date.desc(), Fact.created_at.desc())
            .limit(settings.memory_recent_facts)
        )
    ).scalars().all()
    return MemoryOut(
        goal=goal,
        open_threads=open_threads,
        closed_threads=closed_threads,
        facts=facts,
    )


# ------------------------------------------------------------------ calendar


@router.get("/calendar", response_model=list[CalendarDayOut])
async def calendar(
    user: CurrentUser,
    db: Db,
    from_: date = Query(alias="from"),
    to: date = Query(),
) -> list[CalendarDayOut]:
    """Every day of [from, to] and whether the person talked on it (green)."""
    span = (to - from_).days + 1
    if span < 1 or span > settings.calendar_max_days:
        raise api_error(
            400, BAD_RANGE, f"The range must be 1 to {settings.calendar_max_days} days, from <= to."
        )
    active = set(
        (
            await db.execute(
                select(Conversation.local_date).where(
                    Conversation.user_id == user.id,
                    Conversation.counts_for_limit.is_(True),
                    Conversation.local_date >= from_,
                    Conversation.local_date <= to,
                )
            )
        ).scalars()
    )
    return [
        CalendarDayOut(local_date=day, active=day in active)
        for day in (from_ + timedelta(days=i) for i in range(span))
    ]
