"""Targeted cache control fields such as CDN-Cache-Control (RFC 9213)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from ._build import build
from ._chars import DELTA_MAX, ascii_lower, field_names
from ._errors import CacheControlError
from ._model import CacheControl, DirectiveValue
from ._parse import parse
from ._registry import DELTA_DIRECTIVES, FIELD_DIRECTIVES, argument_rule
from ._sf import BareItem, Date, DisplayString, StructuredError, Token
from ._sfdict import is_sf_token, parse_dictionary, serialize_dictionary

# A malformed value on one of these must not erase it: dropping it would let a cache store or
# reuse what the origin meant to restrict, so the directive is kept in its unqualified form.
_RESTRICTIVE = frozenset(
    {"no-store", "no-cache", "private", "must-revalidate", "proxy-revalidate", "no-transform"}
)

Headers = Mapping[str, str] | Iterable[tuple[str, str]]


def parse_targeted(value: str | Iterable[str]) -> CacheControl | None:
    """Parse a targeted field as a structured field Dictionary (RFC 9213 section 2.1).

    Returns None when the field is empty or does not parse, which RFC 9213 says a cache
    treats as if the field were absent. Booleans, Integers, Strings and Tokens map to
    directive values and parameters are ignored. A member whose value breaks the rules of
    its directive (a Decimal ``max-age``, a String ``s-maxage``) is left out, except that
    a restrictive directive such as ``no-store`` or ``private`` is kept in unqualified form.
    """
    text = value if isinstance(value, str) else ", ".join(value)
    try:
        members = parse_dictionary(text)
    except StructuredError:
        return None
    if not members:
        return None
    directives: dict[str, DirectiveValue] = {}
    for key, (item, _params) in members.items():
        mapped = _map(key, item) if not isinstance(item, list) else None
        if mapped is None and key in _RESTRICTIVE:
            mapped = True
        if mapped is not None:
            directives[key] = mapped
    return CacheControl(directives)


def _map(key: str, item: BareItem) -> DirectiveValue | None:
    rule = argument_rule(key, "response")
    if rule == "ignored":
        return True
    if isinstance(item, (bytes, Date, DisplayString)) or item is False:
        return None
    if item is True:
        return None if rule == "delta" else True
    if rule == "delta":
        return min(item, DELTA_MAX) if isinstance(item, int) and item >= 0 else None
    if rule == "none":
        return None
    if rule == "fields":
        quoted = isinstance(item, str) and not isinstance(item, Token)
        return str(item) if quoted and field_names(str(item)) is not None else None
    if isinstance(item, Decimal):
        return str(item)
    return str(item) if isinstance(item, str) else item


def build_targeted(cache_control: CacheControl) -> str:
    """Serialize a CacheControl as a targeted field value (a structured field Dictionary).

    The directive rules of ``build`` apply. Field lists are written as Strings, numbers as
    Integers, other text as a Token when it is one and as a String otherwise. An empty
    result means the field should not be sent. Names that are not structured field keys
    and text a String cannot hold raise ``CacheControlError``.
    """
    build(cache_control)
    members: dict[str, BareItem] = {}
    for name, value in cache_control.directives.items():
        if value is False:
            continue
        if isinstance(value, str) and name in DELTA_DIRECTIVES:
            members[name] = min(int(value), DELTA_MAX)
        elif isinstance(value, str) and name not in FIELD_DIRECTIVES and is_sf_token(value):
            members[name] = Token(value)
        elif isinstance(value, int) and not isinstance(value, bool) and name in DELTA_DIRECTIVES:
            members[name] = min(value, DELTA_MAX)
        else:
            members[name] = value
    try:
        return serialize_dictionary(members)
    except StructuredError as error:
        raise CacheControlError(str(error)) from error


def select(
    headers: Headers, targets: Iterable[str] = ("CDN-Cache-Control",)
) -> tuple[str, CacheControl]:
    """Pick the policy a cache with this target list follows (RFC 9213 section 2.2).

    The first target field present with a valid, non-empty value wins; otherwise the
    ``Cache-Control`` field is parsed. Returns the chosen field name and its directives.
    When a targeted field wins, the response's ``Expires`` no longer applies either.
    """
    pairs = headers.items() if isinstance(headers, Mapping) else headers
    lines: dict[str, list[str]] = {}
    for name, value in pairs:
        lines.setdefault(ascii_lower(name), []).append(value)
    for target in targets:
        values = lines.get(ascii_lower(target))
        if values:
            chosen = parse_targeted(values)
            if chosen is not None:
                return target, chosen
    return "Cache-Control", parse(lines.get("cache-control", []))
