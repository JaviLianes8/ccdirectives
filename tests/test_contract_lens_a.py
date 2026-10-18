"""Contracts added for the findings of QA lens a (API and docs)."""

from __future__ import annotations

from typing import Any

import pytest

from ccdirectives import (
    DELTA_MAX,
    CacheControl,
    CacheControlError,
    assess,
    build,
    build_targeted,
    current_age,
    freshness_lifetime,
    parse,
    select,
)


def test_assess_reads_an_age_past_two_to_the_31_as_two_to_the_31() -> None:
    verdict = assess(parse("max-age=1"), age=2**40)
    assert (verdict.age, verdict.staleness) == (DELTA_MAX, DELTA_MAX - 1)
    stale = parse("max-stale")
    assert assess(parse("max-age=0"), age=2**40, request=stale).reusable
    assert assess(parse("max-age=0"), age=DELTA_MAX, request=stale).reusable
    verdict = assess(parse("public"), age=2**31 + 5, expires=2**40, date=0)
    assert (verdict.lifetime, verdict.age, verdict.staleness) == (DELTA_MAX, DELTA_MAX, 0)


def test_an_age_value_past_two_to_the_31_is_read_as_two_to_the_31() -> None:
    times = {"date_value": 2**31, "request_time": 2**31, "response_time": 100, "now": 100.5}
    assert current_age(**times, age_value=2**31 + 1) == current_age(**times, age_value=2**31)


def test_build_writes_every_integer_python_can_write() -> None:
    assert build(CacheControl({"x": 10**4000})) == f"x={10**4000}"
    with pytest.raises(CacheControlError, match="'x' argument is too large to write"):
        build(CacheControl({"x": 10**5000}))


def test_build_targeted_names_the_directive_with_a_long_integer() -> None:
    assert build_targeted(CacheControl({"x": 10**15 - 1})) == f"x={10**15 - 1}"
    with pytest.raises(CacheControlError) as caught:
        build_targeted(CacheControl({"x": 10**15}))
    assert str(caught.value) == "'x' argument has more than 15 digits"


def test_keys_and_values_follow_header_order() -> None:
    policy = parse("max-age=5, x-a, private")
    assert list(policy.keys()) == ["max-age", "x-a", "private"]
    assert list(policy.values()) == [5, True, True]
    assert dict(policy) == {"max-age": 5, "x-a": True, "private": True}


@pytest.mark.parametrize("pair", [("a", "b", "c"), ("a",), 5, "ab", {"a": 1, "b": 2}])
def test_select_refuses_what_is_not_a_pair(pair: Any) -> None:
    with pytest.raises(TypeError, match=r"headers holds \(name, value\) pairs"):
        select([pair])


def test_an_integer_time_beyond_a_float_is_out_of_range() -> None:
    with pytest.raises(ValueError, match="expires is out of the range of a float"):
        freshness_lifetime(parse("public"), expires=10**400, date=0)
    with pytest.raises(ValueError, match="now is out of the range of a float"):
        current_age(date_value=0, request_time=0, response_time=0, now=-(10**400))


def test_select_takes_lists_of_two_as_pairs() -> None:
    assert select([["CDN-Cache-Control", "max-age=9"]])[1].max_age == 9  # type: ignore[list-item]


def test_build_targeted_caps_delta_seconds_before_the_digit_limit() -> None:
    assert build_targeted(CacheControl({"max-age": 10**20})) == f"max-age={DELTA_MAX}"
    assert build_targeted(CacheControl({"s-maxage": str(10**20)})) == f"s-maxage={DELTA_MAX}"


def test_keys_and_values_are_live_views() -> None:
    policy = parse("max-age=5")
    keys, values = policy.keys(), policy.values()
    policy["x-new"] = 1
    assert len(keys) == 2 and list(keys) == list(keys) == ["max-age", "x-new"]
    assert list(values) == [5, 1]
    assert keys & {"x-new", "other"} == {"x-new"}


@pytest.mark.parametrize("zero", ["0", "00", 0])
def test_build_targeted_keeps_a_zero_lifetime(zero: str | int) -> None:
    assert build_targeted(CacheControl({"max-age": zero})) == "max-age=0"
