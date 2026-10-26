"""The signed-in person's odds and ends. Ticket 07: POST /api/outreach/{id}/opened.
(/api/paywall/click and /api/me/export come with ticket 08.)"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from sqlalchemy import select

from ..deps import CurrentUser, Db
from ..models import Outreach
from ..services.errors import NOT_FOUND, api_error
from ..services.events import log_event

router = APIRouter(prefix="/api", tags=["me"])


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
