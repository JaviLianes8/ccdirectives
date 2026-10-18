"""Contracts added for the findings of QA lens b (correctness and ground truth)."""

from __future__ import annotations

import pytest

from ccdirectives import assess, may_store, parse, parse_targeted, select


@pytest.mark.parametrize("header", ["private=", 'private=""', "private=,", 'private=" , "'])
def test_an_empty_private_list_keeps_a_shared_cache_out(header: str) -> None:
    assert not may_store(parse(header), shared=True)
    assert may_store(parse(header))


def test_a_listed_private_field_still_lets_a_shared_cache_store() -> None:
    assert may_store(parse('private="set-cookie"'), shared=True)
    assert may_store(parse("private=set-cookie"), shared=True)


def test_an_empty_private_list_in_a_targeted_field_keeps_a_shared_cache_out() -> None:
    policy = parse_targeted('private=""')
    assert policy is not None and not may_store(policy, shared=True)


def test_an_invalid_targeted_s_maxage_does_not_loosen_a_shared_cache() -> None:
    headers = {
        "CDN-Cache-Control": "max-age=600, s-maxage=1.5, stale-while-revalidate=60",
        "Cache-Control": "public",
    }
    name, policy = select(headers)
    assert name == "CDN-Cache-Control"
    verdict = assess(policy, age=630, shared=True)
    assert (verdict.lifetime, verdict.stale_while_revalidate) == (0, False)
    plain = assess(
        parse("max-age=600, s-maxage=x, stale-while-revalidate=60"), age=630, shared=True
    )
    assert (plain.lifetime, plain.stale_while_revalidate) == (0, False)
