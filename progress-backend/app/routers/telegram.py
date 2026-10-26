"""Telegram: the one-time link, unlinking, and the bot's webhook (services/telegram.py).

Without TELEGRAM_BOT_TOKEN (and TELEGRAM_BOT_USERNAME) the link and the webhook answer
503 `telegram_disabled`. Unlinking works either way: forgetting a chat needs no bot.
"""

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, Response

from ..deps import CurrentUser, Db
from ..schemas import TelegramLinkOut
from ..services import telegram
from ..services.errors import TELEGRAM_DISABLED, api_error

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


def _disabled():
    return api_error(503, TELEGRAM_DISABLED, "Telegram is not configured on this server.")


@router.post("/link", response_model=TelegramLinkOut)
async def link(user: CurrentUser, db: Db) -> TelegramLinkOut:
    """A fresh t.me link with a one-time token; the previous link stops working."""
    if not telegram.enabled():
        raise _disabled()
    return TelegramLinkOut(url=await telegram.create_link(db, user))


@router.delete("/link", status_code=204)
async def unlink(user: CurrentUser, db: Db) -> Response:
    """Forget the chat. The AI's messages go back to push if they went to Telegram."""
    user.telegram_chat_id = None
    user.telegram_link_token = None
    if user.outreach_channel == "telegram":
        user.outreach_channel = "push"
    await db.commit()
    return Response(status_code=204)


@router.post("/webhook")
async def webhook(
    request: Request,
    background: BackgroundTasks,
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict:
    """Updates from Telegram. Answered at once; the work (a reply can take a while)
    runs after the response, so Telegram does not resend the update."""
    if not telegram.enabled():
        raise _disabled()
    if not telegram.secret_ok(secret):
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        update = await request.json()
    except ValueError:
        return {"ok": True}
    if isinstance(update, dict):
        background.add_task(telegram.handle_update, update)
    return {"ok": True}
