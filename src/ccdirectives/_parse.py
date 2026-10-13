"""Parse a Cache-Control field value into a CacheControl structure."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from ._chars import ascii_lower, delta_seconds, field_names
from ._errors import CacheControlError
from ._model import CacheControl, DirectiveValue
from ._registry import DELTA_DIRECTIVES, argument_rule
from ._scan import Item, scan

Context = Literal["request", "response"]

_UNSAFE = {0x00: " ", 0x0A: " ", 0x0D: " "}


def parse(
    header: str | Iterable[str], *, strict: bool = False, context: Context | None = None
) -> CacheControl:
    """Parse a Cache-Control field value, or the values of several field lines.

    Directive names are lower-cased, delta-seconds become ints capped at 2147483648,
    quoted arguments are unescaped, and the first occurrence of a repeated directive wins
    (RFC 9111 section 4.2.1); repeated names are listed in ``duplicates``. The lenient
    default never raises on content: what it cannot read is skipped. With ``strict=True``
    anything outside the grammar or the directive rules raises ``CacheControlError``.
    ``context`` selects the request or the response rules for registered directives.
    """
    if context not in (None, "request", "response"):
        raise ValueError(f"context must be 'request', 'response' or None, not {context!r}")
    text = _join(header)
    if strict:
        _refuse_controls(text)
    else:
        # RFC 9110 section 5.5: CR, LF and NUL are rejected or replaced with SP.
        text = text.translate(_UNSAFE)
    directives: dict[str, DirectiveValue] = {}
    duplicates: set[str] = set()
    for item in scan(text, strict):
        name = ascii_lower(item.name)
        if name in directives:
            if strict:
                raise CacheControlError(f"repeated directive {name!r}", item.offset)
            duplicates.add(name)
            continue
        if strict:
            _check(name, item, context)
        directives[name] = _value(name, item.value)
    return CacheControl(directives, frozenset(duplicates))


def _join(header: str | Iterable[str]) -> str:
    if isinstance(header, str):
        return header
    if isinstance(header, (bytes, bytearray)):
        raise TypeError("decode the header value to str first (ISO-8859-1 keeps every octet)")
    lines = list(header)
    for line in lines:
        if not isinstance(line, str):
            raise TypeError(f"field lines must be str, not {type(line).__name__}")
    # RFC 9110 section 5.3: field lines combine into one value separated by commas.
    return ", ".join(lines)


def _refuse_controls(text: str) -> None:
    for offset, char in enumerate(text):
        code = ord(char)
        if (code < 0x20 and char != "\t") or code == 0x7F:
            raise CacheControlError("control character in the field value", offset)


def _value(name: str, raw: str | None) -> DirectiveValue:
    if raw is None:
        return True
    if name in DELTA_DIRECTIVES:
        seconds = delta_seconds(raw)
        if seconds is not None:
            return seconds
    return raw


def _check(name: str, item: Item, context: Context | None) -> None:
    rule = argument_rule(name, context)
    value = item.value
    if rule == "none" and value is not None:
        raise CacheControlError(f"{name!r} takes no argument", item.offset)
    if rule == "delta" and value is None:
        raise CacheControlError(f"{name!r} needs delta-seconds", item.offset)
    if rule in ("delta", "optional-delta") and value is not None and delta_seconds(value) is None:
        raise CacheControlError(f"{name!r} argument is not delta-seconds", item.offset)
    if rule == "fields" and value is not None and field_names(value) is None:
        raise CacheControlError(f"{name!r} argument is not a list of field names", item.offset)
