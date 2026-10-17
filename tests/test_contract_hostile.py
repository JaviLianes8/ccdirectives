"""Hostile input: bounded messages, plain values from subclasses, finite times, linear time."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from typing import Any

import pytest

from ccdirectives import (
    DELTA_MAX,
    CacheControl,
    CacheControlError,
    build,
    build_targeted,
    current_age,
    freshness_lifetime,
    parse,
    parse_targeted,
)
from ccdirectives._checks import type_name
from ccdirectives._head import head_fields

HUGE = "n" * 100_000
MESSAGES: list[Callable[[], object]] = [
    lambda: parse(f"{HUGE}, {HUGE}", strict=True),
    lambda: parse(f"{HUGE}-x=1, no-store=1", strict=True, context="response"),
    lambda: parse(f"max-age={HUGE}", strict=True),
    lambda: parse(f'private="{HUGE} x"', strict=True, context="response"),
    lambda: build(CacheControl({f"{HUGE} x": True})),
    lambda: build(CacheControl({"max-age": HUGE})),
    lambda: build(CacheControl({"no-cache": f"{HUGE} x"})),
    lambda: build(CacheControl({HUGE: f"{HUGE}\n"})),
    lambda: build_targeted(CacheControl({f"1{HUGE}": True})),
    lambda: CacheControl({HUGE: 1.5}),  # type: ignore[dict-item]
]


@pytest.mark.parametrize("call", MESSAGES)
def test_messages_never_echo_huge_input(call: Callable[[], object]) -> None:
    with pytest.raises((CacheControlError, TypeError)) as caught:
        call()
    assert len(str(caught.value)) < 120
    assert "n" * 41 not in str(caught.value)


def test_a_metaclass_cannot_inflate_or_break_a_type_name() -> None:
    class Meta(type):
        @property
        def __name__(cls) -> str:  # type: ignore[override]
            return "m" * 100_000

    class Loud(metaclass=Meta):
        pass

    long_name = type("L" * 1000, (), {})
    assert type_name(Loud()) == "Loud"
    assert type_name(long_name()) == "L" * 40
    with pytest.raises(TypeError) as caught:
        parse("a", strict=long_name())
    assert str(caught.value) == f"strict must be a bool, got {'L' * 40}"


class _Int(int):
    def __str__(self) -> str:
        return "1\r\nSet-Cookie: x"

    __repr__ = __str__

    def __int__(self) -> int:
        return 7

    def __index__(self) -> int:
        return 7

    def __lt__(self, other: object) -> bool:
        return True


class _Str(str):
    def __str__(self) -> str:
        return "evil"

    def translate(self, *args: Any) -> str:
        return "no-store"

    def strip(self, *args: Any) -> str:
        return "no-store"

    def __iter__(self) -> Any:
        return iter("no-store")


def test_subclasses_are_read_as_their_plain_values() -> None:
    policy = CacheControl({_Str("Max-Age"): _Int(60), _Str("x"): _Str("a b")})
    assert [type(v) for v in policy.directives.values()] == [int, str]
    assert [type(k) for k in policy.directives] == [str, str]
    assert build(policy) == 'max-age=60, x="a b"'
    policy.directives["s-maxage"] = _Int(5)
    assert build(policy) == 'max-age=60, x="a b", s-maxage=5'
    assert build_targeted(policy) == 'max-age=60, x="a b", s-maxage=5'
    assert parse(_Str("max-age=5")).directives == {"max-age": 5}
    assert parse([_Str("max-age=5")]).directives == {"max-age": 5}
    assert parse_targeted(_Str("max-age=5")) == CacheControl({"max-age": 5})
    assert _Str("NO-STORE") in CacheControl({"no-store": True})
    assert CacheControl({"no-store": True}).has(_Str("NO-STORE"))


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, 10**400])
def test_times_must_be_finite(bad: float) -> None:
    times: dict[str, Any] = {"date_value": 0, "request_time": 0, "response_time": 0, "now": 0}
    for name in times:
        with pytest.raises(ValueError, match=f"{name} must be finite"):
            current_age(**{**times, name: bad})
    for name in ("expires", "date"):
        with pytest.raises(ValueError, match=f"{name} must be finite"):
            stamps: dict[str, Any] = {"expires": 1, "date": 0, name: bad}
            freshness_lifetime(CacheControl(), **stamps)


@pytest.mark.parametrize("bad", [True, "5", None, [1]])
def test_times_must_be_numbers(bad: Any) -> None:
    with pytest.raises(TypeError, match="now must be an int or a float"):
        current_age(date_value=0, request_time=0, response_time=0, now=bad)
    if bad is not None:
        with pytest.raises(TypeError, match="expires must be an int or a float"):
            freshness_lifetime(CacheControl(), expires=bad, date=0)
    with pytest.raises(TypeError, match="age_value must be an int"):
        current_age(date_value=0, request_time=0, response_time=0, now=0, age_value=1.5)  # type: ignore[arg-type]


def test_overflowing_time_arithmetic_gives_two_to_the_31() -> None:
    big = 1e308
    assert freshness_lifetime(CacheControl(), expires=big, date=-big) == DELTA_MAX
    assert freshness_lifetime(CacheControl(), expires=2**80, date=0) == DELTA_MAX
    assert freshness_lifetime(CacheControl(), expires=-big, date=big) == 0
    assert current_age(date_value=0, request_time=-big, response_time=big, now=-big) == DELTA_MAX
    assert (
        current_age(date_value=0, request_time=0, response_time=0, now=0, age_value=10**400)
        == DELTA_MAX
    )
    exact = 2**60
    assert (
        current_age(date_value=exact, request_time=exact, response_time=exact, now=exact + 1) == 1
    )


def test_a_huge_extension_integer_is_a_cache_control_error() -> None:
    with pytest.raises(CacheControlError, match="too large"):
        build(CacheControl({"x": 10**5000}))
    assert build(CacheControl({"x": 10**500})) == f"x={10**500}"
    assert build(CacheControl({"max-age": 10**5000})) == f"max-age={DELTA_MAX}"


def _seconds(call: Callable[[str], object], text: str) -> float:
    start = time.perf_counter()
    call(text)
    return time.perf_counter() - start


PATTERNS = ['a="', "a=,", "\\", ",", 'a="\\', "a=b c", "=", "a,", '"', 'x="a", ']


@pytest.mark.parametrize("pattern", PATTERNS)
def test_parsing_stays_linear_on_hostile_patterns(pattern: str) -> None:
    calls: list[Callable[[str], object]] = [parse, lambda t: parse(t, strict=False), parse_targeted]
    for call in calls:
        small = _seconds(call, pattern * (20_000 // len(pattern)))
        large = _seconds(call, pattern * (200_000 // len(pattern)))
        assert large < max(small, 0.002) * 40


def test_folded_head_lines_join_in_linear_time() -> None:
    def run(lines: int) -> float:
        text = "HTTP/1.1 200 OK\r\nCache-Control: a\r\n" + " b\r\n" * lines
        return _seconds(head_fields, text)

    assert run(200_000) < max(run(20_000), 0.002) * 40
    fields = head_fields("HTTP/1.1 200 OK\r\nX: a\r\n  \r\n\tb\r\n")
    assert fields == [("X", "a b")]
