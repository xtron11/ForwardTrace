"""Safety check of every message the person sends (levels 0-3) and what each level
changes (brief, "Безопасность: services/safety.py").

0 - ordinary reply. 1 - ordinary reply, gentler; on frequent tiredness a rare,
soft suggestion to see a doctor or a psychologist. 2 - a separate prompt
(`prompts.SAFETY_SYSTEM`) with no memory and no progress. 3 - a template from
services/texts.py, never a model, with help contacts for the person's country
(`SAFETY_RESOURCES`, filled in by the owner from official sources; empty means a
general recommendation with no number). Outreach pauses after a level-3 message until
the person writes again (services/outreach.py reads `messages.safety_level`).

The conversation flow (services/conversation.py) calls these and writes the events.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Conversation, Event, Message, User
from . import prompts, texts
from .llm import complete_json_with

log = logging.getLogger(__name__)


@dataclass(slots=True)
class SafetyResult:
    level: int
    # True when the model call failed and level 0 was assumed; the caller logs the
    # `safety_check_failed` event.
    failed: bool = False


async def safety_check(text: str, locale: str | None) -> SafetyResult:
    """The level of one message from SAFETY_MODEL. Any failure is level 0 with
    `failed=True`: a broken check must not block the conversation."""
    try:
        result = await complete_json_with(
            prompts.SAFETY_CHECK_SYSTEM,
            prompts.safety_check_user_prompt(text),
            prompts.SAFETY_CHECK_SCHEMA,
            model=settings.safety_model or settings.openai_model,
        )
        level = int(result.data.get("level"))
    except Exception:  # noqa: BLE001 - LLMError, a malformed answer, anything
        log.warning("safety check failed; assuming level 0", exc_info=True)
        return SafetyResult(level=0, failed=True)
    return SafetyResult(level=min(max(level, 0), 3), failed=False)


# ------------------------------------------------------------------ level 3


def resources_for(country: str | None) -> list[dict]:
    """Help contacts for a country (ISO code), else the "default" list, else none.
    Entries without both a name and a contact are left out: an empty placeholder is
    not a contact."""
    table = settings.safety_resources or {}

    def usable(entries) -> list[dict]:
        out = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            contact = str(entry.get("contact") or "").strip()
            if name and contact:
                out.append({"name": name, "contact": contact})
        return out

    if country:
        found = usable(table.get(country.upper()))
        if found:
            return found
    return usable(table.get("default"))


def level3_text(user: User) -> str:
    """The level-3 reply. Calm, «вы» in Russian; it does not promise confidentiality
    and does not say who would be told anything."""
    contacts = resources_for(user.country)
    if not contacts:
        return texts.t(user.locale, "safety.level3_no_resources")
    lines = "\n".join(
        texts.t(user.locale, "safety.resource_line", name=c["name"], contact=c["contact"])
        for c in contacts
    )
    return (
        f"{texts.t(user.locale, 'safety.level3')}\n\n{lines}\n\n"
        f"{texts.t(user.locale, 'safety.level3_contact_someone')}"
    )


# ------------------------------------------------------------------ level 2


def _visible_text(message: Message) -> str:
    """What a stored message said, without any quote from the past."""
    if message.role == "user":
        return message.content_raw or ""
    return "".join(
        s.get("text", "") for s in (message.content or []) if s.get("type") == "text"
    ).strip()


def level2_messages(locale: str | None, history: list[Message]) -> list[dict]:
    """The model's input for a level-2 reply: SAFETY_SYSTEM and today's conversation
    only - no goal, facts, threads, past days or quotes."""
    messages = [{"role": "system", "content": prompts.safety_system(locale)}]
    for message in history:
        content = _visible_text(message)
        if content:
            messages.append(
                {"role": "user" if message.role == "user" else "assistant", "content": content}
            )
    return messages


# ------------------------------------------------------------------ level 1


async def should_suggest_help(db: AsyncSession, user: User, today: date) -> bool:
    """Level 1 on at least SAFETY_HELP_MIN_DAYS of the last SAFETY_HELP_WINDOW_DAYS
    days (today included), and no suggestion within SAFETY_HELP_COOLDOWN_DAYS."""
    since = today - timedelta(days=settings.safety_help_window_days - 1)
    days = (
        await db.execute(
            select(func.count(func.distinct(Conversation.local_date)))
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(
                Message.user_id == user.id,
                Message.role == "user",
                Message.safety_level == 1,
                Conversation.local_date >= since,
                Conversation.local_date <= today,
            )
        )
    ).scalar_one()
    if days < settings.safety_help_min_days:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.safety_help_cooldown_days)
    recent = (
        await db.execute(
            select(Event.id)
            .where(
                Event.user_id == user.id,
                Event.type == "safety_suggest_help",
                Event.created_at >= cutoff,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return recent is None
