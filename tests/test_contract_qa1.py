"""Contracts from the first QA round: absent values, select, field lists, targeted caps."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from ccdirectives import (
    DELTA_MAX,
    CacheControl,
    CacheControlError,
    assess,
    build,
    build_targeted,
    freshness_lifetime,
    may_store,
    parse,
    parse_targeted,
    select,
)


def test_a_false_value_is_absent_everywhere() -> None:
    given = CacheControl({"public": False, "max-age": False, "x-a": False})
    assert ("public" in given, len(given), list(given), dict(given)) == (False, 0, [], {})
    assert given == CacheControl() and given.extensions() == ()
    assert CacheControl({"max-age": False}) == CacheControl()
    assert CacheControl({"max-age": 0}) != CacheControl({"max-age": False})


def test_assigning_false_removes_the_directive() -> None:
    cc = CacheControl({"Public": True, "max-age": 5})
    cc["PUBLIC"] = False
    cc["x-new"] = False
    assert list(cc.items()) == [("max-age", 5)] and "x-new" not in cc
    with pytest.raises(TypeError):
        cc[1] = False  # type: ignore[index]


def test_a_false_value_is_not_an_occurrence() -> None:
    cc = CacheControl({"public": False, "PUBLIC": True})
    assert (cc.directives, cc.duplicates) == ({"public": True}, frozenset())


def test_a_false_value_set_directly_compares_as_absent() -> None:
    edited = CacheControl({"max-age": 5})
    edited.directives["no-store"] = False
    assert edited == CacheControl({"max-age": 5}) and build(edited) == "max-age=5"


class _Big(type):
    pass


def _unnamed() -> object:
    return _Big("K" * 200, (), {})()


@pytest.mark.parametrize("which", ["headers", "targets"])
def test_select_refuses_what_is_not_iterable_with_a_bounded_message(which: str) -> None:
    hostile: Any = _unnamed()
    with pytest.raises(TypeError) as caught:
        select(hostile) if which == "headers" else select({}, hostile)
    assert len(str(caught.value)) < 120 and "K" * 41 not in str(caught.value)


def test_select_takes_lists_of_two_as_the_docs_say() -> None:
    name, policy = select([["CDN-Cache-Control", "max-age=1"]])
    assert (name, policy.directives) == ("CDN-Cache-Control", {"max-age": 1})


def test_the_first_present_target_in_the_list_wins() -> None:
    headers = {"A-Cache-Control": "max-age=1", "CDN-Cache-Control": "max-age=2"}
    assert select(headers, ["A-Cache-Control", "CDN-Cache-Control"])[0] == "A-Cache-Control"
    assert select(headers, ["CDN-Cache-Control", "A-Cache-Control"])[0] == "CDN-Cache-Control"


@pytest.mark.parametrize("name", ["private", "no-cache", "PRIVATE"])
@pytest.mark.parametrize("value", [5, 0, True])
def test_a_field_list_directive_takes_text_or_a_bare_flag(name: str, value: int) -> None:
    cc = CacheControl({name: value})
    if value is True:
        assert build(cc) == name.lower()
        return
    for writer in (build, build_targeted):
        with pytest.raises(CacheControlError, match="not a list of field names"):
            writer(cc)


@pytest.mark.parametrize(
    "directives",
    [{"private": True}, {"private": "Set-Cookie"}, {"no-cache": "ETag", "public": True}],
)
def test_the_round_trip_keeps_the_storage_verdict(directives: dict[str, str | bool]) -> None:
    cc = CacheControl(dict(directives))
    again = parse(build(cc), strict=True)
    for shared in (False, True):
        assert may_store(again, shared=shared) == may_store(cc, shared=shared)
    assert (again.private_fields, again.no_cache_fields) == (cc.private_fields, cc.no_cache_fields)
    targeted = parse_targeted(build_targeted(cc))
    assert targeted is not None and targeted == cc


def test_parse_targeted_caps_delta_seconds_like_parse() -> None:
    cc = parse_targeted("max-age=99999999999")
    assert cc is not None and cc["max-age"] == DELTA_MAX == 2**31
    assert cc == parse("max-age=99999999999")


def test_every_property_has_a_docstring_with_a_passing_example() -> None:
    import doctest

    import ccdirectives

    finder, runner = doctest.DocTestFinder(recurse=False), doctest.DocTestRunner()
    names = [n for n, v in inspect.getmembers(CacheControl) if isinstance(v, property)]
    assert len(names) == 18
    for name in names:
        prop = inspect.getattr_static(CacheControl, name)
        tests = finder.find(prop, name, globs=dict(vars(ccdirectives)))
        assert tests and tests[0].examples, name
        runner.run(tests[0])
    assert runner.failures == 0


def test_an_expires_lifetime_is_rounded_down_and_needs_a_date() -> None:
    assert freshness_lifetime(parse("public"), expires=1000.9, date=1000) == 0
    assert freshness_lifetime(parse("public"), expires=1002.5, date=1000) == 2
    with pytest.raises(ValueError, match="pass date"):
        freshness_lifetime(parse("public"), expires=900)
    with pytest.raises(ValueError, match="pass date"):
        assess(parse("public"), age=0, expires=900)
