"""Contracts added for the findings of QA lens c (adversarial and robustness)."""

from __future__ import annotations

from typing import Any

import pytest

from ccdirectives import (
    DELTA_MAX,
    CacheControl,
    assess,
    build,
    current_age,
    freshness_lifetime,
    may_store,
    parse,
    parse_targeted,
    select,
)


def _fake(kind: type) -> Any:
    class Fake:
        __class__ = property(lambda self: kind)

        def __str__(self) -> str:
            return "60\r\nSet-Cookie: x=1"

        def __index__(self) -> int:
            return 60

        def __int__(self) -> int:
            return 60

        def __bool__(self) -> bool:
            return True

    return Fake()


@pytest.mark.parametrize("kind", [bool, int, str])
def test_a_spoofed_class_is_not_a_directive_value(kind: type) -> None:
    fake: Any = _fake(kind)
    assert isinstance(_fake(kind), kind)  # the spoof fools isinstance
    with pytest.raises(TypeError, match="value must be int, str or bool, not Fake"):
        CacheControl({"x-ext": fake})
    policy = CacheControl()
    with pytest.raises(TypeError, match="not Fake"):
        policy["x-ext"] = fake
    policy.directives["x-ext"] = fake
    with pytest.raises(TypeError, match="not Fake"):
        build(policy)


def test_spoofed_flags_names_times_and_structures_are_refused() -> None:
    calls: list[tuple[Any, str]] = [
        (lambda: parse("a", strict=_fake(bool)), "strict must be a bool, got Fake"),
        (lambda: parse(_fake(str)), "header must be str or an iterable of str"),
        (lambda: parse([_fake(str)]), "field lines must be str, not Fake"),
        (lambda: parse_targeted(_fake(str)), "value must be str or an iterable of str"),
        (lambda: CacheControl({_fake(str): 1}), "directive names must be str, not Fake"),
        (lambda: assess(CacheControl(), age=_fake(int)), "age must be an int, got Fake"),
        (lambda: build(_fake(CacheControl)), "build takes a CacheControl, not Fake"),
        (lambda: may_store(CacheControl(), shared=_fake(bool)), "shared must be a bool"),
        (
            lambda: current_age(date_value=_fake(int), request_time=0, response_time=0, now=0),
            "date_value must be an int or a float, got Fake",
        ),
        (lambda: select([_fake(tuple)]), r"headers holds \(name, value\) pairs"),
    ]
    for call, message in calls:
        with pytest.raises(TypeError, match=message) as caught:
            call()
        assert len(str(caught.value)) < 120


def test_mixed_huge_int_and_float_times_never_overflow() -> None:
    big = 10**308
    assert current_age(date_value=-big, request_time=0.0, response_time=big, now=0.0) == DELTA_MAX
    assert current_age(date_value=-big, request_time=big, response_time=big, now=0.5) == DELTA_MAX
    assert current_age(date_value=0, request_time=-1e308, response_time=big, now=0.0) == DELTA_MAX
    assert freshness_lifetime(CacheControl(), expires=big, date=-1e308) == DELTA_MAX
    assert current_age(date_value=0.5, request_time=0, response_time=1, now=1.25) == 2


class _EvilInt(int):
    def __lt__(self, other: object) -> bool:
        return False

    def __gt__(self, other: object) -> bool:
        return True


class _EvilStr(str):
    def lstrip(self, *args: Any) -> str:
        return "999"

    def split(self, *args: Any, **kwargs: Any) -> Any:
        return ["set-cookie"]


class _EvilDict(dict):  # type: ignore[type-arg]
    def get(self, key: Any, default: Any = None) -> Any:
        return 0

    def __getitem__(self, key: Any) -> Any:
        return 0


def test_values_set_directly_are_read_as_plain_values() -> None:
    policy = parse("max-age=0")
    policy.directives["max-age"] = _EvilInt(-5)
    assert policy.max_age is None and freshness_lifetime(policy) == 0
    policy.directives["max-age"] = _EvilStr("abc")
    assert policy.max_age is None
    policy = parse("private")
    policy.directives["private"] = _EvilStr("a b")
    assert policy.private_fields == () and not may_store(policy, shared=True)
    policy = parse("max-age=600, no-store")
    policy.directives = _EvilDict(policy.directives)
    assert policy.max_age == 600 and policy["max-age"] == 600 and freshness_lifetime(policy) == 600


def test_a_missing_name_is_reported_cut() -> None:
    with pytest.raises(KeyError) as caught:
        parse("max-age=1")["x" * 1_000_000]
    assert len(str(caught.value)) < 60
    with pytest.raises(KeyError):
        del parse("max-age=1")["y" * 1_000_000]


class _AlwaysEqual(str):
    def __eq__(self, other: object) -> bool:
        return True

    __hash__ = str.__hash__


def test_a_context_is_compared_as_plain_text() -> None:
    for call in (
        lambda: parse("a", context=_AlwaysEqual("zzz")),  # type: ignore[arg-type]
        lambda: parse("a").extensions(_AlwaysEqual("zzz")),  # type: ignore[arg-type]
    ):
        with pytest.raises(ValueError, match="context must be"):
            call()
    strict = parse("max-stale", strict=True, context=_AlwaysEqual("request"))  # type: ignore[arg-type]
    assert strict.max_stale == DELTA_MAX


class _LongTuple(tuple):  # type: ignore[type-arg]
    def __len__(self) -> int:
        return 2


def test_select_reads_pairs_by_their_real_length() -> None:
    for pair in (_LongTuple(("a", "b", "c")), _LongTuple(("a",))):
        with pytest.raises(TypeError, match=r"headers holds \(name, value\) pairs"):
            select([pair])
    assert select([_LongTuple(("Cache-Control", "max-age=4"))])[1].max_age == 4
