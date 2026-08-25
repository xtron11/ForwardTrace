"""Push subscription management."""

import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import PushSubscription
from ..services import push as push_service
from ..services.reminders import MESSAGES

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(max_length=255)
    auth: str = Field(max_length=255)


class SubscribeIn(BaseModel):
    endpoint: str = Field(max_length=2000)
    keys: SubscriptionKeys


class ReminderSettingsIn(BaseModel):
    reminders_on: bool | None = None
    reminder_hour: int | None = Field(default=None, ge=0, le=23)


@router.get("/key")
async def public_key() -> dict:
    """The browser needs this to create a subscription."""
    return {
        "public_key": settings.vapid_public_key,
        "enabled": bool(settings.vapid_public_key and settings.vapid_private_key),
    }


@router.post("/subscribe", status_code=201)
async def subscribe(
    payload: SubscribeIn, request: Request, user: CurrentUser, db: Db
) -> dict:
    """Register a device. Re-subscribing the same browser returns the same endpoint,
    so this updates rather than duplicating - otherwise one person gets two pings."""
    existing = (
        await db.execute(
            select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.user_id = user.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
        existing.failure_count = 0
    else:
        db.add(
            PushSubscription(
                user_id=user.id,
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
                user_agent=(request.headers.get("user-agent") or "")[:255] or None,
            )
        )

    # Subscribing is a statement of intent; honour it without a second toggle.
    user.reminders_on = True
    await db.commit()
    return {"ok": True}


@router.post("/unsubscribe", status_code=204)
async def unsubscribe(payload: SubscribeIn, user: CurrentUser, db: Db) -> None:
    subscription = (
        await db.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == payload.endpoint,
                PushSubscription.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if subscription is not None:
        await db.delete(subscription)
        await db.commit()


@router.post("/test")
async def send_test(user: CurrentUser, db: Db) -> dict:
    """Prove to the person that notifications actually arrive on this device."""
    text = MESSAGES.get((user.locale or "en")[:2], MESSAGES["en"])
    delivered = await push_service.send_to_user(
        db, user.id, {"title": text["title"], "body": text["body"], "url": "/today"}
    )
    if not delivered:
        raise HTTPException(
            status_code=503,
            detail="Could not deliver to any registered device.",
        )
    return {"delivered": delivered}


@router.patch("/settings")
async def update_settings(payload: ReminderSettingsIn, user: CurrentUser, db: Db) -> dict:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    return {"reminders_on": user.reminders_on, "reminder_hour": user.reminder_hour}
