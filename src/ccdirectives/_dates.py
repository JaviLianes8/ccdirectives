"""HTTP-date (RFC 9110 section 5.6.7): IMF-fixdate, rfc850-date and asctime-date."""

from __future__ import annotations

import calendar
import re
import time

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_LONG_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_TIME = r"([0-9]{2}):([0-9]{2}):([0-9]{2})"
# Names and GMT compare without case (ASCII only, as RFC 9111 section 4.2 asks of a cache);
# digits are ASCII and every space is the one the grammar has.
_GMT = "[Gg][Mm][Tt]"
_IMF = re.compile(rf"([A-Za-z]+), ([0-9]{{2}}) ([A-Za-z]+) ([0-9]{{4}}) {_TIME} {_GMT}")
_RFC850 = re.compile(rf"([A-Za-z]+), ([0-9]{{2}})-([A-Za-z]+)-([0-9]{{2}}) {_TIME} {_GMT}")
_ASCTIME = re.compile(rf"([A-Za-z]+) ([A-Za-z]+) ([0-9]{{2}}| [0-9]) {_TIME} ([0-9]{{4}})")


def http_date(value: str | None, now: float | None = None) -> float | None:
    """Seconds since the epoch for an HTTP-date, or None when it is not one.

    The three formats are read as UTC. IMF-fixdate and rfc850-date must say ``GMT``, in
    any case: a date in another zone is invalid, as RFC 9111 section 4.2 asks for
    expiration. An rfc850 two-digit year gives the latest instant with those digits that
    is at most 50 years after ``now`` (the current time by default): an instant more than
    50 years ahead is moved 100 years back, as RFC 9110 section 5.6.7 requires. Only a
    year that has the day counts: 29 February takes the latest such leap year.
    """
    if value is None:
        return None
    imf = _IMF.fullmatch(value)
    if imf:
        day, d, month, year, *clock = imf.groups()
        return _stamp(_day(day, _DAYS), [int(year)], month, d, clock)
    rfc850 = _RFC850.fullmatch(value)
    if rfc850:
        day, d, month, yy, *clock = rfc850.groups()
        years = _centuries(int(yy), now)
        return _stamp(_day(day, _LONG_DAYS), years, month, d, clock, _limit(now))
    asctime = _ASCTIME.fullmatch(value)
    if asctime:
        day, month, d, *clock, year = asctime.groups()
        return _stamp(_day(day, _DAYS), [int(year)], month, d.strip(" "), clock)
    return None


def _day(name: str, names: tuple[str, ...]) -> bool:
    # The day name must be one, but need not match the date: the date decides.
    return name.lower() in names


def _centuries(two_digits: int, now: float | None) -> list[int]:
    # The candidate years with those digits, latest first. Six centuries always hold one that
    # is not ahead of the limit and, from there, a leap year for 29 February.
    current = time.gmtime(time.time() if now is None else now).tm_year
    year = current - current % 100 + two_digits + 100
    return [year - 100 * back for back in range(6)]


def _limit(now: float | None) -> tuple[int, ...]:
    # The same instant 50 years after now, as a calendar tuple, so whole timestamps compare.
    t = time.gmtime(time.time() if now is None else now)
    return (t.tm_year + 50, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec)


def _stamp(
    ok: bool,
    years: list[int],
    month: str,
    day: str,
    clock: list[str],
    limit: tuple[int, ...] | None = None,
) -> float | None:
    if not ok or month.lower() not in _MONTHS:
        return None
    number = _MONTHS.index(month.lower()) + 1
    hour, minute, second = (int(part) for part in clock)
    # Second 60 is a leap second, which the grammar allows and the epoch count skips.
    if hour > 23 or minute > 59 or second > 60:
        return None
    # A year is a candidate only when it has the day: 29 February needs a leap year.
    years = [y for y in years if y >= 1 and 1 <= int(day) <= calendar.monthrange(y, number)[1]]
    if limit is not None:
        # The latest instant not more than 50 years ahead; a later one is a century earlier.
        years = [y for y in years if (y, number, int(day), hour, minute, second) <= limit]
    if not years:
        return None
    year = years[0]
    return float(calendar.timegm((year, number, int(day), hour, minute, second, 0, 0, 0)))
