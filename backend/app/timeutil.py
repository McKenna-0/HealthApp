from datetime import date, datetime
from zoneinfo import ZoneInfo

from .config import settings


def tzinfo() -> ZoneInfo:
    return ZoneInfo(settings.tz)


def now_local() -> datetime:
    return datetime.now(tzinfo())


def today_local() -> date:
    return now_local().date()


def iso_now() -> str:
    return now_local().isoformat(timespec="seconds")
