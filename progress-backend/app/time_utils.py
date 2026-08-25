from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import settings


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def tz_of(name: str | None) -> ZoneInfo:
    if name and valid_timezone(name):
        return ZoneInfo(name)
    return ZoneInfo("UTC")


def local_today(tz_name: str | None, at: datetime | None = None) -> date:
    """The calendar day as the *user* experiences it, not as the server does."""
    moment = at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tz_of(tz_name)).date()


def period_bounds(anchor: date, days: int | None = None) -> tuple[date, date]:
    """The N-day window ending on `anchor`, inclusive on both sides."""
    n = days or settings.report_period_days
    return anchor - timedelta(days=n - 1), anchor


def week_index(started_on: date, today: date, days: int | None = None) -> int:
    """1-based ordinal of the period the user is currently in."""
    n = days or settings.report_period_days
    return max(1, ((today - started_on).days // n) + 1)


def completed_period(started_on: date, today: date, days: int | None = None) -> tuple[date, date] | None:
    """The most recent *finished* period since the goal started, or None if none finished yet."""
    n = days or settings.report_period_days
    elapsed = (today - started_on).days
    if elapsed < n:
        return None
    completed_count = elapsed // n
    start = started_on + timedelta(days=(completed_count - 1) * n)
    return start, start + timedelta(days=n - 1)


def fmt_minutes(total: int) -> str:
    hours, minutes = divmod(int(total), 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
