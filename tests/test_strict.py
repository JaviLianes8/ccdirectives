from __future__ import annotations

import pytest

from ccdirectives import CacheControlError, parse


@pytest.mark.parametrize(
    ("header", "reason", "offset"),
    [
        ("=orphan", "expected a directive name", 0),
        ("max-age=60 public", "expected ','", 11),
        ("max age", "expected ','", 4),
        ("max-age =60", "whitespace before '='", 7),
        ("max-age= 60", "whitespace after '='", 8),
        ("x=", "expected a token or a quoted string", 2),
        ('x="open', "unterminated quoted string", 2),
        ('x="a\\', "unterminated quoted string", 2),
        ('x="a\x7fb"', "control character", 4),
        ('x="a\u0100"', "character not allowed in a quoted string", 4),
        ("max-age=1\r\n", "control character", 9),
        ("no-store, no-store", "repeated directive 'no-store'", 10),
        ("max-age", "'max-age' needs delta-seconds", 0),
        ("max-age=-1", "not delta-seconds", 0),
        ("s-maxage=1.5", "not delta-seconds", 0),
        ("max-stale=x", "not delta-seconds", 0),
        ("no-store=1", "'no-store' takes no argument", 0),
        ("public, must-revalidate=yes", "takes no argument", 8),
        ('private="a b"', "not a list of field names", 0),
        ('no-cache="set-cookie, x y"', "not a list of field names", 0),
    ],
)
def test_strict_mode_reports_the_problem_and_its_offset(
    header: str, reason: str, offset: int
) -> None:
    with pytest.raises(CacheControlError) as caught:
        parse(header, strict=True)
    assert reason in caught.value.reason
    assert caught.value.offset == offset
    assert isinstance(caught.value, ValueError)
    assert f"at offset {offset}" in str(caught.value)


def test_strict_mode_accepts_every_valid_form() -> None:
    header = (
        'max-age=60, max-stale, min-fresh="5", no-cache="Set-Cookie, ETag", '
        'private, community="UCI", x-flag, immutable=whatever, ,\t, stale-if-error=0'
    )
    cc = parse(header, strict=True)
    assert cc.max_age == 60 and cc.min_fresh == 5 and cc.stale_if_error == 0
    assert cc.no_cache_fields == ("set-cookie", "etag")
    assert cc.immutable


def test_quoted_pairs_and_obs_text_are_valid() -> None:
    assert parse('x="a\\"b\\\\c\\\tq\xe9"', strict=True)["x"] == 'a"b\\c\tq\xe9'


def test_context_applies_the_rules_of_one_direction() -> None:
    # Request no-cache takes no argument; response no-cache takes a field list.
    with pytest.raises(CacheControlError, match="takes no argument"):
        parse('no-cache="ETag"', strict=True, context="request")
    assert parse('no-cache="ETag"', strict=True, context="response").no_cache_fields == ("etag",)
    # max-stale is a request directive: in a response it is an extension with any argument.
    assert parse("max-stale=soon", strict=True, context="response")["max-stale"] == "soon"
    with pytest.raises(CacheControlError, match="not delta-seconds"):
        parse("max-stale=soon", strict=True, context="request")
    # s-maxage is a response directive; a request may carry it as an extension.
    assert parse("s-maxage", strict=True, context="request")["s-maxage"] is True


def test_several_lines_are_checked_as_one_value() -> None:
    with pytest.raises(CacheControlError, match="repeated"):
        parse(["max-age=1", "max-age=2"], strict=True)
