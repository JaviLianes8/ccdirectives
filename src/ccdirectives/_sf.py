"""Structured field dictionaries and bare items, parsed as RFC 9651 section 4.2 describes."""

from __future__ import annotations

import base64
import binascii
from decimal import Decimal

from ._chars import DIGITS, TCHAR


class Token(str):
    """A structured field Token, told apart from a String."""


class DisplayString(str):
    """A structured field Display String."""


class Date(int):
    """A structured field Date, in seconds since the epoch."""


class StructuredError(ValueError):
    """The text is not a valid structured field."""


BareItem = int | Decimal | str | bytes | bool
Params = dict[str, BareItem]
Member = tuple[BareItem | list[tuple[BareItem, Params]], Params]

_LCALPHA = frozenset("abcdefghijklmnopqrstuvwxyz")
_KEY = _LCALPHA | DIGITS | frozenset("_-.*")
_ALPHA = _LCALPHA | frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_HEX = frozenset("0123456789abcdef")


class Reader:
    """A cursor over the field value; every parse step consumes what it reads."""

    def __init__(self, text: str) -> None:
        if not text.isascii():
            raise StructuredError("structured fields are ASCII")
        self.text = text
        self.pos = 0

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def take(self) -> str:
        char = self.peek()
        self.pos += 1
        return char

    def skip(self, chars: str) -> None:
        while self.peek() and self.peek() in chars:
            self.pos += 1

    def done(self) -> bool:
        return self.pos >= len(self.text)


def parse_key(r: Reader) -> str:
    first = r.peek()
    if not first or (first not in _LCALPHA and first != "*"):
        raise StructuredError(f"a key cannot start with {r.peek()!r}")
    start = r.pos
    while r.peek() and r.peek() in _KEY:
        r.pos += 1
    return r.text[start : r.pos]


def parse_params(r: Reader) -> Params:
    params: Params = {}
    while r.peek() == ";":
        r.pos += 1
        r.skip(" ")
        key = parse_key(r)
        value: BareItem = True
        if r.peek() == "=":
            r.pos += 1
            value = parse_bare_item(r)
        params[key] = value
    return params


def parse_bare_item(r: Reader) -> BareItem:
    char = r.peek()
    if char == "-" or (char and char in DIGITS):
        return _number(r)
    if char == '"':
        return _string(r)
    if char and (char in _ALPHA or char == "*"):
        start = r.pos
        while r.peek() and (r.peek() in TCHAR or r.peek() in ":/"):
            r.pos += 1
        return Token(r.text[start : r.pos])
    if char == ":":
        return _bytes(r)
    if char == "?":
        r.pos += 1
        flag = r.take()
        if flag not in ("0", "1"):
            raise StructuredError("a Boolean is ?0 or ?1")
        return flag == "1"
    if char == "@":
        r.pos += 1
        value = _number(r)
        if isinstance(value, Decimal):
            raise StructuredError("a Date is an Integer")
        return Date(value)
    if char == "%":
        return _display(r)
    raise StructuredError(f"no item starts with {char!r}")


def _number(r: Reader) -> int | Decimal:
    sign = -1 if r.peek() == "-" else 1
    if sign < 0:
        r.pos += 1
    if not r.peek() or r.peek() not in DIGITS:
        raise StructuredError("a number needs a digit")
    start = r.pos
    while r.peek() and r.peek() in DIGITS:
        r.pos += 1
    whole = r.text[start : r.pos]
    if r.peek() != ".":
        if len(whole) > 15:
            raise StructuredError("an Integer has at most 15 digits")
        return sign * int(whole)
    r.pos += 1
    begin = r.pos
    while r.peek() and r.peek() in DIGITS:
        r.pos += 1
    fraction = r.text[begin : r.pos]
    if len(whole) > 12 or not fraction or len(fraction) > 3:
        raise StructuredError("a Decimal has 1 to 12 digits, a point and 1 to 3 digits")
    return sign * Decimal(f"{whole}.{fraction}")


def _string(r: Reader) -> str:
    r.pos += 1
    out: list[str] = []
    while not r.done():
        char = r.take()
        if char == "\\":
            escaped = r.take()
            if escaped not in ('"', "\\"):
                raise StructuredError("only a quote or a backslash may be escaped")
            out.append(escaped)
        elif char == '"':
            return "".join(out)
        elif not " " <= char <= "~":
            raise StructuredError("a String holds visible ASCII and spaces")
        else:
            out.append(char)
    raise StructuredError("unterminated String")


def _bytes(r: Reader) -> bytes:
    r.pos += 1
    end = r.text.find(":", r.pos)
    if end < 0:
        raise StructuredError("unterminated Byte Sequence")
    content = r.text[r.pos : end]
    r.pos = end + 1
    try:
        # RFC 9651 asks parsers to accept missing padding and non-zero pad bits.
        bare = content.rstrip("=")
        return base64.b64decode(bare + "=" * (-len(bare) % 4), validate=True)
    except binascii.Error as error:
        raise StructuredError("a Byte Sequence is base64") from error


def _display(r: Reader) -> DisplayString:
    if r.text[r.pos : r.pos + 2] != '%"':
        raise StructuredError('a Display String starts with %"')
    r.pos += 2
    octets = bytearray()
    while not r.done():
        char = r.take()
        if not " " <= char <= "~":
            raise StructuredError("a Display String holds visible ASCII and spaces")
        if char == "%":
            pair = r.text[r.pos : r.pos + 2]
            r.pos += 2
            if len(pair) != 2 or any(digit not in _HEX for digit in pair):
                raise StructuredError("a Display String escape is two lower-case hex digits")
            octets.append(int(pair, 16))
        elif char == '"':
            try:
                return DisplayString(octets.decode("utf-8"))
            except UnicodeDecodeError as error:
                raise StructuredError("a Display String is UTF-8") from error
        else:
            octets.append(ord(char))
    raise StructuredError("unterminated Display String")
