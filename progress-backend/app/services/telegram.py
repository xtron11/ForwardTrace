"""The Telegram bot: a channel for the AI's first message, and a place to answer it.

Everything goes through the Bot API over httpx; there is no SDK. The webhook is checked
by the X-Telegram-Bot-Api-Secret-Token header (routers/telegram.py). Without
TELEGRAM_BOT_TOKEN (and the bot's username, needed for the link) Telegram is off: the
endpoints answer 503 and the profile hides the channel.

Linking: POST /api/telegram/link stores a one-time token in users.telegram_link_token
and hands out t.me/<bot>?start=<token>; "/start <token>" in the bot binds the chat,
switches the channel to telegram and clears the token. A text or voice message from a
linked chat becomes a message in today's conversation, and the streamed reply is sent
back as one message.

The bot token is part of every Bot API URL, so neither URLs nor httpx exception texts
(which quote the URL) are ever logged.
"""

import hmac
import io
import json
import logging
import secrets

import httpx
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from ..config import settings
from ..db import SessionLocal
from ..models import User
from . import texts

log = logging.getLogger(__name__)

API = "https://api.telegram.org"
# Tests put an httpx.MockTransport here; None is the real network.
_transport: httpx.AsyncBaseTransport | None = None
_TIMEOUT = 15.0
TEXT_LIMIT = 4096  # the Bot API refuses longer messages


def enabled() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_bot_username)


def secret_ok(header: str | None) -> bool:
    """The webhook's secret header matches TELEGRAM_WEBHOOK_SECRET. No secret
    configured means no request is trusted."""
    expected = settings.telegram_webhook_secret
    if not expected or not header:
        return False
    return hmac.compare_digest(header.encode(), expected.encode())


def app_link(path: str) -> str:
    return f"{settings.app_url.rstrip('/')}{path}"


async def _call(method: str, payload: dict) -> dict | bool | None:
    """One Bot API method. Returns its `result`, or None on any failure."""
    url = f"{API}/bot{settings.telegram_bot_token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, transport=_transport) as client:
            response = await client.post(url, json=payload)
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("telegram %s failed: %s", method, type(exc).__name__)
        return None
    if response.status_code != 200 or not isinstance(data, dict) or not data.get("ok"):
        description = data.get("description") if isinstance(data, dict) else None
        log.warning("telegram %s answered %s: %s", method, response.status_code, str(description)[:200])
        return None
    return data.get("result", True)


async def send_message(
    chat_id: int, text: str, button_url: str | None = None, *, button_text: str | None = None
) -> bool:
    """Send `text`; with `button_url`, under an inline button that opens the app.
    True when Telegram accepted it."""
    if not enabled():
        return False
    payload: dict = {"chat_id": chat_id, "text": text[:TEXT_LIMIT]}
    if button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [{"text": button_text or texts.t("en", "outreach.reply_button"), "url": button_url}]
            ]
        }
    if await _call("sendMessage", payload) is not None:
        return True
    if button_url:
        # Telegram refuses buttons to addresses it cannot open (a local APP_URL, for
        # one). The words matter more than the button.
        payload.pop("reply_markup")
        return await _call("sendMessage", payload) is not None
    return False


async def create_link(db: AsyncSession, user: User) -> str:
    """A fresh one-time link; the previous one stops working."""
    token = secrets.token_urlsafe(24)  # 32 characters of [A-Za-z0-9_-], as /start allows
    user.telegram_link_token = token
    await db.commit()
    return f"https://t.me/{settings.telegram_bot_username}?start={token}"


# ------------------------------------------------------------------ incoming


async def handle_update(update: dict) -> None:
    """One update from the webhook. Never raises: the webhook has already answered."""
    try:
        await _handle(update)
    except Exception:  # noqa: BLE001
        log.exception("telegram update %s failed", update.get("update_id"))


async def _handle(update: dict) -> None:
    message = update.get("message")
    if not isinstance(message, dict):
        return
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not isinstance(chat_id, int) or chat.get("type", "private") != "private":
        return
    language = (message.get("from") or {}).get("language_code")
    text = message.get("text")

    async with SessionLocal() as db:
        linked = (
            await db.execute(
                select(User).where(
                    User.telegram_chat_id == chat_id,
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                )
            )
        ).scalars().first()

        if isinstance(text, str) and text.startswith("/start"):
            await _start(db, chat_id, text, language, linked)
            return
        if linked is None:
            await send_message(chat_id, texts.t(language, "telegram.not_linked"))
            return
        await _answer(db, linked, chat_id, message)


async def _start(
    db: AsyncSession, chat_id: int, text: str, language: str | None, linked: User | None
) -> None:
    parts = text.split(maxsplit=1)
    token = parts[1].strip() if len(parts) > 1 else ""
    user = None
    if token:
        user = (
            await db.execute(
                select(User).where(
                    User.telegram_link_token == token,
                    User.deleted_at.is_(None),
                    User.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
    if user is None:
        if not token and linked is not None:
            await send_message(chat_id, texts.t(linked.locale, "telegram.linked"))
        else:
            await send_message(chat_id, texts.t(language, "telegram.link_expired"))
        return

    # One chat belongs to one account: a chat linked before moves to the new one.
    others = (
        await db.execute(
            select(User).where(User.telegram_chat_id == chat_id, User.id != user.id)
        )
    ).scalars()
    for other in others:
        other.telegram_chat_id = None
        if other.outreach_channel == "telegram":
            other.outreach_channel = "push"

    user.telegram_chat_id = chat_id
    user.telegram_link_token = None
    user.outreach_channel = "telegram"
    await db.commit()
    await send_message(chat_id, texts.t(user.locale, "telegram.linked"))


async def _download_voice(voice: dict) -> UploadFile | None:
    file_id = voice.get("file_id")
    if not isinstance(file_id, str):
        return None
    size = voice.get("file_size")
    if isinstance(size, int) and size > settings.max_audio_mb * 1024 * 1024:
        return None
    info = await _call("getFile", {"file_id": file_id})
    path = info.get("file_path") if isinstance(info, dict) else None
    if not isinstance(path, str):
        return None
    url = f"{API}/file/bot{settings.telegram_bot_token}/{path}"
    try:
        async with httpx.AsyncClient(timeout=60.0, transport=_transport) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        log.warning("telegram voice download failed: %s", type(exc).__name__)
        return None
    if response.status_code != 200:
        return None
    mime = voice.get("mime_type") or "audio/ogg"
    return UploadFile(
        file=io.BytesIO(response.content),
        filename=path.rsplit("/", 1)[-1] or "voice.ogg",
        headers=Headers({"content-type": mime}),
    )


_ERROR_TEXTS = {
    "limit_reached": "telegram.limit_reached",
    "reply_in_progress": "telegram.busy",
}


def _sse_event(item: str) -> tuple[str, dict]:
    name, data = "message", ""
    for line in item.split("\n"):
        if line.startswith("event:"):
            name = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data += line[len("data:"):].strip()
    try:
        return name, json.loads(data) if data else {}
    except json.JSONDecodeError:
        return name, {}


def _quoted(locale: str | None, quote: str) -> str:
    return f"«{quote}»" if (locale or "").startswith("ru") else f"“{quote}”"


async def _answer(db: AsyncSession, user: User, chat_id: int, message: dict) -> None:
    """The person's text or voice as a message in today's conversation (the same path
    as the app), the reply collected from the stream and sent as one message."""
    from . import conversation as convo  # conversation -> ... must not import this module

    open_app = texts.t(user.locale, "telegram.open_app")
    text = message.get("text")
    audio = None
    if not (isinstance(text, str) and text.strip()):
        text = None
        voice = message.get("voice") or message.get("audio")
        if not isinstance(voice, dict):
            await send_message(chat_id, texts.t(user.locale, "telegram.unsupported"))
            return
        audio = await _download_voice(voice)
        if audio is None:
            await send_message(
                chat_id, texts.t(user.locale, "telegram.cannot_reply"), app_link("/today"),
                button_text=open_app,
            )
            return

    try:
        prepared = await convo.prepare_message(db, user, text=text, audio=audio)
    except HTTPException as exc:
        code = exc.detail.get("code") if isinstance(exc.detail, dict) else None
        key = _ERROR_TEXTS.get(code, "telegram.cannot_reply")
        await send_message(
            chat_id, texts.t(user.locale, key), app_link("/today"), button_text=open_app
        )
        return

    parts: list[str] = []
    failed = False
    try:
        async for item in convo.stream_reply(prepared):
            event, data = _sse_event(item)
            if event == "delta":
                parts.append(str(data.get("text", "")))
            elif event == "quote":
                parts.append(_quoted(user.locale, str(data.get("quote", ""))))
            elif event == "error":
                failed = True
    finally:
        convo.release_if_unstarted(prepared)

    reply = "".join(parts).strip()
    if failed or not reply:
        await send_message(
            chat_id, texts.t(user.locale, "telegram.cannot_reply"), app_link("/today"),
            button_text=open_app,
        )
        return
    await send_message(chat_id, reply)
