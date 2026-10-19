"""HTTP-date (RFC 9110 section 5.6.7): IMF-fixdate, rfc850-date and asctime-date."""

from __future__ import annotations

import calendar
import re
import time

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_LONG_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_TIME = r"([0-9]{2}):([0-9]{2}):([0-9]{2})"
# Names compare without case; digits are ASCII and every space is the one the grammar has.
_IMF = re.compile(rf"([A-Za-z]+), ([0-9]{{2}}) ([A-Za-z]+) ([0-9]{{4}}) {_TIME} GMT")
_RFC850 = re.compile(rf"([A-Za-z]+), ([0-9]{{2}})-([A-Za-z]+)-([0-9]{{2}}) {_TIME} GMT")
_ASCTIME = re.compile(rf"([A-Za-z]+) ([A-Za-z]+) ([0-9]{{2}}| [0-9]) {_TIME} ([0-9]{{4}})")


def http_date(value: str | None, now: float | None = None) -> float | None:
    """Seconds since the epoch for an HTTP-date, or None when it is not one.

    The three formats are read as UTC. IMF-fixdate and rfc850-date must say ``GMT``: a
    date in another zone is invalid, as RFC 9111 section 4.2 asks for expiration. An
    rfc850 two-digit year is the latest year with those digits that is at most 50 years
    after ``now`` (the current time by default), as RFC 9110 section 5.6.7 requires.
    """
    if value is None:
        return None
    imf = _IMF.fullmatch(value)
    if imf:
        day, d, month, year, *clock = imf.groups()
        return _stamp(_day(day, _DAYS), int(year), month, d, clock)
    rfc850 = _RFC850.fullmatch(value)
    if rfc850:
        day, d, month, yy, *clock = rfc850.groups()
        return _stamp(_day(day, _LONG_DAYS), _century(int(yy), now), month, d, clock)
    asctime = _ASCTIME.fullmatch(value)
    if asctime:
        day, month, d, *clock, year = asctime.groups()
        return _stamp(_day(day, _DAYS), int(year), month, d.strip(" "), clock)
    return None


def _day(name: str, names: tuple[str, ...]) -> bool:
    # The day name must be one, but need not match the date: the date decides.
    return name.lower() in names


def _century(two_digits: int, now: float | None) -> int:
    current = time.gmtime(time.time() if now is None else now).tm_year
    year = current - current % 100 + two_digits
    while year > current + 50:
        year -= 100
    while year + 100 <= current + 50:
        year += 100
    return year


def _stamp(ok: bool, year: int, month: str, day: str, clock: list[str]) -> float | None:
    if not ok or month.lower() not in _MONTHS or year < 1:
        return None
    number = _MONTHS.index(month.lower()) + 1
    hour, minute, second = (int(part) for part in clock)
    if not 1 <= int(day) <= calendar.monthrange(year, number)[1]:
        return None
    # Second 60 is a leap second, which the grammar allows and the epoch count skips.
    if hour > 23 or minute > 59 or second > 60:
        return None
    return float(calendar.timegm((year, number, int(day), hour, minute, second, 0, 0, 0)))
