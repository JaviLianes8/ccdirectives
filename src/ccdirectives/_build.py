"""Build a Cache-Control field value from a CacheControl structure."""

from __future__ import annotations

from ._access import DirectiveValue
from ._chars import DELTA_MAX, delta_seconds, field_names, is_token
from ._checks import is_a, shown, type_name
from ._errors import CacheControlError
from ._model import CacheControl, checked_items
from ._registry import DELTA_DIRECTIVES, FIELD_DIRECTIVES, argument_rule


def build(cache_control: CacheControl) -> str:
    """Render a CacheControl as a field value, refusing anything the grammar cannot carry.

    Bare flags are written alone and ``False`` is left out. delta-seconds go out in token
    form and ``no-cache`` and ``private`` field lists in quoted-string form, as RFC 9111
    section 5.2 asks of senders; other arguments are quoted only when they are not tokens.
    Names that are not tokens, negative numbers, non-numeric or missing delta-seconds,
    arguments on registered directives that take none, control characters and non-ASCII
    text raise ``CacheControlError``, so the output always passes ``parse(strict=True)``.

    >>> from ccdirectives import CacheControl
    >>> build(CacheControl({"max-age": 3600, "private": "Set-Cookie", "public": False}))
    'max-age=3600, private="Set-Cookie"'
    >>> build(CacheControl({"x-note": "two words", "max-age": "0060"}))
    'x-note="two words", max-age=60'
    """
    if not is_a(cache_control, CacheControl):
        raise TypeError(f"build takes a CacheControl, not {type_name(cache_control)}")
    parts: list[str] = []
    for name, value in checked_items(cache_control):
        if value is False:
            continue
        if not is_token(name):
            raise CacheControlError(f"directive name {shown(name)} is not a token")
        rule = argument_rule(name, None)
        if value is True:
            if rule == "delta":
                raise CacheControlError(f"{shown(name)} needs delta-seconds")
            parts.append(name)
        elif rule in ("none", "ignored"):
            raise CacheControlError(f"{shown(name)} takes no argument")
        else:
            parts.append(f"{name}={_argument(name, value)}")
    return ", ".join(parts)


def _argument(name: str, value: DirectiveValue) -> str:
    if isinstance(value, int):
        if value < 0:
            raise CacheControlError(f"{shown(name)} cannot be negative")
        # RFC 9111 section 1.2.2: anything past 2^31 means the same, so write the cap.
        if name in DELTA_DIRECTIVES:
            return str(min(value, DELTA_MAX))
        try:
            return str(value)
        except ValueError:
            # Past the interpreter's limit on int to str conversion (4300 digits by default).
            raise CacheControlError(f"{shown(name)} argument is too large to write") from None
    if name in DELTA_DIRECTIVES:
        seconds = delta_seconds(value)
        if seconds is None:
            raise CacheControlError(f"{shown(name)} needs delta-seconds")
        return str(seconds)
    for char in value:
        code = ord(char)
        if code > 0x7E or (code < 0x20 and char != "\t") or code == 0x7F:
            raise CacheControlError(f"{shown(name)} argument has a character a header cannot carry")
    if name in FIELD_DIRECTIVES:
        if field_names(value) is None:
            raise CacheControlError(f"{shown(name)} argument is not a list of field names")
        return _quote(value)
    return value if is_token(value) else _quote(value)


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
