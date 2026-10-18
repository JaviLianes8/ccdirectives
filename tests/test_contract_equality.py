"""Equality of structures: names, values with their types and duplicates, in any order."""

from __future__ import annotations

import pytest

from ccdirectives import CacheControl, build, freshness_lifetime, parse


def test_equality_tells_numbers_from_flags() -> None:
    zero, absent = CacheControl({"max-age": 0}), CacheControl({"max-age": False})
    assert zero != absent and build(zero) != build(absent)
    assert freshness_lifetime(zero) == 0 and freshness_lifetime(absent) is None
    assert CacheControl({"no-store": True}) != CacheControl({"no-store": 1})
    assert CacheControl({"x": "1"}) != CacheControl({"x": 1})


def test_equality_ignores_order_and_case_but_not_duplicates() -> None:
    assert parse("max-age=5, x-a") == CacheControl({"X-A": True, "max-age": 5})
    assert parse("max-age=5, max-age=6") != parse("max-age=5")
    assert parse("max-age=5, max-age=6") == CacheControl({"max-age": 5}, frozenset({"MAX-AGE"}))


def test_equality_reads_direct_edits_as_plain_values() -> None:
    class Loud(int):
        def __eq__(self, other: object) -> bool:
            return False

        __hash__ = int.__hash__

    edited = CacheControl()
    edited.directives["max-age"] = Loud(5)
    assert edited == CacheControl({"max-age": 5})
    edited.directives["x"] = 1.5  # type: ignore[assignment]
    with pytest.raises(TypeError, match="value must be int, str or bool, not float"):
        _ = edited == CacheControl()


def test_equality_with_other_types_is_false_both_ways() -> None:
    policy, plain = CacheControl({"max-age": 5}), {"max-age": 5}
    assert policy != plain and plain != policy
    assert (policy == "max-age=5") is False and policy.__eq__(5) is NotImplemented

    class Sub(CacheControl):
        pass

    assert Sub({"max-age": 5}) != policy and Sub({"max-age": 5}) == Sub({"max-age": 5})
    with pytest.raises(TypeError, match="unhashable"):
        hash(policy)
