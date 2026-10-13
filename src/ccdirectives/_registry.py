"""The registered cache directives, which direction each applies to, and its argument."""

from __future__ import annotations

from typing import Literal

Argument = Literal["none", "delta", "optional-delta", "fields", "ignored"]

# Name: (request argument or None when not a request directive, response argument or None).
# Sources: RFC 9111 section 5.2, RFC 5861 sections 3 and 4, RFC 8246 section 2, and the IANA
# HTTP Cache Directive Registry.
_TABLE: dict[str, tuple[Argument | None, Argument | None]] = {
    "immutable": (None, "ignored"),
    "max-age": ("delta", "delta"),
    "max-stale": ("optional-delta", None),
    "min-fresh": ("delta", None),
    "must-revalidate": (None, "none"),
    "must-understand": (None, "none"),
    "no-cache": ("none", "fields"),
    "no-store": ("none", "none"),
    "no-transform": ("none", "none"),
    "only-if-cached": ("none", None),
    "private": (None, "fields"),
    "proxy-revalidate": (None, "none"),
    "public": (None, "none"),
    "s-maxage": (None, "delta"),
    "stale-if-error": ("delta", "delta"),
    "stale-while-revalidate": (None, "delta"),
}

REGISTERED_DIRECTIVES: frozenset[str] = frozenset(_TABLE)
"""Every name in the IANA HTTP Cache Directive Registry."""

REQUEST_DIRECTIVES: frozenset[str] = frozenset(n for n, (req, _) in _TABLE.items() if req)
"""Registered directives defined for requests."""

RESPONSE_DIRECTIVES: frozenset[str] = frozenset(n for n, (_, res) in _TABLE.items() if res)
"""Registered directives defined for responses."""

DELTA_DIRECTIVES: frozenset[str] = frozenset(
    name for name, pair in _TABLE.items() if {"delta", "optional-delta"} & set(pair)
)
FIELD_DIRECTIVES: frozenset[str] = frozenset({"no-cache", "private"})


def argument_rule(name: str, context: str | None) -> Argument | None:
    """The argument rule for ``name`` in ``context``, or None for an unregistered name.

    Without a context the most permissive rule of the two directions applies, so a header
    of unknown direction is never rejected for something one side allows.
    """
    pair = _TABLE.get(name)
    if pair is None:
        return None
    request, response = pair
    if context == "request":
        return request
    if context == "response":
        return response
    rules = {rule for rule in pair if rule is not None}
    for loose in ("fields", "ignored", "optional-delta", "delta", "none"):
        if loose in rules:
            return loose
    return None
