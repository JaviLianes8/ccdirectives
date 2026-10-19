"""Contracts from the fourth QA round: the oldest leap day and the first valid year."""

from __future__ import annotations

import calendar
import io
import json
import sys
from types import SimpleNamespace

import pytest

from ccdirectives._cli import main
from ccdirectives._dates import http_date

# In 2300 to 2349 the latest year 00 with 29 February (2000) is five centuries back.
YEAR_2310 = float(calendar.timegm((2310, 1, 1, 0, 0, 0, 0, 0, 0)))
YEAR_ONE = float(calendar.timegm((1, 1, 1, 0, 0, 0, 0, 0, 0)))
LEAP_DAY = "Tuesday, 29-Feb-00 00:00:00 GMT"


def _run(monkeypatch: pytest.MonkeyPatch, head: str) -> dict[str, object]:
    raw = ("HTTP/1.1 200 OK\r\n" + head + "\r\n").encode("latin-1")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main([]) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


def test_february_29_read_in_2310_is_five_centuries_back() -> None:
    assert http_date(LEAP_DAY, now=YEAR_2310) == calendar.timegm((2000, 2, 29, 0, 0, 0))


def test_february_29_read_in_2310_keeps_its_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.time", lambda: YEAR_2310)
    head = (
        f"Date: {LEAP_DAY}\r\nExpires: Tuesday, 29-Feb-00 01:00:00 GMT\r\nCache-Control: public\r\n"
    )
    assert _run(monkeypatch, head)["lifetime"] == 3600


@pytest.mark.parametrize("value", ["Mon, 01 Jan 0001 00:00:00 GMT", "Mon Jan  1 00:00:00 0001"])
def test_year_0001_is_read_as_written(value: str) -> None:
    assert YEAR_ONE == -62135596800.0
    assert http_date(value) == YEAR_ONE


def test_an_expires_in_year_0001_keeps_its_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    head = (
        "Date: Mon, 01 Jan 0001 00:00:00 GMT\r\n"
        "Expires: Mon, 01 Jan 0001 01:00:00 GMT\r\n"
        "Cache-Control: public\r\n"
    )
    assert _run(monkeypatch, head)["lifetime"] == 3600
