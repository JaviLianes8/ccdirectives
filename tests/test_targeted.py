"""Targeted fields (RFC 9213): mapping structured field members to directives and back."""

from __future__ import annotations

import pytest

from ccdirectives import (
    DELTA_MAX,
    CacheControl,
    CacheControlError,
    build_targeted,
    parse_targeted,
    select,
)


def test_members_map_to_directive_values() -> None:
    cc = parse_targeted('max-age=600, private="Set-Cookie", community="UCI", x=tok, y=1.5')
    assert cc is not None
    assert cc.directives == {
        "max-age": 600,
        "private": "Set-Cookie",
        "community": "UCI",
        "x": "tok",
        "y": "1.5",
    }
    assert type(cc["x"]) is str


def test_parameters_are_ignored() -> None:
    cc = parse_targeted("max-age=60;a=1, no-store;b")
    assert cc is not None and cc.directives == {"max-age": 60, "no-store": True}


@pytest.mark.parametrize(
    "value", ["", "   ", "max-age=60,", "MAX-AGE=60", "max-age=60 x", "a=" + chr(0xE9)]
)
def test_an_empty_or_invalid_field_is_ignored(value: str) -> None:
    assert parse_targeted(value) is None


def test_values_that_break_a_directive_rule_are_left_out() -> None:
    cc = parse_targeted('max-age=1.5, s-maxage="60", stale-if-error=-1, public=?0, x=:AQID:')
    assert cc is not None and len(cc) == 0
    cc = parse_targeted('max-age, must-understand=1, public="yes", y=@1, z=%"a", w=(1 2)')
    assert cc is not None and len(cc) == 0


def test_restrictive_directives_survive_a_bad_value() -> None:
    cc = parse_targeted('no-store=1, private=tok, no-cache=(a), must-revalidate="x"')
    assert cc is not None
    assert cc.directives == {
        "no-store": True,
        "private": True,
        "no-cache": True,
        "must-revalidate": True,
    }


def test_immutable_ignores_its_argument() -> None:
    cc = parse_targeted("immutable=?0, max-age=31536000")
    assert cc is not None and cc.immutable and cc.max_age == 31536000


def test_large_integers_are_capped() -> None:
    cc = parse_targeted("max-age=999999999999999")
    assert cc is not None and cc.max_age == DELTA_MAX


def test_repeated_keys_keep_the_last_value() -> None:
    cc = parse_targeted("max-age=1, max-age=2")
    assert cc is not None and cc.max_age == 2


def test_several_lines_combine() -> None:
    cc = parse_targeted(["max-age=60", "no-transform"])
    assert cc is not None and cc.max_age == 60 and cc.no_transform


def test_build_targeted_writes_a_dictionary() -> None:
    cc = CacheControl(
        {"max-age": 600, "private": "Set-Cookie", "x": "tok", "y": "1abc", "s-maxage": "30"}
    )
    expected = 'max-age=600, private="Set-Cookie", x=tok, y="1abc", s-maxage=30'
    assert build_targeted(cc) == expected
    assert build_targeted(CacheControl({"max-age": DELTA_MAX * 3, "z": False})) == (
        f"max-age={DELTA_MAX}"
    )
    assert build_targeted(CacheControl()) == ""


def test_build_targeted_round_trips() -> None:
    cc = CacheControl({"max-age": 60, "no-cache": "ETag", "community": "U C I", "flag": True})
    assert parse_targeted(build_targeted(cc)) == cc


@pytest.mark.parametrize(
    ("directives", "reason"),
    [
        ({"x!": True}, "not a structured field key"),
        ({"9x": True}, "not a structured field key"),
        ({"max-age": True}, "needs delta-seconds"),
        ({"x": 10**16}, "at most 15 digits"),
        ({"x": "a\tb"}, "visible ASCII"),
    ],
)
def test_build_targeted_refuses_what_the_dictionary_cannot_carry(
    directives: dict[str, int | str | bool], reason: str
) -> None:
    with pytest.raises(CacheControlError, match=reason):
        build_targeted(CacheControl(directives))


def test_select_prefers_the_first_valid_target() -> None:
    headers = [
        ("Cache-Control", "max-age=60"),
        ("CDN-Cache-Control", "max-age=600"),
        ("Example-Cache-Control", "max-age=,"),
    ]
    targets = ("Example-Cache-Control", "CDN-Cache-Control")
    assert select(headers, targets) == ("CDN-Cache-Control", CacheControl({"max-age": 600}))
    assert select(headers, ()) == ("Cache-Control", CacheControl({"max-age": 60}))


def test_select_matches_names_case_insensitively_and_joins_lines() -> None:
    headers = [("cdn-cache-control", "max-age=600"), ("CDN-CACHE-CONTROL", "no-transform")]
    field, cc = select(headers)
    assert field == "CDN-Cache-Control" and cc.max_age == 600 and cc.no_transform


def test_select_falls_back_on_cache_control() -> None:
    assert select({"Cache-Control": "no-store", "CDN-Cache-Control": ""}) == (
        "Cache-Control",
        CacheControl({"no-store": True}),
    )
    assert select({}) == ("Cache-Control", CacheControl())
