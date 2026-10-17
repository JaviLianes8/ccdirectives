"""Every public function refuses the wrong argument types with a short, typed error."""

from __future__ import annotations

from typing import Any

import pytest

import ccdirectives as cc
from ccdirectives import parse


def test_public_functions_refuse_the_wrong_structure() -> None:
    raw: Any = {"max-age": 5}
    api: Any = cc
    for call, word in [
        (lambda: cc.build(raw), "build takes a CacheControl, not dict"),
        (lambda: cc.build_targeted(raw), "build_targeted takes a CacheControl, not dict"),
        (lambda: cc.assess(raw, age=1), "response must be a CacheControl, not dict"),
        (lambda: cc.assess(parse(""), age=1, request=raw), "request must be a CacheControl"),
        (lambda: cc.freshness_lifetime(raw), "response must be a CacheControl"),
        (lambda: cc.may_store(raw), "response must be a CacheControl"),
        (lambda: parse(raw.values()), "field lines must be str, not int"),
        (lambda: api.parse(5), "header must be str or an iterable of str"),
        (lambda: api.parse(b"a"), "decode the header value"),
        (lambda: api.parse_targeted([1]), "field lines must be str, not int"),
        (lambda: api.parse_targeted(None), "value must be str or an iterable of str"),
        (lambda: api.select({"Cache-Control": b"x"}), "field values must be str, not bytes"),
        (lambda: api.select({}, [b"x"]), "target names must be str, not bytes"),
        (lambda: api.select("Cache-Control: x"), "headers is a mapping"),
        (lambda: api.CacheControl({}, "x"), "duplicates must be an iterable of names"),
    ]:
        with pytest.raises(TypeError, match=word):
            call()  # type: ignore[no-untyped-call]


@pytest.mark.parametrize(
    "context", ["x" * 100_000, "Request", 1, ["request"]], ids=["huge", "case", "int", "list"]
)
def test_an_unknown_context_is_refused_without_echoing_it(context: Any) -> None:
    for call in (lambda: parse("a", context=context), lambda: parse("a").extensions(context)):
        with pytest.raises(ValueError) as caught:
            call()
        assert str(caught.value) == "context must be 'request', 'response' or None"
