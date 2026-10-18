"""Targeted cache control fields such as CDN-Cache-Control (RFC 9213)."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Protocol, runtime_checkable

from ._access import DirectiveValue
from ._build import build
from ._chars import DELTA_MAX, ascii_lower, delta_seconds, field_names
from ._checks import is_a, plain_str, shown, type_name
from ._errors import CacheControlError
from ._model import CacheControl, checked_items
from ._parse import parse
from ._registry import DELTA_DIRECTIVES, FIELD_DIRECTIVES, argument_rule
from ._sf import BareItem, Date, DisplayString, StructuredError, Token
from ._sfdict import is_sf_token, parse_dictionary, serialize_dictionary

# A malformed value on one of these must not erase it: dropping it would let a cache store or
# reuse what the origin meant to restrict, so the directive is kept in its unqualified form.
_RESTRICTIVE = frozenset(
    {"no-store", "no-cache", "private", "must-revalidate", "proxy-revalidate", "no-transform"}
    # s-maxage also forbids stale use in a shared cache (RFC 9111 section 5.2.2.10).
    | {"s-maxage"}
)


# A structured field Integer has at most 15 digits (RFC 9651 section 3.3.1).
_SF_INT_MAX = 999_999_999_999_999


@runtime_checkable
class HasItems(Protocol):
    """A mapping, or a header object such as http.client.HTTPMessage that repeats names."""

    def items(self) -> Iterable[tuple[str, str]]: ...


Headers = HasItems | Iterable[tuple[str, str]]


def parse_targeted(value: str | Iterable[str]) -> CacheControl | None:
    """Parse a targeted field as a structured field Dictionary (RFC 9213 section 2.1).

    Returns None when the field is empty or does not parse, which RFC 9213 says a cache
    treats as if the field were absent. Booleans, Integers, Strings and Tokens map to
    directive values and parameters are ignored. A member whose value breaks the rules of
    its directive (a Decimal ``max-age``, a String ``s-maxage``) is left out, except that
    a restrictive directive such as ``no-store`` or ``private`` is kept in unqualified form.

    >>> parse_targeted('max-age=600, private="Set-Cookie"').directives
    {'max-age': 600, 'private': 'Set-Cookie'}
    >>> parse_targeted("max-age=1.5, no-store").directives
    {'no-store': True}
    >>> parse_targeted("max-age=") is None
    True
    """
    if is_a(value, (bytes, bytearray, memoryview)):
        raise TypeError("decode the field value to str first")
    if is_a(value, str):
        text = str.__str__(value)
    elif issubclass(type(value), Iterable):
        text = ", ".join([plain_str("field lines", line) for line in value])
    else:
        raise TypeError(f"value must be str or an iterable of str, not {type_name(value)}")
    try:
        members = parse_dictionary(text)
    except StructuredError:
        return None
    if not members:
        return None
    directives: dict[str, DirectiveValue] = {}
    for key, (item, _params) in members.items():
        mapped = _map(key, item) if not is_a(item, list) else None
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
        return min(item, DELTA_MAX) if is_a(item, int) and item >= 0 else None
    if rule == "none":
        return None
    if rule == "fields":
        quoted = is_a(item, str) and not is_a(item, Token)
        return str(item) if quoted and field_names(str(item)) is not None else None
    if is_a(item, Decimal):
        return str(item)
    return str(item) if is_a(item, str) else item


def build_targeted(cache_control: CacheControl) -> str:
    """Serialize a CacheControl as a targeted field value (a structured field Dictionary).

    The directive rules of ``build`` apply, and an extension integer may have at most 15
    digits (the limit of a structured field Integer). Field lists are written as Strings,
    numbers as Integers, other text as a Token when it is one and as a String otherwise. An empty
    result means the field should not be sent. Names that are not structured field keys
    and text a String cannot hold raise ``CacheControlError``.

    >>> from ccdirectives import CacheControl
    >>> build_targeted(CacheControl({"max-age": 600, "private": "Set-Cookie", "x": "tok"}))
    'max-age=600, private="Set-Cookie", x=tok'
    """
    if not is_a(cache_control, CacheControl):
        raise TypeError(f"build_targeted takes a CacheControl, not {type_name(cache_control)}")
    build(cache_control)
    members: dict[str, BareItem] = {}
    for name, value in checked_items(cache_control):
        if value is False:
            continue
        if is_a(value, str) and name in DELTA_DIRECTIVES:
            members[name] = delta_seconds(value) or 0
        elif is_a(value, str) and name not in FIELD_DIRECTIVES and is_sf_token(value):
            members[name] = Token(value)
        elif is_a(value, int) and not is_a(value, bool) and name in DELTA_DIRECTIVES:
            members[name] = min(value, DELTA_MAX)
        elif is_a(value, int) and not is_a(value, bool) and value > _SF_INT_MAX:
            raise CacheControlError(f"{shown(name)} argument has more than 15 digits")
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

    >>> headers = {"Cache-Control": "max-age=60", "CDN-Cache-Control": "max-age=600"}
    >>> name, policy = select(headers)
    >>> name, policy.max_age
    ('CDN-Cache-Control', 600)
    >>> select(headers, [])[1].max_age
    60
    """
    if is_a(targets, (str, bytes)):
        raise TypeError("targets is a list of field names, not one string")
    wanted = [plain_str("target names", target) for target in targets]
    if is_a(headers, (str, bytes)):
        raise TypeError("headers is a mapping or a list of (name, value) pairs")
    pairs = headers.items() if isinstance(headers, HasItems) else headers
    lines: dict[str, list[str]] = {}
    for pair in pairs:
        # A two-character string or a two-key dict would unpack too: only tuples and lists.
        if is_a(pair, tuple):
            items: tuple[object, ...] | list[object] = tuple.__getitem__(pair, slice(None))
        elif is_a(pair, list):
            items = list.__getitem__(pair, slice(None))
        else:
            items = ()
        if len(items) != 2:
            raise TypeError("headers holds (name, value) pairs")
        name, value = items
        lines.setdefault(ascii_lower(plain_str("field names", name)), []).append(
            plain_str("field values", value)
        )
    for target in wanted:
        values = lines.get(ascii_lower(target))
        if values:
            chosen = parse_targeted(values)
            if chosen is not None:
                return target, chosen
    return "Cache-Control", parse(lines.get("cache-control", []))
