"""The signed-in person's odds and ends: the fake door (POST /api/paywall/click), the
export (GET /api/me/export) and POST /api/outreach/{id}/opened."""

import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Response
from sqlalchemy import select

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import Conversation, Fact, Goal, Message, Outreach, Thread
from ..schemas import PaywallClickOut
from ..services.errors import NOT_FOUND, api_error
from ..services.events import log_event
from ..time_utils import local_today

router = APIRouter(prefix="/api", tags=["me"])


@router.post("/paywall/click", response_model=PaywallClickOut)
async def paywall_click(user: CurrentUser, db: Db) -> PaywallClickOut:
    """"Continue with Plus" in the beta: no payment, a month without the weekly limit
    (`plus_until` = the person's today + PLUS_BETA_DAYS). Plus is only that."""
    until = local_today(user.timezone) + timedelta(days=settings.plus_beta_days)
    user.plus_until = until
    await log_event(db, user, "paywall_clicked", {"plus_until": until.isoformat()})
    await db.commit()
    return PaywallClickOut(plus_until=until)


def _fact(f: Fact) -> dict:
    return {
        "id": str(f.id),
        "type": f.type,
        "text": f.text,
        "quote": f.quote,
        "local_date": f.local_date.isoformat(),
        "message_id": str(f.message_id) if f.message_id else None,
        "thread_id": str(f.thread_id) if f.thread_id else None,
        "flagged": f.flagged_at is not None,
    }


@router.get("/me/export")
async def export(user: CurrentUser, db: Db) -> Response:
    """Everything the person said and what was remembered from it, as one JSON file:
    conversations with messages, facts, threads and the goal. Only their own rows;
    recordings are not included (only whether a message had one)."""
    conversations = (
        await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.local_date)
        )
    ).scalars().all()
    messages = (
        await db.execute(
            select(Message)
            .where(Message.user_id == user.id)
            .order_by(Message.created_at, Message.id)
        )
    ).scalars().all()
    by_conversation: dict[uuid.UUID, list[dict]] = {}
    for m in messages:
        by_conversation.setdefault(m.conversation_id, []).append(
            {
                "id": str(m.id),
                "role": m.role,
                "source": m.source,
                "content_raw": m.content_raw,
                "content": m.content,
                "has_audio": m.audio_path is not None,
                "audio_seconds": m.audio_seconds,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    facts = (
        await db.execute(
            select(Fact).where(Fact.user_id == user.id).order_by(Fact.local_date, Fact.created_at)
        )
    ).scalars().all()
    threads = (
        await db.execute(
            select(Thread).where(Thread.user_id == user.id).order_by(Thread.opened_on)
        )
    ).scalars().all()
    goal = (
        await db.execute(
            select(Goal)
            .where(Goal.user_id == user.id, Goal.is_active.is_(True))
            .order_by(Goal.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    today = local_today(user.timezone)
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "account": {
            "email": user.email,
            "timezone": user.timezone,
            "locale": user.locale,
            "skill": user.skill,
        },
        "goal": (
            {
                "title": goal.title,
                "why_text": goal.why_text,
                "finish_line": goal.finish_line,
                "finish_set_on": goal.finish_set_on.isoformat() if goal.finish_set_on else None,
            }
            if goal
            else None
        ),
        "conversations": [
            {
                "local_date": c.local_date.isoformat(),
                "kind": c.kind,
                "started_by": c.started_by,
                "summary": c.summary,
                "messages": by_conversation.get(c.id, []),
            }
            for c in conversations
        ],
        "facts": [_fact(f) for f in facts],
        "threads": [
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status,
                "opened_on": t.opened_on.isoformat(),
                "closed_on": t.closed_on.isoformat() if t.closed_on else None,
            }
            for t in threads
        ],
    }
    body = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return Response(
        content=body.encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="forwardtrace-export-{today.isoformat()}.json"'
        },
    )


@router.post("/outreach/{outreach_id}/opened", status_code=204)
async def outreach_opened(outreach_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    """The app was opened from the AI's message (/today?o=<id>). Idempotent: the first
    call stamps `opened_at` and writes `outreach_opened`; later ones change nothing."""
    row = (
        await db.execute(
            select(Outreach).where(Outreach.id == outreach_id, Outreach.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise api_error(404, NOT_FOUND, "Message not found")
    if row.opened_at is None:
        row.opened_at = datetime.now(timezone.utc)
        await log_event(
            db,
            user,
            "outreach_opened",
            {"outreach_id": str(row.id), "topic": row.topic, "channel": row.channel},
        )
        await db.commit()
    return Response(status_code=204)
