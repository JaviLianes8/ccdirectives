"""Structured field dictionaries: RFC 9651 sections 4.2.2 (parsing) and 4.1.2 (serializing)."""

from __future__ import annotations

from decimal import Decimal

from ._chars import TCHAR
from ._checks import shown, type_name
from ._sf import (
    BareItem,
    Member,
    Params,
    Reader,
    StructuredError,
    Token,
    parse_bare_item,
    parse_key,
    parse_params,
)

_OWS = " \t"


def parse_item(r: Reader) -> tuple[BareItem, Params]:
    return parse_bare_item(r), parse_params(r)


def _inner_list(r: Reader) -> Member:
    r.pos += 1
    items: list[tuple[BareItem, Params]] = []
    while not r.done():
        r.skip(" ")
        if r.peek() == ")":
            r.pos += 1
            return items, parse_params(r)
        items.append(parse_item(r))
        if r.peek() not in (" ", ")"):
            raise StructuredError("inner list members are separated by spaces")
    raise StructuredError("unterminated inner list")


def parse_dictionary(text: str) -> dict[str, Member]:
    """Parse a whole field value as a Dictionary; the last of repeated keys wins."""
    r = Reader(text)
    r.skip(" ")
    members: dict[str, Member] = {}
    while not r.done():
        key = parse_key(r)
        member: Member
        if r.peek() == "=":
            r.pos += 1
            member = _inner_list(r) if r.peek() == "(" else parse_item(r)
        else:
            member = (True, parse_params(r))
        members[key] = member
        r.skip(_OWS)
        if r.done():
            break
        if r.take() != ",":
            raise StructuredError(f"expected ',' at offset {r.pos - 1}")
        r.skip(_OWS)
        if r.done():
            raise StructuredError("trailing comma")
    r.skip(" ")
    if not r.done():
        raise StructuredError("unexpected text after the dictionary")
    return members


def serialize_key(key: str) -> str:
    if not key or not (key[0].islower() or key[0] == "*") or not key.isascii():
        raise StructuredError(f"{shown(key)} is not a structured field key")
    if any(not (char.islower() or char.isdigit() or char in "_-.*") for char in key):
        raise StructuredError(f"{shown(key)} is not a structured field key")
    return key


def is_sf_token(value: str) -> bool:
    """True when ``value`` can be written as a structured field Token."""
    if not value or not (value[0].isascii() and (value[0].isalpha() or value[0] == "*")):
        return False
    return all(char in TCHAR or char in ":/" for char in value[1:])


def serialize_bare_item(value: BareItem) -> str:
    """Serialize the item types a cache directive can hold: Boolean, Integer, String, Token."""
    if isinstance(value, bool):
        return "?1" if value else "?0"
    if isinstance(value, int):
        if not -999_999_999_999_999 <= value <= 999_999_999_999_999:
            raise StructuredError("an Integer has at most 15 digits")
        return str(value)
    if isinstance(value, Token):
        if not is_sf_token(value):
            raise StructuredError(f"{shown(value)} is not a Token")
        return str(value)
    if isinstance(value, str):
        if any(not " " <= char <= "~" for char in value):
            raise StructuredError("a String holds visible ASCII and spaces")
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, Decimal):
        raise StructuredError("cache directives never hold a Decimal")
    raise StructuredError(f"cannot serialize {type_name(value)}")


def serialize_dictionary(members: dict[str, BareItem]) -> str:
    """Serialize a Dictionary of bare items without parameters."""
    parts: list[str] = []
    for key, value in members.items():
        name = serialize_key(key)
        parts.append(name if value is True else f"{name}={serialize_bare_item(value)}")
    return ", ".join(parts)
