"""Contracts from the sixth QA round: an Age member with whitespace inside is invalid."""

from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace

import pytest

from ccdirectives._cli import main
from ccdirectives._head import age_of

INNER_SPACE = ["12 34", "1 2, 3", "12\t34", " 12 34 , 5"]


def _run(monkeypatch: pytest.MonkeyPatch, head: str) -> dict[str, object]:
    raw = ("HTTP/1.1 200 OK\r\n" + head + "\r\n").encode("latin-1")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main([]) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


@pytest.mark.parametrize("value", INNER_SPACE)
def test_an_age_member_with_inner_whitespace_counts_as_zero(value: str) -> None:
    # The first member is not delta-seconds, so the whole field is ignored.
    assert age_of([("Age", value)]) == 0


@pytest.mark.parametrize("value", INNER_SPACE)
def test_an_age_member_with_inner_whitespace_reports_age_zero(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    report = _run(monkeypatch, f"Age: {value}\r\nCache-Control: max-age=60\r\n")
    assert report["age"] == 0
