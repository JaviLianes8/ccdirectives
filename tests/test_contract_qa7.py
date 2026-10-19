"""Contracts from the seventh QA round: Age is ASCII delta-seconds capped at 2^31."""

from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace

import pytest

from ccdirectives._cli import main
from ccdirectives._head import age_of

# Digits outside ASCII: Arabic-Indic, fullwidth and a superscript two (RFC 9110 DIGIT is 0-9).
NON_ASCII = ["\u0661\u0662", "\uff11\uff12", "\u00b2", "1\u00b2", "\uff11, 5"]


def _run(monkeypatch: pytest.MonkeyPatch, head: str) -> dict[str, object]:
    raw = ("HTTP/1.1 200 OK\r\n" + head + "\r\n").encode("latin-1")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main([]) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


@pytest.mark.parametrize("value", ["99999999999", "2147483649", "2147483648", "0" * 40 + "9" * 40])
def test_an_age_past_2_to_the_31_is_capped(value: str) -> None:
    # RFC 9111 section 1.2.2: a delta-seconds too large to hold is read as 2147483648.
    assert age_of([("Age", value)]) == 2147483648


def test_an_age_below_the_cap_is_kept() -> None:
    assert age_of([("Age", "2147483647")]) == 2147483647


@pytest.mark.parametrize("value", NON_ASCII)
def test_an_age_with_non_ascii_digits_counts_as_zero(value: str) -> None:
    assert age_of([("Age", value)]) == 0


@pytest.mark.parametrize("value", ["\u00b2", "\u00b9\u00b3", "1\u00b2, 5"])
def test_an_age_with_a_latin1_superscript_reports_age_zero(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    report = _run(monkeypatch, f"Age: {value}\r\n")
    assert report["age"] == 0


def test_a_huge_age_is_reported_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _run(monkeypatch, "Age: 99999999999\r\nCache-Control: max-age=60\r\n")
    assert report["age"] == 2147483648
