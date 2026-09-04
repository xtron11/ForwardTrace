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
    """The most recent finished reporting period, or None if none has finished.

    `first_days` is the day the first report APPEARS on, counting the day the goal was
    set as day one. With the default of 3 it shows up on the third day and covers the
    two completed days before it - "day three" in the plain sense of the phrase, which
    is how anyone waiting for it will read it.

    Every later period is a full week. Reports only ever cover finished days: a report
    that included today would go stale the moment someone checked in again, and it is
    written once and kept.

        day 1-2    first period, readable on day 3
        day 3-9    second period, readable on day 10
        day 10-16  third, and so on
    """
    n = days or settings.report_period_days
    first = first_days if first_days is not None else settings.first_report_after_days
    # Days of history the first report needs before it can appear.
    lead = max(first - 1, 1)
    elapsed = (today - started_on).days

    if elapsed < lead:
        return None
    if elapsed < lead + n:
        return started_on, started_on + timedelta(days=lead - 1)

    index = (elapsed - lead) // n
    start = started_on + timedelta(days=lead + (index - 1) * n)
    return start, start + timedelta(days=n - 1)


def days_until_report(started_on: date, today: date, days: int | None = None,
                      first_days: int | None = None) -> int:
    """How many days until the next period closes. Zero means one has already closed."""
    n = days or settings.report_period_days
    first = first_days if first_days is not None else settings.first_report_after_days
    lead = max(first - 1, 1)
    elapsed = (today - started_on).days

    if elapsed < lead:
        return lead - elapsed
    index = ((elapsed - lead) // n) + 1
    return (lead + index * n) - elapsed


def is_first_period(started_on: date, period_start: date) -> bool:
    return period_start == started_on


def fmt_minutes(total: int) -> str:
    hours, minutes = divmod(int(total), 60)
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"
