"""Contracts added when the author mutation round found promises no test pinned."""

from __future__ import annotations

import pytest

from ccdirectives import CacheControl, CacheControlError, build, build_targeted, parse


def test_nul_inside_a_value_becomes_a_space_in_lenient_mode() -> None:
    assert parse('x="a\x00b", y=c\x00d')["x"] == "a b"


def test_field_lines_are_joined_with_a_comma_and_a_space() -> None:
    with pytest.raises(CacheControlError) as caught:
        parse(["max-age=1", "max-age=2"], strict=True)
    assert caught.value.offset == len("max-age=1, ")
    with pytest.raises(CacheControlError) as caught:
        parse(["a", "b c"], strict=True)
    assert caught.value.offset == len("a, b ")


@pytest.mark.parametrize("length", [41, 1000, 39_999])
def test_a_long_name_is_cut_to_forty_characters_in_messages(length: int) -> None:
    name = "n" * length
    with pytest.raises(CacheControlError) as caught:
        parse(f"{name}, {name}", strict=True)
    assert str(caught.value) == f"repeated directive {'n' * 40!r}... at offset {length + 2}"
    with pytest.raises(CacheControlError) as caught:
        build(CacheControl({f"{name} x": True}))
    assert str(caught.value) == f"directive name {'n' * 40!r}... is not a token"


def test_a_name_of_forty_characters_is_shown_whole() -> None:
    name = "n" * 40
    with pytest.raises(CacheControlError) as caught:
        parse(f"{name}, {name}", strict=True)
    assert caught.value.reason == f"repeated directive {name!r}"


@pytest.mark.parametrize("name", ["Max-Age", "x-A", "Z"])
def test_build_targeted_refuses_a_key_that_is_not_lower_case_ascii(name: str) -> None:
    policy = CacheControl()
    policy.directives[name] = True
    with pytest.raises(CacheControlError, match="is not a structured field key"):
        build_targeted(policy)
