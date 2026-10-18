"""Freshness lifetime and current age, RFC 9111 sections 4.2.1 and 4.2.3."""

from __future__ import annotations

import math
from collections.abc import Callable
from fractions import Fraction

from ._chars import DELTA_MAX
from ._checks import check_bool, check_seconds, check_time, is_a, type_name
from ._model import CacheControl


def policy(name: str, value: object) -> CacheControl:
    if not is_a(value, CacheControl):
        raise TypeError(f"{name} must be a CacheControl, not {type_name(value)}")
    return value


def freshness_lifetime(
    response: CacheControl,
    *,
    shared: bool = False,
    expires: float | None = None,
    date: float | None = None,
) -> int | None:
    """The freshness lifetime in seconds by the first matching rule of RFC 9111 4.2.1.

    ``s-maxage`` counts for a shared cache, then ``max-age``, then ``expires - date``
    (both in seconds since the epoch; pass the time of receipt as ``date`` when the
    response has no Date). A directive that is present but not delta-seconds gives 0, as
    section 4.2.1 encourages treating invalid freshness information as stale. The result
    is at most 2147483648, the cap of section 1.2.2.

    >>> from ccdirectives import parse
    >>> freshness_lifetime(parse("max-age=60, s-maxage=600"), shared=True)
    600
    >>> freshness_lifetime(parse("public"), expires=1_700_000_600, date=1_700_000_000)
    600
    >>> freshness_lifetime(parse("public")) is None
    True
    """
    policy("response", response)
    check_bool("shared", shared)
    stamps = [
        None if v is None else check_time(n, v) for n, v in (("expires", expires), ("date", date))
    ]
    for name in ("s-maxage", "max-age") if shared else ("max-age",):
        if response.has(name):
            return response.seconds(name) or 0
    if stamps[0] is None:
        return None
    if stamps[1] is None:
        raise ValueError("pass date (or the time the response was received) with expires")
    return _capped(math.floor, Fraction(stamps[0]) - Fraction(stamps[1]))


def current_age(
    *,
    date_value: float,
    request_time: float,
    response_time: float,
    now: float,
    age_value: int = 0,
) -> int:
    """The current age in whole seconds, rounded up (RFC 9111 section 4.2.3).

    All times are seconds since the epoch; ``age_value`` is the Age field. A result past
    2147483648, or one that overflows, is 2147483648 (section 1.2.2).

    >>> current_age(date_value=100, request_time=100, response_time=102, now=160, age_value=30)
    90
    """
    # An Age beyond 2^31 means the same as 2^31 (RFC 9111 section 1.2.2).
    age_value = min(check_seconds("age_value", age_value), DELTA_MAX)
    date_value = check_time("date_value", date_value)
    request_time = check_time("request_time", request_time)
    response_time = check_time("response_time", response_time)
    now = check_time("now", now)
    # Fractions hold ints and floats exactly: mixing them can neither overflow nor round.
    date, sent, received = Fraction(date_value), Fraction(request_time), Fraction(response_time)
    apparent_age = max(Fraction(0), received - date)
    corrected_age_value = age_value + (received - sent)
    corrected_initial_age = max(apparent_age, corrected_age_value)
    return _capped(math.ceil, corrected_initial_age + (Fraction(now) - received))


def _capped(rounding: Callable[[Fraction], int], seconds: Fraction) -> int:
    # Section 1.2.2: a calculation that overflows (here, anything past 2^31) is taken as 2^31.
    if not seconds < DELTA_MAX:
        return DELTA_MAX
    return 0 if seconds <= 0 else rounding(seconds)
