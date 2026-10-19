"""Contracts from the first QA round: HTTP dates, the Age field and the head reader."""

from __future__ import annotations

import calendar
import io
import json
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from ccdirectives._cli import main
from ccdirectives._dates import http_date
from ccdirectives._head import age_of, head_fields

# RFC 9110 section 5.6.7 gives this instant in its three formats.
SUNDAY = calendar.timegm((1994, 11, 6, 8, 49, 37, 0, 0, 0))
NOW_2026 = calendar.timegm((2026, 10, 19, 0, 0, 0, 0, 0, 0))
EPOCH = datetime(1970, 1, 1)
NOW_1990 = calendar.timegm((1990, 1, 1, 0, 0, 0, 0, 0, 0))


def _run(monkeypatch: pytest.MonkeyPatch, head: str, *args: str) -> dict[str, object]:
    raw = ("HTTP/1.1 200 OK\r\n" + head + "\r\n").encode("latin-1")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main(list(args)) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


@pytest.mark.parametrize(
    "value",
    ["Sun, 06 Nov 1994 08:49:37 GMT", "Sunday, 06-Nov-94 08:49:37 GMT", "Sun Nov  6 08:49:37 1994"],
)
def test_the_three_http_date_formats_are_accepted(value: str) -> None:
    assert http_date(value, now=NOW_2026) == SUNDAY


def test_an_asctime_head_gives_the_same_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    for date in ("Sun Nov  6 08:49:37 1994", "Sun, 06 Nov 1994 08:49:37 GMT"):
        head = f"Date: {date}\r\nExpires: Sun Nov  6 09:49:37 1994\r\n"
        assert _run(monkeypatch, head)["lifetime"] == 3600


@pytest.mark.parametrize(
    "value",
    [
        "Sun, 06 Nov 1994 09:49:37 EST",
        "Sun, 06 Nov 1994 09:49:37 +0200",
        "Sun, 06 Nov 1994 09:49:37 +0000",
        "Thu, 01 Jan 49 00:00:00 GMT",
        "Sun, 06 Nov 1994 24:00:00 GMT",
        "Mon, 31 Feb 1994 00:00:00 GMT",
        "Sun Nov 6 08:49:37 1994",
        "Sun, 06 Nov 1994 08:49:37",
        "06 Nov 1994 08:49:37 GMT",
        "Sun, 06 Nov 0000 08:49:37 GMT",
        "Sun, \uff10\uff16 Nov 1994 08:49:37 GMT",
    ],
)
def test_other_dates_do_not_parse(value: str) -> None:
    assert http_date(value, now=NOW_2026) is None


def test_an_expires_in_another_zone_means_already_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "Date: Sun, 06 Nov 1994 08:49:37 GMT\r\nExpires: Sun, 06 Nov 1994 09:49:37 EST\r\n"
    assert _run(monkeypatch, head)["lifetime"] == 0


def test_a_four_digit_year_is_read_as_written(monkeypatch: pytest.MonkeyPatch) -> None:
    assert http_date("Thu, 01 Jan 0099 00:00:00 GMT") == calendar.timegm((99, 1, 1, 0, 0, 0))
    head = "Date: Mon, 19 Oct 2026 00:00:00 GMT\r\nExpires: Thu, 01 Jan 0049 00:00:00 GMT\r\n"
    report = _run(monkeypatch, head + "Cache-Control: public\r\n")
    assert (report["lifetime"], report["fresh"], report["reusable"]) == (0, False, False)


def test_rfc850_years_follow_the_fifty_year_rule() -> None:
    def year(value: str, now: float) -> int:
        stamp = http_date(value, now=now)
        assert stamp is not None
        return (EPOCH + timedelta(seconds=stamp)).year

    assert year("Tuesday, 01-Jan-70 00:00:00 GMT", NOW_2026) == 2070
    assert year("Thursday, 01-Jan-77 00:00:00 GMT", NOW_2026) == 1977
    assert year("Tuesday, 01-Jan-70 00:00:00 GMT", NOW_1990) == 1970
    assert year("Monday, 01-Jan-40 00:00:00 GMT", NOW_1990) == 2040
    assert year("Tuesday, 01-Jan-46 00:00:00 GMT", NOW_1990) == 1946
    assert year("Friday, 01-Jan-10 00:00:00 GMT", calendar.timegm((2090, 1, 1, 0, 0, 0))) == 2110


def test_a_head_with_rfc850_years_past_2068(monkeypatch: pytest.MonkeyPatch) -> None:
    head = "Date: Monday, 01-Jan-46 00:00:00 GMT\r\nExpires: Tuesday, 01-Jan-70 00:00:00 GMT\r\n"
    report = _run(monkeypatch, head)
    assert (report["lifetime"], report["fresh"]) == (757382400, True)


def test_a_list_age_uses_its_first_member(monkeypatch: pytest.MonkeyPatch) -> None:
    assert age_of([("Age", "100, 5")]) == 100 and age_of([("Age", " 7 ,x")]) == 7
    assert age_of([("Age", "x, 5")]) == 0 and age_of([("Age", ", 5")]) == 5
    report = _run(monkeypatch, "Cache-Control: max-age=60\r\nAge: 100, 5\r\n")
    assert (report["age"], report["fresh"], report["reusable"]) == (100, False, False)


@pytest.mark.parametrize("space", ["\xa0", "\x0b", "\x0c", "\x1c", "\x85"])
def test_age_strips_only_spaces_and_tabs(space: str) -> None:
    assert age_of([("Age", space + "60")]) == 0 and age_of([("Age", "60" + space)]) == 0
    assert age_of([("Age", " \t60\t ")]) == 60


def test_a_field_with_whitespace_before_the_colon_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "HTTP/1.1 200 OK\r\nX-Cache : max-age=5\r\nCache-Control: no-store\r\n\r\n"
    assert head_fields(text) == [("Cache-Control", "no-store")]
    head = "X-Cache : max-age=5\r\nCache-Control: no-store\r\n"
    report = _run(monkeypatch, head, "--target", "X-Cache ")
    assert (report["field"], report["directives"]) == ("Cache-Control", {"no-store": True})


def test_repeated_targets_keep_their_order(monkeypatch: pytest.MonkeyPatch) -> None:
    head = "A-Cache-Control: max-age=1\r\nCDN-Cache-Control: max-age=2\r\n"
    first = _run(monkeypatch, head, "--target", "A-Cache-Control", "--target", "CDN-Cache-Control")
    assert first["field"] == "A-Cache-Control"
    second = _run(monkeypatch, head, "--target", "CDN-Cache-Control", "--target", "A-Cache-Control")
    assert second["field"] == "CDN-Cache-Control"


@pytest.mark.parametrize("prefix", ["cache-control:", "CACHE-CONTROL: ", "Cache-control:"])
def test_a_value_prefix_is_stripped_in_any_case(
    monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main([prefix + " max-age=5"]) == 0
    assert json.loads(out.getvalue())["directives"] == {"max-age": 5}
