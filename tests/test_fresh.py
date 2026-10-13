"""Freshness rules of RFC 9111 section 4.2 and the stale extensions of RFC 5861.

Cases are written by hand from the section text; the RFC examples themselves are read
from the fetched files in test_sources.py.
"""

from __future__ import annotations

import pytest

from ccdirectives import CacheControl, assess, current_age, freshness_lifetime, may_store, parse


def test_lifetime_follows_the_first_matching_rule() -> None:
    cc = parse("max-age=60, s-maxage=120")
    assert freshness_lifetime(cc) == 60
    assert freshness_lifetime(cc, shared=True) == 120
    assert freshness_lifetime(parse("s-maxage=120")) is None
    assert freshness_lifetime(parse("public"), expires=1100.9, date=1000.0) == 100
    assert freshness_lifetime(parse("max-age=5"), expires=9999.0, date=0.0) == 5
    assert freshness_lifetime(parse(""), expires=900.0, date=1000.0) == 0
    assert freshness_lifetime(parse("")) is None


def test_invalid_freshness_information_counts_as_stale() -> None:
    assert freshness_lifetime(parse("max-age=soon")) == 0
    assert freshness_lifetime(parse("max-age")) == 0
    assert freshness_lifetime(parse("s-maxage=x, max-age=60"), shared=True) == 0
    assert freshness_lifetime(parse("max-age=-5, max-age=60")) == 0


def test_expires_needs_a_date() -> None:
    with pytest.raises(ValueError, match="date"):
        freshness_lifetime(parse(""), expires=10.0)


def test_current_age_uses_the_more_conservative_estimate() -> None:
    assert current_age(date_value=100, request_time=100, response_time=102, now=110) == 10
    # The Age header beats a small apparent age; the response delay is added to it.
    assert (
        current_age(date_value=100, request_time=100, response_time=101, now=101, age_value=30)
        == 31
    )
    # Without an Age header a large apparent age wins over the response delay.
    assert current_age(date_value=0, request_time=100, response_time=101, now=101) == 101
    # A clock ahead of the origin cannot make the apparent age negative.
    assert current_age(date_value=200, request_time=100, response_time=100, now=100) == 0
    assert current_age(date_value=0, request_time=0, response_time=0.2, now=0.3) == 1


def test_fresh_and_reusable() -> None:
    verdict = assess(parse("max-age=60"), age=59)
    assert verdict.fresh and verdict.reusable and verdict.staleness == 0
    stale = assess(parse("max-age=60"), age=60)
    assert not stale.fresh and not stale.reusable and stale.staleness == 0
    assert assess(parse("max-age=60"), age=75).staleness == 15


def test_a_response_without_explicit_freshness_is_stale() -> None:
    verdict = assess(parse("public"), age=0)
    assert verdict.lifetime is None and not verdict.fresh and not verdict.reusable


def test_response_no_cache_blocks_reuse_even_when_fresh() -> None:
    assert not assess(parse("max-age=60, no-cache"), age=1).reusable
    assert not assess(parse('max-age=60, no-cache="Set-Cookie"'), age=1).reusable


def test_request_limits_narrow_reuse() -> None:
    cc = parse("max-age=600")
    assert not assess(cc, age=100, request=parse("no-cache")).reusable
    assert not assess(cc, age=100, request=parse("max-age=99")).reusable
    assert assess(cc, age=100, request=parse("max-age=100")).reusable
    assert not assess(cc, age=100, request=parse("max-age=junk")).reusable
    assert assess(cc, age=100, request=parse("min-fresh=500")).reusable
    assert not assess(cc, age=100, request=parse("min-fresh=501")).reusable


def test_max_stale_admits_a_stale_response() -> None:
    cc = parse("max-age=60")
    assert assess(cc, age=70, request=parse("max-stale=10")).reusable
    assert not assess(cc, age=71, request=parse("max-stale=10")).reusable
    assert assess(cc, age=10**9, request=parse("max-stale")).reusable
    assert not assess(cc, age=70, request=parse("max-stale=10, max-age=65")).reusable


@pytest.mark.parametrize(
    ("header", "shared"),
    [
        ("max-age=60, must-revalidate", False),
        ("max-age=60, no-cache", False),
        ("max-age=60, proxy-revalidate", True),
        ("max-age=60, s-maxage=60", True),
    ],
)
def test_directives_that_forbid_stale_use(header: str, shared: bool) -> None:
    cc = parse(f"{header}, stale-while-revalidate=99, stale-if-error=99")
    verdict = assess(cc, age=70, shared=shared, request=parse("max-stale"))
    assert not verdict.reusable
    assert not verdict.stale_while_revalidate and not verdict.stale_if_error


def test_proxy_revalidate_and_s_maxage_do_not_bind_a_private_cache() -> None:
    for header in ("max-age=60, proxy-revalidate", "max-age=60, s-maxage=60"):
        cc = parse(f"{header}, stale-while-revalidate=99")
        assert assess(cc, age=70).stale_while_revalidate


def test_stale_windows_apply_only_once_stale() -> None:
    cc = parse("max-age=60, stale-while-revalidate=30, stale-if-error=100")
    fresh = assess(cc, age=10)
    assert not fresh.stale_while_revalidate and not fresh.stale_if_error
    assert assess(cc, age=90).stale_while_revalidate
    assert not assess(cc, age=91).stale_while_revalidate
    assert not assess(cc, age=90, request=parse("no-cache")).stale_while_revalidate
    assert assess(cc, age=160).stale_if_error and not assess(cc, age=161).stale_if_error


def test_request_stale_if_error_takes_precedence() -> None:
    cc = parse("max-age=60, stale-if-error=100")
    assert not assess(cc, age=80, request=parse("stale-if-error=10")).stale_if_error
    assert assess(parse("max-age=60"), age=80, request=parse("stale-if-error=30")).stale_if_error


def test_negative_age_is_refused() -> None:
    with pytest.raises(ValueError, match="age"):
        assess(CacheControl(), age=-1)


def test_may_store_follows_the_directives() -> None:
    assert may_store(parse("max-age=60"))
    assert not may_store(parse("no-store"))
    assert may_store(parse("private"))
    assert not may_store(parse("private"), shared=True)
    assert may_store(parse('private="Set-Cookie"'), shared=True)
    assert not may_store(parse("max-age=60"), shared=True, authorized=True)
    for header in ("must-revalidate", "public", "s-maxage=5"):
        assert may_store(parse(header), shared=True, authorized=True), header
    assert may_store(parse("max-age=60"), authorized=True)


def test_must_understand_overrides_no_store_only_when_understood() -> None:
    cc = parse("must-understand, no-store")
    assert not may_store(cc)
    assert may_store(cc, understood_status=True)
    assert not may_store(parse("must-understand"))
