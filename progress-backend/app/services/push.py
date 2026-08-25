"""Web Push delivery.

Reminders go here rather than to email because an inbox is where a nudge goes to die.
The rule that keeps this from becoming spam is in the scheduler, not here: nobody is
reminded on a day they have already checked in.
"""

import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import PushSubscription

log = logging.getLogger(__name__)

# A subscription that fails this many times in a row is gone: the browser was
# uninstalled, the permission revoked, the endpoint rotated. Retrying forever wastes
# requests and hides real failures in the noise.
MAX_FAILURES = 3


class PushError(RuntimeError):
    pass


def _send_sync(subscription: PushSubscription, payload: dict) -> int:
    """Returns the HTTP status. Blocking, so callers run it in a thread."""
    from pywebpush import WebPushException, webpush

    try:
        response = webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": f"mailto:{settings.vapid_subject_email}"},
            ttl=settings.push_ttl_seconds,
        )
        return response.status_code
    except WebPushException as exc:
        status = getattr(exc.response, "status_code", 0)
        # 404 and 410 are the browser telling us the subscription no longer exists.
        if status in (404, 410):
            return status
        raise PushError(str(exc)[:300]) from exc


async def send_to_user(db: AsyncSession, user_id, payload: dict) -> int:
    """Push to every device this person has registered. Returns how many got through."""
    if not settings.vapid_private_key:
        log.warning("push requested but VAPID_PRIVATE_KEY is not set")
        return 0

    subscriptions = (
        (
            await db.execute(
                select(PushSubscription).where(PushSubscription.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )

    delivered = 0
    for subscription in subscriptions:
        try:
            status = await asyncio.to_thread(_send_sync, subscription, payload)
        except PushError as exc:
            log.warning("push to %s failed: %s", subscription.id, exc)
            subscription.failure_count += 1
            if subscription.failure_count >= MAX_FAILURES:
                await db.delete(subscription)
            continue

        if status in (404, 410):
            # Definitively dead; no point counting toward a threshold.
            await db.delete(subscription)
            continue

        from datetime import datetime, timezone

        subscription.failure_count = 0
        subscription.last_success_at = datetime.now(timezone.utc)
        delivered += 1

    await db.commit()
    return delivered
