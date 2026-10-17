from __future__ import annotations

import pytest

from ccdirectives import DELTA_MAX, CacheControl, parse


def test_construction_folds_names_and_keeps_the_first_of_a_pair() -> None:
    cc = CacheControl({"Max-Age": 1, "max-age": 2})
    assert cc.directives == {"max-age": 1}
    assert cc.duplicates == {"max-age"}


def test_values_of_the_wrong_type_are_refused() -> None:
    with pytest.raises(TypeError, match="int, str or bool"):
        CacheControl({"max-age": 1.5})  # type: ignore[dict-item]
    with pytest.raises(TypeError, match="names must be str"):
        CacheControl({1: True})  # type: ignore[dict-item]
    cc = CacheControl()
    with pytest.raises(TypeError, match="int, str or bool"):
        cc["max-age"] = None  # type: ignore[assignment]


def test_mapping_operations_ignore_case() -> None:
    cc = CacheControl()
    cc["Max-Age"] = 5
    assert cc["MAX-AGE"] == 5 and cc.get("max-AGE") == 5 and len(cc) == 1
    assert list(cc.items()) == [("max-age", 5)]
    del cc["MAX-age"]
    assert "max-age" not in cc and cc.get("max-age", 7) == 7
    assert 5 not in cc


def test_flags_are_true_for_any_present_value_but_false() -> None:
    cc = parse('no-cache="", private="", public=junk')
    assert cc.no_cache and cc.private and cc.public
    assert not CacheControl({"no-store": False}).no_store
    assert CacheControl({"immutable": "x"}).immutable


@pytest.mark.parametrize(
    ("prop", "name"),
    [
        ("no_store", "no-store"),
        ("no_transform", "no-transform"),
        ("only_if_cached", "only-if-cached"),
        ("must_revalidate", "must-revalidate"),
        ("proxy_revalidate", "proxy-revalidate"),
        ("must_understand", "must-understand"),
        ("public", "public"),
        ("private", "private"),
        ("no_cache", "no-cache"),
        ("immutable", "immutable"),
    ],
)
def test_each_flag_reads_its_own_directive(prop: str, name: str) -> None:
    assert getattr(parse(name), prop) is True
    assert getattr(parse("x-other"), prop) is False


@pytest.mark.parametrize(
    ("prop", "name"),
    [
        ("max_age", "max-age"),
        ("s_maxage", "s-maxage"),
        ("min_fresh", "min-fresh"),
        ("max_stale", "max-stale"),
        ("stale_while_revalidate", "stale-while-revalidate"),
        ("stale_if_error", "stale-if-error"),
    ],
)
def test_each_number_reads_its_own_directive(prop: str, name: str) -> None:
    assert getattr(parse(f"{name}=17"), prop) == 17
    assert getattr(parse("max-age=99, s-maxage=98, min-fresh=97, x=1"), prop) == {
        "max_age": 99,
        "s_maxage": 98,
        "min_fresh": 97,
    }.get(prop)


def test_seconds_rejects_flags_text_and_negative_numbers() -> None:
    cc = CacheControl({"a": True, "b": "5", "c": -1, "d": DELTA_MAX + 9, "e": 0})
    assert [cc.seconds(n) for n in "abcde"] == [None, 5, None, DELTA_MAX, 0]


def test_bare_max_stale_accepts_any_staleness() -> None:
    assert parse("max-stale").max_stale == DELTA_MAX
    assert parse("max-stale=10").max_stale == 10
    assert parse("max-stale=x").max_stale is None
    assert CacheControl().max_stale is None


def test_field_lists_are_split_and_lower_cased() -> None:
    cc = parse('no-cache="Set-Cookie, , ETag", private="X-Token"')
    assert cc.no_cache_fields == ("set-cookie", "etag")
    assert cc.private_fields == ("x-token",)
    assert parse("no-cache, private").no_cache_fields == ()
    assert parse('private="a b"').private_fields == ()


def test_extensions_depend_on_the_direction() -> None:
    cc = parse("max-age=1, public, max-stale, x-vendor")
    assert cc.extensions() == ("x-vendor",)
    assert cc.extensions("request") == ("public", "x-vendor")
    assert cc.extensions("response") == ("max-stale", "x-vendor")
    with pytest.raises(ValueError, match="context"):
        cc.extensions("both")  # type: ignore[arg-type]
