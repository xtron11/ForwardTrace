"""Deleting an account, restoring it, and erasing it for good.

Deletion happens in two steps. Pressing "delete" marks the account and locks it: no
session works, the AI stops writing first, and a letter with a restore link is sent. The
data stays where it is for settings.account_restore_days, because people delete in a
bad week and regret it in a better one. Once that period is over the eraser removes
every row the account owned and every recording on disk, and nothing is left to
restore.

The eraser runs in-process on a timer, like the other background loops.
"""

import asyncio
import logging
import shutil
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import SessionLocal
from ..models import (
    Conversation,
    Event,
    Fact,
    Goal,
    Message,
    MonthlySummary,
    Outreach,
    Pair,
    PushSubscription,
    Thread,
    User,
)
from ..security import create_restore_token
from . import mail

log = logging.getLogger(__name__)

# Signing in to a deleted account sends the letter again; anyone who knows the
# password can ask for that, so there has to be a gap between letters.
RESEND_INTERVAL_SECONDS = 60


# Default users.country from the timezone, for help-line contacts. Only common zones:
# an unknown one gives None, and the "default" contacts are used.
_COUNTRY_ZONES: dict[str, tuple[str, ...]] = {
    "KZ": ("Asia/Almaty", "Asia/Qyzylorda", "Asia/Aqtobe", "Asia/Aqtau", "Asia/Atyrau",
           "Asia/Oral", "Asia/Qostanay"),
    "RU": ("Europe/Moscow", "Europe/Kaliningrad", "Europe/Samara", "Europe/Volgograd",
           "Europe/Saratov", "Europe/Ulyanovsk", "Europe/Astrakhan", "Europe/Kirov",
           "Asia/Yekaterinburg", "Asia/Omsk", "Asia/Novosibirsk", "Asia/Barnaul",
           "Asia/Tomsk", "Asia/Novokuznetsk", "Asia/Krasnoyarsk", "Asia/Irkutsk",
           "Asia/Chita", "Asia/Yakutsk", "Asia/Vladivostok", "Asia/Magadan",
           "Asia/Sakhalin", "Asia/Kamchatka", "Asia/Anadyr"),
    "UA": ("Europe/Kyiv", "Europe/Kiev", "Europe/Uzhgorod", "Europe/Zaporozhye"),
    "BY": ("Europe/Minsk",),
    "UZ": ("Asia/Tashkent", "Asia/Samarkand"),
    "KG": ("Asia/Bishkek",),
    "TJ": ("Asia/Dushanbe",),
    "TM": ("Asia/Ashgabat",),
    "GE": ("Asia/Tbilisi",),
    "AM": ("Asia/Yerevan",),
    "AZ": ("Asia/Baku",),
    "MD": ("Europe/Chisinau",),
    "LT": ("Europe/Vilnius",),
    "LV": ("Europe/Riga",),
    "EE": ("Europe/Tallinn",),
    "DE": ("Europe/Berlin",),
    "GB": ("Europe/London",),
    "IE": ("Europe/Dublin",),
    "NL": ("Europe/Amsterdam",),
    "CZ": ("Europe/Prague",),
    "FR": ("Europe/Paris",),
    "ES": ("Europe/Madrid", "Atlantic/Canary"),
    "PT": ("Europe/Lisbon",),
    "IT": ("Europe/Rome",),
    "PL": ("Europe/Warsaw",),
    "FI": ("Europe/Helsinki",),
    "SE": ("Europe/Stockholm",),
    "TR": ("Europe/Istanbul",),
    "IL": ("Asia/Jerusalem", "Asia/Tel_Aviv"),
    "AE": ("Asia/Dubai",),
    "IN": ("Asia/Kolkata", "Asia/Calcutta"),
    "CN": ("Asia/Shanghai",),
    "JP": ("Asia/Tokyo",),
    "KR": ("Asia/Seoul",),
    "TH": ("Asia/Bangkok",),
    "SG": ("Asia/Singapore",),
    "US": ("America/New_York", "America/Chicago", "America/Denver", "America/Phoenix",
           "America/Los_Angeles", "America/Anchorage", "Pacific/Honolulu",
           "America/Detroit", "America/Boise", "America/Indiana/Indianapolis"),
    "CA": ("America/Toronto", "America/Vancouver", "America/Edmonton", "America/Winnipeg",
           "America/Halifax", "America/St_Johns", "America/Regina"),
    "BR": ("America/Sao_Paulo",),
    "MX": ("America/Mexico_City",),
    "AU": ("Australia/Sydney", "Australia/Melbourne", "Australia/Brisbane",
           "Australia/Perth", "Australia/Adelaide", "Australia/Hobart", "Australia/Darwin"),
}
COUNTRY_BY_TIMEZONE = {zone: code for code, zones in _COUNTRY_ZONES.items() for zone in zones}


def country_for_timezone(tz_name: str | None) -> str | None:
    return COUNTRY_BY_TIMEZONE.get(tz_name or "")


def _aware(moment: datetime) -> datetime:
    # SQLite hands timestamps back without a zone; Postgres keeps it.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def erase_on(user: User) -> date:
    """The day the data goes for good, as the person is told it."""
    assert user.deleted_at is not None
    return (_aware(user.deleted_at) + timedelta(days=settings.account_restore_days)).date()


async def send_restore_letter(db: AsyncSession, user: User) -> bool:
    """Returns whether a letter went out. Never raises."""
    assert user.deleted_at is not None
    now = datetime.now(timezone.utc)
    if user.restore_sent_at is not None:
        if (now - _aware(user.restore_sent_at)).total_seconds() < RESEND_INTERVAL_SECONDS:
            return False

    token = create_restore_token(user.id, _aware(user.deleted_at))
    sent = await mail.send_account_deleted(
        user.email,
        f"{settings.app_url}/restore?token={token}",
        erase_on(user),
        user.locale or "en",
        name=user.display_name,
    )
    if sent:
        user.restore_sent_at = now
        await db.commit()
    return sent


async def mark_deleted(db: AsyncSession, user: User) -> None:
    user.deleted_at = datetime.now(timezone.utc)
    user.restore_sent_at = None
    # Every session on every device ends here, not when its token happens to expire.
    user.token_version += 1
    db.add(Event(user_id=user.id, type="account_deleted"))
    await db.commit()


async def restore(db: AsyncSession, user: User) -> None:
    user.deleted_at = None
    user.restore_sent_at = None
    db.add(Event(user_id=user.id, type="account_restored"))
    await db.commit()


async def erase(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Remove everything the account owns, then the account.

    Postgres would cascade most of this from the user row on its own, but the deletes
    are spelled out: the suite runs on SQLite, which ignores foreign keys unless asked,
    and an erasure that quietly leaves rows behind is the one bug this must not have.
    """
    # Collected before the rows go: the paths live only in them.
    recordings = [
        Path(path)
        for query in (
            select(Goal.why_audio_path).where(Goal.user_id == user_id),
            select(Message.audio_path).where(Message.user_id == user_id),
        )
        for path in (await db.execute(query)).scalars()
        if path
    ]

    for statement in (
        # Children before parents.
        delete(Pair).where(Pair.user_id == user_id),
        delete(Outreach).where(Outreach.user_id == user_id),
        delete(MonthlySummary).where(MonthlySummary.user_id == user_id),
        delete(Fact).where(Fact.user_id == user_id),
        delete(Thread).where(Thread.user_id == user_id),
        delete(Message).where(Message.user_id == user_id),
        delete(Conversation).where(Conversation.user_id == user_id),
        delete(Goal).where(Goal.user_id == user_id),
        delete(PushSubscription).where(PushSubscription.user_id == user_id),
        delete(Event).where(Event.user_id == user_id),
        delete(User).where(User.id == user_id),
    ):
        await db.execute(statement)
    await db.commit()

    # Files after the commit: a failed transaction must not leave an account whose
    # recordings are already gone. Every upload lands in the user's own folder, but a
    # changed AUDIO_DIR would leave older paths elsewhere, so those go one by one.
    for path in recordings:
        path.unlink(missing_ok=True)
    shutil.rmtree(Path(settings.audio_dir) / str(user_id), ignore_errors=True)


async def purge_expired(now: datetime | None = None) -> int:
    """Erase every account whose grace period is over. Returns how many."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=settings.account_restore_days)
    async with SessionLocal() as db:
        due = (
            await db.execute(
                select(User.id).where(User.deleted_at.is_not(None), User.deleted_at <= cutoff)
            )
        ).scalars().all()

    erased = 0
    for user_id in due:
        # One session per account, so one failure does not hold up the rest.
        try:
            async with SessionLocal() as db:
                await erase(db, user_id)
            erased += 1
        except Exception:  # noqa: BLE001
            log.exception("could not erase account %s", user_id)

    if erased:
        log.info("erased %s deleted accounts", erased)
    return erased


async def loop() -> None:
    """Background task started at app startup and cancelled at shutdown."""
    interval = settings.account_purge_tick_minutes * 60
    while True:
        try:
            await purge_expired()
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - an eraser that dies silently keeps data it promised to remove
            log.exception("account purge pass failed; continuing")
            await asyncio.sleep(interval)
