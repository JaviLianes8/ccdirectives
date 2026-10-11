from ccdirectives import CacheControl, parse


def test_parses_a_mix_of_boolean_and_valued_directives() -> None:
    cc = parse("max-age=600, no-store, must-revalidate")
    assert cc.max_age == 600
    assert cc.no_store is True
    assert cc.must_revalidate is True


def test_numeric_directive_becomes_an_int() -> None:
    cc = parse("s-maxage=86400")
    assert cc.s_maxage == 86400
    assert isinstance(cc["s-maxage"], int)


def test_quoted_argument_is_unescaped() -> None:
    cc = parse('private="Set-Cookie, X-Token"')
    assert cc["private"] == "Set-Cookie, X-Token"
    assert cc.private is True


def test_escaped_quote_inside_a_quoted_argument() -> None:
    cc = parse('no-cache="a\\"b"')
    assert cc["no-cache"] == 'a"b'


def test_unknown_directive_is_preserved() -> None:
    cc = parse("max-age=0, x-vendor=custom, surrogate-control")
    assert cc["x-vendor"] == "custom"
    assert cc["surrogate-control"] is True


def test_directive_names_are_case_insensitive() -> None:
    cc = parse("Max-Age=60, NO-STORE")
    assert cc.max_age == 60
    assert cc.no_store is True
    assert "MAX-AGE" in cc


def test_malformed_input_is_tolerated() -> None:
    cc = parse(",, =orphan, max-age=notanumber, ,no-store,")
    assert cc.no_store is True
    assert cc["max-age"] == "notanumber"
    assert "" not in cc


def test_empty_header_is_empty() -> None:
    assert len(parse("")) == 0
    assert parse("   ") == CacheControl()
