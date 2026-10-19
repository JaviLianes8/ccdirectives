"""Contracts from the second QA round: absent values, the Age list and HTTP-date edges."""

from __future__ import annotations

import calendar
import io
import json
import sys
from types import SimpleNamespace

import pytest

from ccdirectives import CacheControl, build, build_targeted
from ccdirectives._cli import main
from ccdirectives._dates import http_date
from ccdirectives._head import age_of

SUNDAY = calendar.timegm((1994, 11, 6, 8, 49, 37, 0, 0, 0))
NOON_2026 = calendar.timegm((2026, 10, 19, 12, 0, 0, 0, 0, 0))
DATE = "Date: Sun, 06 Nov 1994 08:49:37 GMT\r\n"


def _run(monkeypatch: pytest.MonkeyPatch, head: str) -> dict[str, object]:
    raw = ("HTTP/1.1 200 OK\r\n" + head + "\r\n").encode("latin-1")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main([]) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


def test_a_false_set_directly_is_stored_but_not_present() -> None:
    cc = CacheControl({"max-age": 5})
    cc.directives["public"] = False
    assert (cc.has("public"), cc.public, cc.get("public")) == (False, False, False)
    assert ("public" in cc, len(cc), list(cc), list(cc.keys())) == (
        True,
        2,
        ["max-age", "public"],
        ["max-age", "public"],
    )
    assert dict(cc) == {"max-age": 5, "public": False} and list(cc.values()) == [5, False]
    assert list(cc.items()) == [("max-age", 5), ("public", False)]
    cc.directives["x-a"] = False
    assert cc.extensions() == ("x-a",)
    assert build(cc) == "max-age=5" and build_targeted(cc) == "max-age=5"
    assert cc == CacheControl({"max-age": 5})


def test_a_false_repeat_of_a_present_name_is_not_a_duplicate() -> None:
    cc = CacheControl({"public": True, "PUBLIC": False})
    assert (cc.directives, cc.duplicates) == ({"public": True}, frozenset())


@pytest.mark.parametrize(
    ("values", "age"),
    [(", 100", 100), (" ,\t, 7", 7), (",,", 0), (", x, 5", 0), ("", 0)],
)
def test_empty_age_members_are_skipped(values: str, age: int) -> None:
    assert age_of([("Age", values)]) == age


def test_age_lines_form_one_list(monkeypatch: pytest.MonkeyPatch) -> None:
    assert age_of([("Age", ""), ("X", "1"), ("age", "100")]) == 100
    assert age_of([("Age", "30"), ("Age", "100")]) == 30
    for age in ("Age: , 100\r\n", "Age:\r\nAge: 100\r\n"):
        report = _run(monkeypatch, "Cache-Control: max-age=60\r\n" + age)
        assert (report["age"], report["fresh"], report["reusable"]) == (100, False, False)


@pytest.mark.parametrize(
    "value",
    [
        "Sun, 06 Nov 1994 08:49:37 gmt",
        "Sunday, 06-Nov-94 08:49:37 Gmt",
        "SUN, 06 NOV 1994 08:49:37 GMT",
        "SUNDAY, 06-NOV-94 08:49:37 GMT",
        "SUN NOV  6 08:49:37 1994",
        "sun, 06 nov 1994 08:49:37 gMt",
    ],
)
def test_names_and_gmt_ignore_case(value: str) -> None:
    assert http_date(value, now=NOON_2026) == SUNDAY


def test_gmt_in_any_case_keeps_the_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    head = DATE + "Expires: Sun, 06 Nov 1994 09:49:37 gmt\r\n"
    assert _run(monkeypatch, head)["lifetime"] == 3600
    head = "Date: Sun, 06 Nov 1994 08:49:37 gmt\r\nExpires: Sun, 06 Nov 1994 09:49:37 GMT\r\n"
    assert _run(monkeypatch, head)["lifetime"] == 3600


@pytest.mark.parametrize(
    "value",
    [
        "Sunday, 06-Nov-94 08:49:37 EST",
        "Sunday, 06-Nov-94 08:49:37 UTC",
        "Xyz, 06 Nov 1994 08:49:37 GMT",
        "Sundae, 06-Nov-94 08:49:37 GMT",
        "Xyz Nov  6 08:49:37 1994",
        "Sun, 06-Nov-94 08:49:37 GMT",
        "Sunday, 06 Nov 1994 08:49:37 GMT",
        "Sun, 00 Nov 1994 08:49:37 GMT",
        "Sunday, 00-Nov-94 08:49:37 GMT",
        "Sun Nov  0 08:49:37 1994",
        "Sun, 06 Nov 1994 08:49:37 GMTX",
        "Sun, 06 Nov 1994 08:49:37 GMT ",
        " Sun, 06 Nov 1994 08:49:37 GMT",
        "Sunday, 06-Nov-94 08:49:37 GMT ",
        "Sun Nov  6 08:49:37 1994 ",
        "Sun Nov  6 08:49:37 94",
        "Sun Nov  6 08:49:37 994",
        "Sun Nov  6 08:49:37 01994",
    ],
)
def test_malformed_dates_do_not_parse(value: str) -> None:
    assert http_date(value, now=NOON_2026) is None


@pytest.mark.parametrize(
    "expires",
    [
        "Sunday, 06-Nov-94 09:49:37 EST",
        "Xyz, 06 Nov 1994 09:49:37 GMT",
        "Sun, 06-Nov-94 09:49:37 GMT",
        "Sun, 06 Nov 1994 09:49:37 GMTX",
        "Sun Nov  6 09:49:37 94",
    ],
)
def test_a_malformed_expires_means_already_expired(
    monkeypatch: pytest.MonkeyPatch, expires: str
) -> None:
    report = _run(monkeypatch, DATE + f"Expires: {expires}\r\nCache-Control: public\r\n")
    assert (report["lifetime"], report["fresh"]) == (0, False)


def test_day_zero_is_not_the_last_day_of_the_month_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "Date: Mon, 31 Oct 1994 08:00:00 GMT\r\nExpires: Sun, 00 Nov 1994 09:00:00 GMT\r\n"
    assert _run(monkeypatch, head)["lifetime"] == 0


def test_second_sixty_is_the_next_second(monkeypatch: pytest.MonkeyPatch) -> None:
    after = calendar.timegm((2017, 1, 1, 0, 0, 0, 0, 0, 0))
    assert http_date("Sat, 31 Dec 2016 23:59:60 GMT") == after
    assert http_date("Saturday, 31-Dec-16 23:59:60 GMT", now=NOON_2026) == after
    assert http_date("Sat Dec 31 23:59:60 2016") == after
    assert http_date("Sat, 31 Dec 2016 23:59:61 GMT") is None
    head = "Date: Sat, 31 Dec 2016 23:59:00 GMT\r\nExpires: Sat, 31 Dec 2016 23:59:60 GMT\r\n"
    report = _run(monkeypatch, head)
    assert (report["lifetime"], report["fresh"]) == (60, True)


@pytest.mark.parametrize(
    ("value", "year"),
    [
        ("Thursday, 31-Dec-76 00:00:00 GMT", 1976),
        ("Tuesday, 19-Oct-76 12:00:01 GMT", 1976),
        ("Monday, 19-Oct-76 12:00:00 GMT", 2076),
        ("Monday, 19-Oct-76 11:59:59 GMT", 2076),
        ("Thursday, 01-Jan-76 00:00:00 GMT", 2076),
        ("Monday, 19-Oct-26 12:00:00 GMT", 2026),
        ("Friday, 19-Oct-27 12:00:00 GMT", 2027),
    ],
)
def test_the_fifty_year_rule_compares_instants(value: str, year: int) -> None:
    stamp = http_date(value, now=NOON_2026)
    assert stamp is not None
    assert (
        calendar.timegm((year, 1, 1, 0, 0, 0)) <= stamp < calendar.timegm((year + 1, 1, 1, 0, 0, 0))
    )


def test_a_rfc850_expires_just_past_fifty_years_is_in_the_past(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("time.time", lambda: float(NOON_2026))
    head = DATE + "Expires: Friday, 31-Dec-76 00:00:00 GMT\r\n"
    report = _run(monkeypatch, head)
    assert (report["lifetime"], report["fresh"]) == (0, False)
