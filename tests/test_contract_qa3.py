"""Contracts from the third QA round: the 50-year rule in detail and strict date forms."""

from __future__ import annotations

import calendar
import io
import json
import sys
import time
from types import SimpleNamespace

import pytest

from ccdirectives._cli import main
from ccdirectives._dates import http_date

DATE = "Date: Sun, 06 Nov 1994 08:49:37 GMT\r\n"
# A clock whose minutes and seconds are not zero, so the whole instant is compared.
HALF_PAST = calendar.timegm((2026, 10, 19, 12, 30, 30, 0, 0, 0))
YEAR_3000 = calendar.timegm((3000, 11, 6, 8, 49, 37, 0, 0, 0))
CAP = 2147483648


def _run(monkeypatch: pytest.MonkeyPatch, head: str) -> dict[str, object]:
    raw = ("HTTP/1.1 200 OK\r\n" + head + "\r\n").encode("latin-1")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main([]) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


def _year(stamp: float | None) -> int:
    assert stamp is not None
    return time.gmtime(stamp).tm_year


@pytest.mark.parametrize(
    ("now", "year"),
    [((2060, 1, 1), 2000), ((2160, 1, 1), 2000), ((2250, 1, 1), 2000), ((2026, 10, 19), 2000)],
)
def test_february_29_takes_the_latest_year_that_has_it(now: tuple[int, ...], year: int) -> None:
    clock = calendar.timegm((*now, 0, 0, 0))
    stamp = http_date("Tuesday, 29-Feb-00 00:00:00 GMT", now=clock)
    assert stamp == calendar.timegm((year, 2, 29, 0, 0, 0))


def test_february_29_read_in_2060_keeps_its_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.time", lambda: float(calendar.timegm((2060, 1, 1, 0, 0, 0))))
    head = (
        "Date: Tuesday, 29-Feb-00 00:00:00 GMT\r\n"
        "Expires: Tuesday, 29-Feb-00 01:00:00 GMT\r\n"
        "Cache-Control: public\r\n"
    )
    assert _run(monkeypatch, head)["lifetime"] == 3600


@pytest.mark.parametrize("value", ["Sun, 06 Nov 3000 08:49:37 GMT", "Sun Nov  6 08:49:37 3000"])
def test_four_digit_years_far_ahead_are_read_as_written(value: str) -> None:
    assert http_date(value) == YEAR_3000
    assert http_date(value, now=HALF_PAST) == YEAR_3000


@pytest.mark.parametrize("value", ["Sun, 06 Nov 3000 08:49:37 GMT", "Sun Nov  6 08:49:37 3000"])
def test_a_far_future_expires_is_fresh_up_to_the_cap(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    head = (
        "Date: Mon, 19 Oct 2026 12:00:00 GMT\r\n" + f"Expires: {value}\r\nCache-Control: public\r\n"
    )
    report = _run(monkeypatch, head)
    assert (report["lifetime"], report["fresh"]) == (CAP, True)


@pytest.mark.parametrize(
    ("value", "year"),
    [
        ("Monday, 19-Oct-76 12:30:15 GMT", 2076),
        ("Monday, 19-Oct-76 12:30:30 GMT", 2076),
        ("Monday, 19-Oct-76 12:30:31 GMT", 1976),
        ("Monday, 19-Oct-76 12:15:00 GMT", 2076),
        ("Monday, 19-Oct-76 12:45:00 GMT", 1976),
    ],
)
def test_the_fifty_year_rule_compares_minutes_and_seconds(value: str, year: int) -> None:
    assert _year(http_date(value, now=HALF_PAST)) == year


@pytest.mark.parametrize(
    ("expires", "lifetime"),
    [
        ("Monday, 19-Oct-76 12:30:15 GMT", 1577925015),
        ("Monday, 19-Oct-76 12:15:00 GMT", 1577924100),
    ],
)
def test_the_command_line_uses_the_whole_current_instant(
    monkeypatch: pytest.MonkeyPatch, expires: str, lifetime: int
) -> None:
    monkeypatch.setattr("time.time", lambda: float(HALF_PAST))
    head = "Date: Mon, 19 Oct 2026 12:00:00 GMT\r\n" + f"Expires: {expires}\r\n"
    report = _run(monkeypatch, head)
    assert (report["lifetime"], report["fresh"]) == (lifetime, True)


@pytest.mark.parametrize(
    "value",
    [
        "Sun, 06 Nov 1994 08:49:37 GM",
        "Sunday, 06-Nov-94 08:49:37 GM",
        "Sun, 06 Nov 1994 08:49:37",
        "Sunday Nov  6 08:49:37 1994",
        "SUNDAY Nov  6 08:49:37 1994",
    ],
)
def test_truncated_zones_and_long_asctime_days_do_not_parse(value: str) -> None:
    assert http_date(value, now=HALF_PAST) is None


@pytest.mark.parametrize("expires", ["Sun, 06 Nov 1994 09:49:37 GM", "Sunday Nov  6 09:49:37 1994"])
def test_a_truncated_or_long_day_expires_is_already_expired(
    monkeypatch: pytest.MonkeyPatch, expires: str
) -> None:
    report = _run(monkeypatch, DATE + f"Expires: {expires}\r\nCache-Control: public\r\n")
    assert (report["lifetime"], report["fresh"]) == (0, False)
