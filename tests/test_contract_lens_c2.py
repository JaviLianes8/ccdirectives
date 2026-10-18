"""Contracts for the second round of QA lens c: plain reads of every value and name."""

from __future__ import annotations

import io
import sys
from typing import Any

import pytest

from ccdirectives import (
    DELTA_MAX,
    CacheControl,
    CacheControlError,
    _cli,
    _cliio,
    assess,
    build,
    build_targeted,
    current_age,
    freshness_lifetime,
    parse,
    select,
)

HEADER = 'no-store, max-stale, private="a", x-ext, max-age=5'


class _Lying(dict):  # type: ignore[type-arg]
    def get(self, key: Any, default: Any = None) -> Any:
        return False if key in ("no-store", "max-stale", "private", "no-cache") else 0

    def __iter__(self) -> Any:
        return iter(["evil"])

    def __contains__(self, key: object) -> bool:
        return False

    def __len__(self) -> int:
        return 0

    def __setitem__(self, key: Any, value: Any) -> None:
        pass

    def items(self) -> Any:
        return [("x-evil", 1)]


def _lying() -> CacheControl:
    policy = parse(HEADER)
    policy.directives = _Lying(policy.directives)
    return policy


def test_a_dict_subclass_cannot_steer_any_read() -> None:
    policy = _lying()
    assert policy.no_store and policy.max_stale == DELTA_MAX
    assert policy.private_fields == ("a",) and policy.extensions() == ("x-ext",)
    assert "max-age" in policy and len(policy) == 5 and policy.get("max-age") == 5
    assert list(policy) == ["no-store", "max-stale", "private", "x-ext", "max-age"]
    assert build(policy) == build(parse(HEADER))
    policy["public"] = True
    assert dict.get(policy.directives, "public") is True


class _Digits(str):
    def __iter__(self) -> Any:
        return iter("5")

    def lstrip(self, *args: Any) -> str:
        return "5"


def test_a_str_subclass_value_is_read_as_plain_text() -> None:
    policy = parse("max-age=0")
    policy.directives["max-age"] = _Digits("abc")
    assert policy.max_age is None


class _NeverEqual(str):
    __hash__ = str.__hash__

    def __eq__(self, other: object) -> bool:
        return False


class _AlwaysRequest(str):
    def __hash__(self) -> int:
        return hash("request")

    def __eq__(self, other: object) -> bool:
        return True


def test_contexts_are_read_as_plain_text() -> None:
    accepted = parse("only-if-cached=1", strict=True, context=_NeverEqual("response"))  # type: ignore[arg-type]
    assert accepted.directives == {"only-if-cached": "1"}
    with pytest.raises(CacheControlError):
        parse("only-if-cached=1", strict=True, context=_NeverEqual("request"))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="context must be"):
        CacheControl({"a": 1}).extensions(_AlwaysRequest("zzz"))  # type: ignore[arg-type]


class _LyingList(list):  # type: ignore[type-arg]
    def __len__(self) -> int:
        return 2

    def __iter__(self) -> Any:
        return iter(("Cache-Control", "no-store"))


def test_select_reads_a_list_pair_by_its_real_items() -> None:
    pair: Any = _LyingList(["Cache-Control", "max-age=5"])
    assert select([pair])[1].directives == {"max-age": 5}


def test_a_spoofed_policy_is_a_type_error_with_its_own_message() -> None:
    fake: Any = type("FakeCC", (), {"__class__": property(lambda self: CacheControl)})()
    with pytest.raises(TypeError, match="response must be a CacheControl"):
        assess(fake, age=1)
    with pytest.raises(TypeError, match="build_targeted takes a CacheControl"):
        build_targeted(fake)


def test_time_arithmetic_is_exact_and_clamped() -> None:
    assert freshness_lifetime(CacheControl(), expires=10**20 + 100, date=1e20) == 100
    late = 10**20 + 100
    assert current_age(date_value=1e20, request_time=late, response_time=late, now=late) == 100
    # A Date after the response time gives an apparent age of 0, not a negative one.
    assert current_age(date_value=100, request_time=50, response_time=10, now=20) == 10


class _Formatted(str):
    def __format__(self, spec: str) -> str:
        return "x\r\nSet-Cookie: a=1"

    def __str__(self) -> str:
        return "x\r\nSet-Cookie: a=1"


def test_a_name_set_directly_is_written_as_plain_text() -> None:
    policy = CacheControl()
    policy.directives[_Formatted("x")] = "v"
    assert build(policy) == "x=v"


def test_deleting_a_missing_name_reports_it_cut() -> None:
    with pytest.raises(KeyError) as caught:
        del parse("max-age=1")["y" * 1000]
    assert len(str(caught.value)) < 60


class _ClosedStream(io.StringIO):
    def write(self, text: str) -> int:
        raise ValueError("I/O operation on closed file.")


def test_a_closed_stderr_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stderr", _ClosedStream())
    _cliio.report("x")


def test_a_closed_stdout_object_exits_1_quietly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    closed = io.StringIO()
    closed.close()
    monkeypatch.setattr(sys, "stdout", closed)
    assert _cli.main(["max-age=1"]) == 1
    assert capsys.readouterr().err == ""
