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


def completed_period(
    started_on: date,
    today: date,
    days: int | None = None,
    first_days: int | None = None,
) -> tuple[date, date] | None:
    """The most recent *finished* reporting period, or None if none has finished.

    The first period is short (three days by default) and every one after it is a full
    week. Waiting a week for the first report asks someone to trust the product on
    faith for longer than most people will, and the ones who quit before day seven
    never see what they were producing input for.

        day 0-2    first period
        day 3-9    second period
        day 10-16  third, and so on
    """
    n = days or settings.report_period_days
    first = first_days if first_days is not None else settings.first_report_after_days
    elapsed = (today - started_on).days

    if elapsed < first:
        return None
    if elapsed < first + n:
        return started_on, started_on + timedelta(days=first - 1)

    index = (elapsed - first) // n
    start = started_on + timedelta(days=first + (index - 1) * n)
    return start, start + timedelta(days=n - 1)


def is_first_period(started_on: date, period_start: date) -> bool:
    return period_start == started_on


def fmt_minutes(total: int) -> str:
    hours, minutes = divmod(int(total), 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
