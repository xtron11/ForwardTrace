"""Admin surface: the experiment's numbers as JSON and the client telemetry endpoint."""

import uuid

from fastapi import APIRouter, HTTPException

from ..deps import AdminUser, CurrentUser, Db
from ..schemas import EventIn
from ..services import adminstats
from ..services.events import log_event

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/events", status_code=201)
async def client_event(payload: EventIn, user: CurrentUser, db: Db) -> dict:
    """Client-side research telemetry (quote_opened, feed_opened, ...). The server adds
    day_number, language and channel, overriding whatever the client sent for them."""
    await log_event(db, user, payload.type, payload.payload)
    await db.commit()
    return {"ok": True}


@router.get("/admin/overview")
async def overview(admin: AdminUser, db: Db) -> dict:
    """One glance at whether the experiment is alive: retention by cohort, replies to the
    AI's first message, "helped" with and without a quotation, inaccurate quotations,
    safety-flagged conversations, cost per conversation."""
    return await adminstats.overview(db)


@router.get("/admin/conversations/{conversation_id}")
async def admin_conversation(conversation_id: uuid.UUID, admin: AdminUser, db: Db) -> dict:
    """One conversation as it was said, for reading by hand."""
    detail = await adminstats.conversation_detail(db, conversation_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return detail
