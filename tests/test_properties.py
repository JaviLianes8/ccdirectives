"""Seeded properties: the freshness verdict, strict and lenient agreement, any code point."""

from __future__ import annotations

import contextlib
import random

from ccdirectives import (
    DELTA_MAX,
    CacheControl,
    CacheControlError,
    assess,
    build,
    current_age,
    freshness_lifetime,
    may_store,
    parse,
    parse_targeted,
    select,
)

ROUNDS = 4000
DIRECTIVES = [
    "max-age=60",
    "max-age=0",
    "s-maxage=120",
    "no-cache",
    'no-cache="etag"',
    "must-revalidate",
    "proxy-revalidate",
    "stale-while-revalidate=30",
    "stale-if-error=300",
    "private",
    "public",
    "no-store",
    "must-understand",
    "max-age=x",
]
REQUESTS = [
    "",
    "max-age=90",
    "min-fresh=10",
    "max-stale",
    "max-stale=20",
    "no-cache",
    "stale-if-error=5",
]


def _header(rng: random.Random, pool: list[str]) -> str:
    return ", ".join(rng.sample(pool, rng.randint(0, 4)))


def test_the_verdict_keeps_its_invariants() -> None:
    rng = random.Random(5861)
    for _ in range(ROUNDS):
        response = parse(_header(rng, DIRECTIVES))
        request = parse(_header(rng, REQUESTS))
        shared = rng.random() < 0.5
        age = rng.choice([0, 1, 30, 59, 60, 61, 89, 90, 119, 120, 121, 200, 10**12])
        verdict = assess(response, age=age, shared=shared, request=request)
        lifetime = freshness_lifetime(response, shared=shared)
        assert verdict.lifetime == lifetime and verdict.age == age
        assert verdict.fresh == (lifetime is not None and lifetime > age)
        assert verdict.staleness == (0 if verdict.fresh else age - (lifetime or 0))
        if verdict.reusable:
            assert not response.no_cache and not request.no_cache
            assert verdict.fresh or request.max_stale is not None
        if verdict.fresh:
            assert not verdict.stale_while_revalidate and not verdict.stale_if_error
        if verdict.stale_while_revalidate or verdict.stale_if_error:
            assert not response.no_cache and not response.must_revalidate
        if response.no_store and not response.must_understand:
            assert not may_store(response, shared=shared, understood_status=True)


def test_current_age_is_monotonic_in_now() -> None:
    rng = random.Random(4231)
    for _ in range(ROUNDS):
        date = rng.uniform(-1e6, 1e6)
        sent = rng.uniform(-1e6, 1e6)
        received = sent + rng.uniform(0, 100)
        now = received + rng.uniform(0, 1e6)
        age = rng.randint(0, 10**6)
        first = current_age(
            date_value=date, request_time=sent, response_time=received, now=now, age_value=age
        )
        later = current_age(
            date_value=date, request_time=sent, response_time=received, now=now + 1, age_value=age
        )
        assert 0 <= first <= later <= DELTA_MAX
        assert first >= age


def test_any_code_point_is_parsed_without_surprises() -> None:
    rng = random.Random(9651)
    special = [*list('=,;" \t\\()'), "max-age", "private", "no-store"]
    for _ in range(ROUNDS):
        parts = [
            chr(rng.randrange(0x110000)) if rng.random() < 0.3 else rng.choice(special)
            for _ in range(rng.randint(0, 12))
        ]
        text = "".join(parts)
        lenient = parse(text)
        try:
            strict = parse(text, strict=True)
        except CacheControlError as error:
            assert error.offset is not None and 0 <= error.offset <= len(text)
            assert len(str(error)) < 120
        else:
            assert strict == lenient
            # A value strict mode accepts is one build can write back unless it holds
            # obs-text, which build refuses, or a directive whose argument it cannot carry.
            with contextlib.suppress(CacheControlError):
                assert list(parse(build(strict), strict=True)) == list(strict)
        targeted = parse_targeted(text)
        assert targeted is None or isinstance(targeted, CacheControl)
        name, chosen = select(
            {"CDN-Cache-Control": text, "Cache-Control": text}, ["cdn-cache-control"]
        )
        assert chosen == (targeted if name == "cdn-cache-control" else lenient)
