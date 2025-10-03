"""Time helper utilities."""

from __future__ import annotations

from datetime import datetime, time

from dateutil import tz


def to_timezone(dt: datetime, tz_name: str) -> datetime:
    target = tz.gettz(tz_name)
    if target is None:
        target = tz.UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz.UTC)
    return dt.astimezone(target)


def is_time_between(check: time, start: time, end: time) -> bool:
    """Return True if check is within [start, end) with wrap-around support."""

    if start <= end:
        return start <= check < end
    return check >= start or check < end
