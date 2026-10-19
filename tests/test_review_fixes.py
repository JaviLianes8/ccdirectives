"""Regression tests for the findings of the independent review; each failed before its fix."""

from __future__ import annotations

import http.client
import io
import json
import sys

import pytest

from ccdirectives import (
    DELTA_MAX,
    CacheControl,
    CacheControlError,
    assess,
    build,
    build_targeted,
    current_age,
    may_store,
    parse,
    parse_targeted,
    select,
)
from ccdirectives._cli import main


def test_a_bare_directive_before_junk_survives() -> None:
    assert parse("no-cache; no-store").no_cache
    assert parse("no-store x, public").directives == {"no-store": True, "public": True}
    assert not may_store(parse("private; no-store"), shared=True)


def test_immutable_with_an_argument_is_not_generated() -> None:
    with pytest.raises(CacheControlError, match="takes no argument"):
        build(CacheControl({"immutable": "x"}))
    with pytest.raises(CacheControlError, match="takes no argument"):
        build_targeted(CacheControl({"immutable": "x"}))
    with pytest.raises(CacheControlError, match="takes no argument"):
        parse("immutable=x", strict=True, context="response")
    assert parse("immutable=x").immutable


def test_select_reads_header_objects_and_refuses_a_string_target() -> None:
    raw = b"Cache-Control: max-age=60\r\nCDN-Cache-Control: max-age=600\r\n\r\n"
    message = http.client.parse_headers(io.BytesIO(raw))
    assert select(message) == ("CDN-Cache-Control", CacheControl({"max-age": 600}))
    with pytest.raises(TypeError, match="not one string"):
        select({}, "CDN-Cache-Control")


def test_digit_strings_are_delta_seconds_everywhere() -> None:
    cc = CacheControl({"max-age": "600"})
    assert cc.max_age == 600 and assess(cc, age=0).fresh
    huge = CacheControl({"max-age": "1" * 5000})
    assert build(huge) == f"max-age={DELTA_MAX}"
    assert build_targeted(huge) == f"max-age={DELTA_MAX}"


def test_an_empty_private_list_is_unqualified() -> None:
    assert not may_store(parse('private=""'), shared=True)
    assert not may_store(parse('private="a b"'), shared=True)


def test_arguments_of_the_wrong_type_are_refused() -> None:
    with pytest.raises(TypeError, match="age must be an int"):
        assess(parse("max-age=5"), age=True)
    with pytest.raises(TypeError, match="age must be an int"):
        assess(parse("max-age=5"), age=4.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="age_value"):
        current_age(date_value=0, request_time=0, response_time=0, now=0, age_value=-50)
    with pytest.raises(TypeError, match="dict"):
        CacheControl([("a", 1)])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="decode"):
        parse_targeted(b"max-age=5")  # type: ignore[arg-type]


class _Stdin:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


def _cli(monkeypatch: pytest.MonkeyPatch, args: list[str], stdin: bytes = b"") -> tuple[int, str]:
    monkeypatch.setattr(sys, "stdin", _Stdin(stdin))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    return main(args), out.getvalue()


def test_the_command_line_reads_age_expires_and_folded_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = b"HTTP/1.1 200 OK\r\nAge: 5000\r\nCache-Control: max-age=60,\r\n  public\r\n\r\n"
    code, out = _cli(monkeypatch, [], head)
    report = json.loads(out)
    assert code == 0 and report["age"] == 5000 and not report["fresh"]
    assert report["directives"] == {"max-age": 60, "public": True}
    assert json.loads(_cli(monkeypatch, ["--age", "1"], head)[1])["fresh"]
    dated = (
        b"HTTP/1.1 200 OK\r\nDate: Tue, 13 Oct 2026 10:00:00 GMT\r\n"
        b"Expires: Wed, 13 Oct 2027 10:00:00 GMT\r\n\r\n"
    )
    report = json.loads(_cli(monkeypatch, [], dated)[1])
    assert report["lifetime"] == 365 * 86400 and report["fresh"]
    broken = b"HTTP/1.1 200 OK\r\nDate: Tue, 13 Oct 2026 10:00:00 GMT\r\nExpires: 0\r\n\r\n"
    assert json.loads(_cli(monkeypatch, [], broken)[1])["lifetime"] == 0


def test_the_command_line_checks_a_head_with_the_response_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = b'HTTP/1.1 200 OK\r\nCache-Control: no-cache="ETag", max-stale=soon\r\n\r\n'
    assert _cli(monkeypatch, ["--strict"], head)[0] == 0
    request_only = b"HTTP/1.1 200 OK\r\nCache-Control: s-maxage\r\n\r\n"
    assert _cli(monkeypatch, ["--strict"], request_only)[0] == 1


def test_the_command_line_accepts_a_value_with_its_field_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code, out = _cli(monkeypatch, ["Cache-Control: max-age=60"])
    assert code == 0 and json.loads(out)["directives"] == {"max-age": 60}
