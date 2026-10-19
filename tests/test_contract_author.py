"""Contracts added when the author mutation round found promises no test pinned."""

from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace

import pytest

from ccdirectives import (
    CacheControl,
    CacheControlError,
    build,
    build_targeted,
    parse,
    parse_targeted,
    select,
)
from ccdirectives._cli import main


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


def test_names_are_folded_before_the_rules_apply() -> None:
    policy = parse("MAX-AGE=5, max-age=3, ZZ-TOP")
    assert policy.directives == {"max-age": 5, "zz-top": True}
    assert policy.duplicates == frozenset({"max-age"})


def test_a_semicolon_is_not_a_separator() -> None:
    with pytest.raises(CacheControlError) as caught:
        parse("no-store;private", strict=True)
    assert (caught.value.reason, caught.value.offset) == ("expected ',' after a directive", 8)


def test_a_structured_boolean_is_only_0_or_1() -> None:
    assert parse_targeted("max-age=60, x=?1") is not None
    assert parse_targeted("max-age=60, x=?2") is None


def test_select_combines_every_cache_control_line() -> None:
    name, policy = select([("Cache-Control", "max-age=60"), ("cache-control", "no-store")], [])
    assert name == "Cache-Control"
    assert policy.directives == {"max-age": 60, "no-store": True}


def _head(monkeypatch: pytest.MonkeyPatch, head: bytes, *args: str) -> dict[str, object]:
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(head)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main(list(args)) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


DATE = b"Date: Tue, 13 Oct 2026 10:00:00 GMT\r\n"


def test_the_head_reader_follows_the_field_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    lower = b"HTTP/1.1 200 OK\r\nage: 5000\r\ncache-control: max-age=60\r\n\r\n"
    assert _head(monkeypatch, lower)["age"] == 5000
    body = b"HTTP/1.1 200 OK\r\nCache-Control: max-age=60\r\n\r\nCache-Control: no-store\r\n"
    assert _head(monkeypatch, body)["directives"] == {"max-age": 60}
    spaced = b"HTTP/1.1 200 OK\r\nCache-Control: max-age=60\r\nX-Note : a\r\n , no-store\r\n\r\n"
    assert _head(monkeypatch, spaced)["directives"] == {"max-age": 60}


def test_an_expires_without_a_time_zone_means_already_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    zoned = b"HTTP/1.1 200 OK\r\n" + DATE + b"Expires: Wed, 13 Oct 2027 10:00:00 GMT\r\n\r\n"
    assert _head(monkeypatch, zoned)["lifetime"] == 365 * 86400
    naive = b"HTTP/1.1 200 OK\r\n" + DATE + b"Expires: Wed, 13 Oct 2027 10:00:00\r\n\r\n"
    assert _head(monkeypatch, naive)["lifetime"] == 0


def test_expires_does_not_apply_to_a_targeted_field(monkeypatch: pytest.MonkeyPatch) -> None:
    head = (
        b"HTTP/1.1 200 OK\r\n" + DATE + b"Expires: Wed, 13 Oct 2027 10:00:00 GMT\r\n"
        b"Cache-Control: public\r\nCDN-Cache-Control: public\r\n\r\n"
    )
    assert _head(monkeypatch, head)["lifetime"] == 365 * 86400
    report = _head(monkeypatch, head, "--shared")
    assert report["field"] == "CDN-Cache-Control" and report["lifetime"] is None
