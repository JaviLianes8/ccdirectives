from __future__ import annotations

import io
import json
import sys
from typing import Any

import pytest

from ccdirectives._cli import main


class _Stdin:
    def __init__(self, data: bytes) -> None:
        self.buffer = io.BytesIO(data)


def _run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    stdin: bytes = b"",
) -> tuple[int, Any, str]:
    monkeypatch.setattr(sys, "stdin", _Stdin(stdin))
    code = main(args)
    out, err = capsys.readouterr()
    return code, json.loads(out) if out else None, err


def test_a_value_on_the_command_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, report, _ = _run(monkeypatch, capsys, ["max-age=60, x-a, max-age=1", "--age", "30"])
    assert code == 0
    assert report == {
        "field": "Cache-Control",
        "directives": {"max-age": 60, "x-a": True},
        "duplicates": ["max-age"],
        "extensions": ["x-a"],
        "lifetime": 60,
        "age": 30,
        "fresh": True,
        "reusable": True,
        "stale_while_revalidate": False,
        "stale_if_error": False,
    }


def test_a_response_head_prefers_the_cdn_field_for_a_shared_cache(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    head = (
        b"HTTP/1.1 301 Moved\r\nCache-Control: no-store\r\n\r\n"
        b"HTTP/2 200\r\ncache-control: max-age=60, s-maxage=120\r\n"
        b"CDN-Cache-Control: max-age=600\r\nX-Note: caf\xe9\r\n\r\nCache-Control: no-store\r\n"
    )
    code, report, _ = _run(monkeypatch, capsys, ["--shared"], head)
    assert code == 0 and report["field"] == "CDN-Cache-Control" and report["lifetime"] == 600
    code, report, _ = _run(monkeypatch, capsys, ["--shared", "--target", "Other"], head)
    assert report["field"] == "Cache-Control" and report["lifetime"] == 120
    code, report, _ = _run(monkeypatch, capsys, [], head)
    assert report["field"] == "Cache-Control" and report["lifetime"] == 60


def test_a_bare_value_on_standard_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, report, _ = _run(monkeypatch, capsys, [], b"  no-cache, max-age=5\n")
    assert code == 0 and report["directives"] == {"no-cache": True, "max-age": 5}
    assert report["reusable"] is False


def test_strict_errors_exit_with_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, report, err = _run(monkeypatch, capsys, ["--strict", "max-age=x"])
    assert code == 1 and report is None
    assert "not delta-seconds at offset 0" in err
    head = b"HTTP/1.1 200 OK\nCache-Control: max-age=1\nCache-Control: max-age=2\n\n"
    code, _, err = _run(monkeypatch, capsys, ["--strict"], head)
    assert code == 1 and "repeated directive" in err


def test_negative_age_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as caught:
        _run(monkeypatch, capsys, ["--age", "-1", "max-age=1"])
    assert caught.value.code == 2
