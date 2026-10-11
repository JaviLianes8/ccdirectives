"""Parse a Cache-Control header into a CacheControl structure."""

from __future__ import annotations

from ._model import NUMERIC_DIRECTIVES, CacheControl, DirectiveValue


def parse(header: str) -> CacheControl:
    """Parse a Cache-Control header value, tolerating malformed input.

    Directive names are lowercased, numeric directives become ints, quoted
    arguments are unescaped, and anything unrecognised is preserved verbatim.
    """
    directives: dict[str, DirectiveValue] = {}
    for token in _split(header):
        name, sep, raw = token.partition("=")
        key = name.strip().lower()
        if not key:
            continue
        directives[key] = _value(key, raw.strip()) if sep else True
    return CacheControl(directives)


def _value(name: str, raw: str) -> DirectiveValue:
    text = _unquote(raw)
    if name in NUMERIC_DIRECTIVES:
        try:
            return int(text)
        except ValueError:
            return text
    return text


def _unquote(raw: str) -> str:
    if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        return raw
    out: list[str] = []
    escaped = False
    for char in raw[1:-1]:
        if escaped:
            out.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            out.append(char)
    return "".join(out)


def _split(header: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    in_quotes = False
    escaped = False
    for char in header:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\" and in_quotes:
            current.append(char)
            escaped = True
        elif char == '"':
            in_quotes = not in_quotes
            current.append(char)
        elif char == "," and not in_quotes:
            tokens.append("".join(current))
            current = []
        else:
            current.append(char)
    tokens.append("".join(current))
    return [token for token in tokens if token.strip()]
