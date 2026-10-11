from ccdirectives import CacheControl, build, parse


def test_builds_boolean_and_valued_directives() -> None:
    cc = CacheControl({"max-age": 600, "no-store": True})
    assert build(cc) == "max-age=600, no-store"


def test_false_flag_is_omitted() -> None:
    cc = CacheControl({"no-store": False, "public": True})
    assert build(cc) == "public"


def test_argument_with_special_characters_is_quoted() -> None:
    cc = CacheControl({"private": "Set-Cookie, X-Token"})
    assert build(cc) == 'private="Set-Cookie, X-Token"'


def test_plain_token_argument_is_not_quoted() -> None:
    assert build(CacheControl({"x-vendor": "custom"})) == "x-vendor=custom"


def test_quotes_and_backslashes_are_escaped() -> None:
    assert build(CacheControl({"note": 'a"b\\c'})) == 'note="a\\"b\\\\c"'


def test_round_trip_preserves_semantics() -> None:
    header = 'max-age=600, s-maxage=30, no-cache="Set-Cookie", must-revalidate, x-vendor=custom'
    assert parse(build(parse(header))) == parse(header)


def test_names_are_normalised_to_lower_case_on_build() -> None:
    assert build(CacheControl({"Max-Age": 10})) == "max-age=10"
