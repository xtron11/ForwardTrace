from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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
