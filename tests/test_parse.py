from __future__ import annotations

import pytest

from ccdirectives import DELTA_MAX, CacheControl, parse


def test_parses_a_mix_of_boolean_and_valued_directives() -> None:
    cc = parse("max-age=600, no-store, must-revalidate")
    assert cc.max_age == 600
    assert cc.no_store is True
    assert cc.must_revalidate is True


def test_numeric_directive_becomes_an_int() -> None:
    cc = parse("s-maxage=86400")
    assert cc.s_maxage == 86400
    assert isinstance(cc["s-maxage"], int)


def test_quoted_delta_seconds_are_accepted() -> None:
    assert parse('max-age="5"')["max-age"] == 5


@pytest.mark.parametrize("raw", ["-5", "+7", "1_0", " 5x", chr(0xFF15), "5.0", "0x10", ""])
def test_delta_seconds_are_ascii_digits_only(raw: str) -> None:
    cc = parse(f"max-age={raw}")
    assert cc.max_age is None
    assert cc["max-age"] == raw.strip()


def test_delta_seconds_overflow_to_two_to_the_31() -> None:
    assert parse("max-age=2147483647").max_age == 2147483647
    assert parse("max-age=2147483648").max_age == DELTA_MAX
    assert parse("max-age=2147483649").max_age == DELTA_MAX
    assert parse("max-age=9999999999")["max-age"] == DELTA_MAX
    assert parse("s-maxage=" + "9" * 5000).s_maxage == DELTA_MAX
    assert parse("max-age=000000000000000042").max_age == 42


def test_extension_digits_stay_text() -> None:
    assert parse("x-ttl=60")["x-ttl"] == "60"


def test_the_first_occurrence_wins_and_repeats_are_reported() -> None:
    cc = parse("max-age=60, MAX-AGE=5, no-store, no-store")
    assert cc.max_age == 60
    assert cc.duplicates == frozenset({"max-age", "no-store"})


def test_quoted_argument_is_unescaped() -> None:
    cc = parse('private="Set-Cookie, X-Token"')
    assert cc["private"] == "Set-Cookie, X-Token"
    assert cc.private is True


def test_escaped_quote_inside_a_quoted_argument() -> None:
    assert parse('no-cache="a\\"b"')["no-cache"] == 'a"b'


def test_an_unterminated_quote_does_not_hide_later_directives() -> None:
    cc = parse('private="a", x="unterminated, no-store')
    assert cc.no_store is True
    assert cc["x"] == '"unterminated'


def test_junk_after_an_argument_keeps_the_whole_argument() -> None:
    cc = parse("max-age=5 6, public")
    assert cc["max-age"] == "5 6" and cc.max_age is None
    assert cc.public


def test_junk_after_a_quoted_argument_is_dropped() -> None:
    assert parse('community="UCI" junk, public').directives == {"community": "UCI", "public": True}


def test_a_name_followed_by_junk_is_kept_bare() -> None:
    assert parse("max age=5, no store, public").directives == {
        "max": True,
        "no": True,
        "public": True,
    }


def test_whitespace_around_equals_is_tolerated() -> None:
    assert parse("max-age = 60").max_age == 60


def test_unknown_directive_is_preserved() -> None:
    cc = parse("max-age=0, x-vendor=custom, surrogate-control")
    assert cc["x-vendor"] == "custom"
    assert cc["surrogate-control"] is True


def test_directive_names_are_case_insensitive() -> None:
    cc = parse("Max-Age=60, NO-STORE")
    assert cc.max_age == 60
    assert cc.no_store is True
    assert "MAX-AGE" in cc


KELVIN = chr(0x212A)


def test_only_ascii_letters_fold() -> None:
    # The Kelvin sign lower-cases to "k" with Unicode rules; it is not a token character.
    assert "max-agek" not in parse("MAX-AGE" + KELVIN + "=1")
    assert parse("MAX-AGE" + KELVIN + "=1").max_age is None
    assert "max-agek" not in CacheControl({"MAX-AGE" + KELVIN: 1})


def test_cr_lf_and_nul_become_spaces() -> None:
    cc = parse("max-age=5\r\nSet-Cookie: a=b, no-store")
    assert cc.no_store
    assert cc["max-age"] == "5  Set-Cookie: a=b"
    assert parse("no-cache\x00, public").public


def test_malformed_input_is_tolerated() -> None:
    cc = parse(',, =orphan, max-age=notanumber, ,no-store,, "quoted", {x}')
    assert cc.no_store is True
    assert cc["max-age"] == "notanumber"
    assert list(cc) == ["max-age", "no-store"]


def test_empty_header_is_empty() -> None:
    assert len(parse("")) == 0
    assert parse("   ") == CacheControl()


def test_several_field_lines_combine_in_order() -> None:
    cc = parse(["max-age=60", "no-cache, max-age=5", ""])
    assert cc.max_age == 60 and cc.no_cache and cc.duplicates == {"max-age"}


def test_bytes_are_refused_with_a_hint() -> None:
    with pytest.raises(TypeError, match="ISO-8859-1"):
        parse(b"max-age=1")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="field lines must be str"):
        parse(["max-age=1", b"x"])  # type: ignore[list-item]


def test_an_unknown_context_is_refused() -> None:
    with pytest.raises(ValueError, match="context"):
        parse("max-age=1", context="both")  # type: ignore[arg-type]
