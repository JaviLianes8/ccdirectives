"""Seeded random structures and headers: build and parse agree, and nothing else escapes."""

from __future__ import annotations

import random

from ccdirectives import (
    CacheControl,
    CacheControlError,
    DirectiveValue,
    build,
    build_targeted,
    parse,
    parse_targeted,
)
from ccdirectives._registry import argument_rule

ROUNDS = 3000
NAME_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-._*"
TEXT_CHARS = "".join(chr(c) for c in range(0x20, 0x7F))
FIELDS = ["set-cookie", "etag", "x-token", "authorization"]


def _value(rng: random.Random, name: str) -> DirectiveValue:
    rule = argument_rule(name, None)
    if rule == "delta":
        return rng.choice([0, 1, 60, 2147483647, 2147483648])
    if rule == "optional-delta":
        options: list[DirectiveValue] = [True, 0, 30]
        return rng.choice(options)
    if rule == "none":
        return True
    if rule == "fields":
        listed: list[DirectiveValue] = [True, ", ".join(rng.sample(FIELDS, rng.randint(1, 3)))]
        return rng.choice(listed)
    choice = rng.randrange(3)
    if choice == 0:
        return True
    if choice == 1:
        return rng.randint(0, 10**9)
    return "".join(rng.choice(TEXT_CHARS) for _ in range(rng.randint(1, 12)))


def _structure(rng: random.Random) -> CacheControl:
    registered = ["max-age", "s-maxage", "no-cache", "private", "no-store", "max-stale"]
    names = rng.sample(registered, rng.randint(0, 4))
    for _ in range(rng.randint(0, 3)):
        first = rng.choice("abcdefghijklmnopqrstuvwxyz")
        names.append(first + "".join(rng.choice(NAME_CHARS) for _ in range(rng.randint(0, 6))))
    return CacheControl({name: _value(rng, name) for name in names})


def _text_numbers(cc: CacheControl) -> CacheControl:
    # An extension's meaning is unknown, so parse keeps its digits as text.
    known = {"max-age", "s-maxage", "max-stale"}
    items = cc.items()
    return CacheControl({k: v if k in known or v is True else str(v) for k, v in items})


def test_build_then_parse_gives_back_the_structure() -> None:
    rng = random.Random(9111)
    for _ in range(ROUNDS):
        cc = _text_numbers(_structure(rng))
        text = build(cc)
        assert parse(text, strict=True) == cc, text
        assert parse(text) == cc, text


def test_build_targeted_then_parse_targeted_gives_back_the_structure() -> None:
    rng = random.Random(9213)
    for _ in range(ROUNDS):
        cc = _structure(rng)
        cc.directives = {k: v for k, v in cc.directives.items() if v != "" and "\t" not in str(v)}
        text = build_targeted(cc)
        assert (parse_targeted(text) or CacheControl()) == cc, text


def test_random_headers_never_raise_anything_unexpected() -> None:
    rng = random.Random(9110)
    alphabet = 'abcm-x=,;" \t\\0123456789\r\n\x00\x7f\xe9{}'
    for _ in range(ROUNDS):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))
        lenient = parse(text)
        assert all(name and name == name.lower() for name in lenient)
        try:
            strict = parse(text, strict=True)
        except CacheControlError as error:
            assert error.offset is not None and 0 <= error.offset <= len(text)
        else:
            assert strict.directives == lenient.directives and not strict.duplicates
        parse_targeted(text)
