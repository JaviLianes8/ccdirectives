"""Freshness, age and reuse decisions for a stored response (RFC 9111 section 4.2, RFC 5861)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ._chars import field_names
from ._model import CacheControl


@dataclass(frozen=True)
class Freshness:
    """What a cache may do with a stored response at a given age.

    ``lifetime`` is None when the response carries no explicit expiration; no heuristic is
    applied, so such a response counts as stale. ``reusable`` means it may be sent without
    contacting the origin; ``stale_while_revalidate`` that it may be sent while a background
    revalidation runs; ``stale_if_error`` that it may be sent if the origin fails.
    """

    lifetime: int | None
    age: int
    fresh: bool
    reusable: bool
    stale_while_revalidate: bool
    stale_if_error: bool

    @property
    def staleness(self) -> int:
        """Seconds past the end of the lifetime, 0 while fresh."""
        return max(0, self.age - (self.lifetime or 0))


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
    section 4.2.1 encourages treating invalid freshness information as stale.
    """
    for name in ("s-maxage", "max-age") if shared else ("max-age",):
        if response.has(name):
            return response.seconds(name) or 0
    if expires is None:
        return None
    if date is None:
        raise ValueError("pass date (or the time the response was received) with expires")
    return max(0, math.floor(expires - date))


def current_age(
    *,
    date_value: float,
    request_time: float,
    response_time: float,
    now: float,
    age_value: int = 0,
) -> int:
    """The current age in whole seconds, rounded up (RFC 9111 section 4.2.3)."""
    if age_value < 0:
        raise ValueError("age_value cannot be negative")
    apparent_age = max(0.0, response_time - date_value)
    corrected_age_value = age_value + (response_time - request_time)
    corrected_initial_age = max(apparent_age, corrected_age_value)
    return max(0, math.ceil(corrected_initial_age + (now - response_time)))


def _stale_forbidden(response: CacheControl, shared: bool) -> bool:
    # RFC 9111 section 4.2.4 lists what forbids serving a stale response.
    if response.no_cache or response.must_revalidate:
        return True
    return shared and (response.proxy_revalidate or response.has("s-maxage"))


def assess(
    response: CacheControl,
    *,
    age: int,
    shared: bool = False,
    request: CacheControl | None = None,
    expires: float | None = None,
    date: float | None = None,
) -> Freshness:
    """Decide whether a stored response of ``age`` seconds may be reused.

    The response directives set the lifetime and what forbids stale use (``no-cache``,
    ``must-revalidate``, and for shared caches ``proxy-revalidate`` and ``s-maxage``);
    a ``no-cache`` response is never reusable without validation, qualified or not. The
    optional request directives narrow reuse: ``no-cache``, ``max-age``, ``min-fresh``,
    and ``max-stale`` to accept a stale response. ``stale-if-error`` in the request takes
    precedence over the response's for that request (RFC 5861 section 4).
    """
    if isinstance(age, bool) or not isinstance(age, int):
        raise TypeError("age is a whole number of seconds")
    if age < 0:
        raise ValueError("age cannot be negative")
    asked = request if request is not None else CacheControl()
    lifetime = freshness_lifetime(response, shared=shared, expires=expires, date=date)
    fresh = lifetime is not None and lifetime > age
    staleness = max(0, age - (lifetime or 0))
    forbidden = _stale_forbidden(response, shared)
    reusable = not response.no_cache and not asked.no_cache
    if asked.has("max-age"):
        reusable = reusable and age <= (asked.max_age or 0)
    if fresh:
        if asked.has("min-fresh"):
            reusable = reusable and (lifetime or 0) - age >= (asked.min_fresh or 0)
    else:
        allowance = asked.max_stale
        reusable = reusable and not forbidden and allowance is not None and staleness <= allowance
    revalidate_window = response.stale_while_revalidate
    error_window = asked.stale_if_error if asked.has("stale-if-error") else response.stale_if_error
    stale_ok = not fresh and not forbidden
    return Freshness(
        lifetime=lifetime,
        age=age,
        fresh=fresh,
        reusable=reusable,
        stale_while_revalidate=stale_ok
        and not asked.no_cache
        and revalidate_window is not None
        and staleness <= revalidate_window,
        stale_if_error=stale_ok and error_window is not None and staleness <= error_window,
    )


def may_store(
    response: CacheControl,
    *,
    shared: bool = False,
    authorized: bool = False,
    understood_status: bool = False,
) -> bool:
    """Whether the response directives let a cache store the response (RFC 9111 3 and 3.5).

    ``authorized`` is True when the request carried Authorization; ``understood_status``
    when the cache implements the caching rules of the response's status code, which is
    what ``must-understand`` asks for and what lets it override ``no-store``. A qualified
    ``private`` still allows a shared cache to store the response without those fields.
    Only directives are judged: method, status and freshness rules stay with the caller.
    """
    if response.must_understand:
        if not understood_status:
            return False
    elif response.no_store:
        return False
    qualifier = response.get("private")
    unqualified = not isinstance(qualifier, str) or field_names(qualifier) is None
    if shared and response.private and unqualified:
        return False
    if shared and authorized:
        return response.must_revalidate or response.public or response.has("s-maxage")
    return True
