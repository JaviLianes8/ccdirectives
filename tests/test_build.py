from __future__ import annotations

import pytest

from ccdirectives import DELTA_MAX, CacheControl, CacheControlError, build, parse


def test_builds_boolean_and_valued_directives() -> None:
    assert build(CacheControl({"max-age": 600, "no-store": True})) == "max-age=600, no-store"


def test_false_flag_is_omitted() -> None:
    assert build(CacheControl({"no-store": False, "public": True})) == "public"


def test_field_lists_are_always_quoted() -> None:
    assert build(CacheControl({"private": "Set-Cookie"})) == 'private="Set-Cookie"'
    cc = CacheControl({"no-cache": "Set-Cookie, X-Token"})
    assert build(cc) == 'no-cache="Set-Cookie, X-Token"'


def test_plain_token_argument_is_not_quoted() -> None:
    assert build(CacheControl({"x-vendor": "custom"})) == "x-vendor=custom"


def test_other_arguments_are_quoted_when_not_tokens() -> None:
    assert build(CacheControl({"community": "U C I"})) == 'community="U C I"'
    assert build(CacheControl({"x": ""})) == 'x=""'


def test_quotes_and_backslashes_are_escaped() -> None:
    assert build(CacheControl({"note": 'a"b\\c'})) == 'note="a\\"b\\\\c"'


def test_delta_seconds_go_out_as_tokens() -> None:
    assert build(CacheControl({"max-age": "60"})) == "max-age=60"
    assert build(CacheControl({"max-age": DELTA_MAX * 4})) == f"max-age={DELTA_MAX}"
    assert build(CacheControl({"x-big": DELTA_MAX * 4})) == f"x-big={DELTA_MAX * 4}"


def test_bare_max_stale_is_allowed() -> None:
    assert build(CacheControl({"max-stale": True})) == "max-stale"


def test_round_trip_preserves_semantics() -> None:
    header = 'max-age=600, s-maxage=30, no-cache="Set-Cookie", must-revalidate, x-vendor=custom'
    assert parse(build(parse(header))) == parse(header)


def test_names_are_normalised_to_lower_case_on_build() -> None:
    assert build(CacheControl({"Max-Age": 10})) == "max-age=10"


@pytest.mark.parametrize(
    ("directives", "reason"),
    [
        ({"bad name": True}, "is not a token"),
        ({"": True}, "is not a token"),
        ({"max-age": -3}, "cannot be negative"),
        ({"x": -1}, "cannot be negative"),
        ({"max-age": "soon"}, "needs delta-seconds"),
        ({"max-age": ""}, "needs delta-seconds"),
        ({"max-age": True}, "needs delta-seconds"),
        ({"s-maxage": True}, "needs delta-seconds"),
        ({"no-store": "yes"}, "takes no argument"),
        ({"public": 1}, "takes no argument"),
        ({"x": "a\r\nSet-Cookie: b"}, "cannot carry"),
        ({"x": "caf\xe9"}, "cannot carry"),
        ({"x": "a\x7f"}, "cannot carry"),
        ({"private": "a b"}, "not a list of field names"),
    ],
)
def test_build_refuses_what_the_grammar_cannot_carry(
    directives: dict[str, int | str | bool], reason: str
) -> None:
    with pytest.raises(CacheControlError, match=reason) as caught:
        build(CacheControl(directives))
    assert caught.value.offset is None


def test_tab_inside_an_argument_is_quoted() -> None:
    assert build(CacheControl({"x": "a\tb"})) == 'x="a\tb"'
    assert parse(build(CacheControl({"x": "a\tb"})), strict=True)["x"] == "a\tb"
