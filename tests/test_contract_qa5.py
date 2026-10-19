"""Contracts from the fifth QA round: minute 60 is not a time of day."""

from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace

import pytest

from ccdirectives._cli import main


def _run(monkeypatch: pytest.MonkeyPatch, head: str) -> dict[str, object]:
    raw = ("HTTP/1.1 200 OK\r\n" + head + "\r\n").encode("latin-1")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main([]) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


@pytest.mark.parametrize(
    "expires",
    [
        "Sun, 06 Nov 1994 09:60:00 GMT",
        "Sunday, 06-Nov-94 09:60:00 GMT",
        "Sun Nov  6 09:60:00 1994",
    ],
)
def test_an_expires_at_minute_60_means_already_expired(
    monkeypatch: pytest.MonkeyPatch, expires: str
) -> None:
    # Read as 10:00:00 it would give 7200 seconds; an invalid Expires gives none.
    head = f"Date: Sun, 06 Nov 1994 08:00:00 GMT\r\nExpires: {expires}\r\nCache-Control: public\r\n"
    assert _run(monkeypatch, head)["lifetime"] == 0
