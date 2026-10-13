"""Split a Cache-Control field value into directives on the RFC 9111 section 5.2 grammar."""

from __future__ import annotations

from typing import NamedTuple

from ._chars import OWS, TCHAR, is_qdtext, is_quotable
from ._errors import CacheControlError


class Item(NamedTuple):
    name: str
    value: str | None
    offset: int


def scan(text: str, strict: bool) -> list[Item]:
    """Read ``#cache-directive``; lenient mode skips what it cannot read, strict mode raises."""
    items: list[Item] = []
    length = len(text)
    index = 0
    while index < length:
        if text[index] in OWS or text[index] == ",":
            index += 1
            continue
        item, index = _directive(text, index, strict)
        if item is not None:
            items.append(item)
    return items


def _fail(strict: bool, message: str, offset: int) -> None:
    if strict:
        raise CacheControlError(message, offset)


def _next_comma(text: str, index: int) -> int:
    found = text.find(",", index)
    return len(text) if found < 0 else found


def _skip(text: str, index: int, chars: str) -> int:
    while index < len(text) and text[index] in chars:
        index += 1
    return index


def _token_end(text: str, index: int) -> int:
    while index < len(text) and text[index] in TCHAR:
        index += 1
    return index


def _directive(text: str, start: int, strict: bool) -> tuple[Item | None, int]:
    end = _token_end(text, start)
    if end == start:
        _fail(strict, "expected a directive name", start)
        return None, _next_comma(text, start)
    name = text[start:end]
    after = _skip(text, end, OWS)
    if after < len(text) and text[after] == "=":
        if after != end:
            _fail(strict, "whitespace before '='", end)
        return _argument(text, start, name, after + 1, strict)
    if after < len(text) and text[after] != ",":
        _fail(strict, "expected ',' after a directive", after)
        return None, _next_comma(text, after)
    return Item(name, None, start), after


def _argument(text: str, start: int, name: str, index: int, strict: bool) -> tuple[Item, int]:
    begin = _skip(text, index, OWS)
    if begin != index:
        _fail(strict, "whitespace after '='", index)
    if begin < len(text) and text[begin] == '"':
        value, end = _quoted(text, begin, strict)
        if value is None:
            comma = _next_comma(text, begin)
            return Item(name, text[begin:comma].strip(OWS), start), comma
    else:
        end = _token_end(text, begin)
        value = text[begin:end]
        if not value:
            _fail(strict, "expected a token or a quoted string after '='", begin)
    after = _skip(text, end, OWS)
    if after < len(text) and text[after] != ",":
        _fail(strict, "expected ',' after a directive", after)
        comma = _next_comma(text, after)
        if not text[begin:end].startswith('"'):
            # Keep the whole unreadable argument visible rather than a misleading prefix.
            value = text[begin:comma].strip(OWS)
        return Item(name, value, start), comma
    return Item(name, value, start), after


def _quoted(text: str, start: int, strict: bool) -> tuple[str | None, int]:
    """Unescape the quoted-string at ``start``; (None, start) when it never closes."""
    out: list[str] = []
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == '"':
            return "".join(out), index + 1
        if char == "\\":
            if index + 1 >= len(text):
                break
            if not is_quotable(text[index + 1]):
                _fail(strict, "character not allowed after a backslash", index + 1)
            out.append(text[index + 1])
            index += 2
            continue
        if not is_qdtext(char):
            _fail(strict, "character not allowed in a quoted string", index)
        out.append(char)
        index += 1
    _fail(strict, "unterminated quoted string", start)
    return None, start
