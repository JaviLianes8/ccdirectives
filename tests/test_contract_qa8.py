"""Contracts from the eighth QA round: only a field named exactly Age is the Age field."""

from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace

import pytest

from ccdirectives._cli import main
from ccdirectives._head import age_of

# Names that contain "age" without being Age (RFC 9110 field names compare whole).
LOOKALIKES = ["X-Age", "Age-Hint", "X-Cache-Age", "Ages", "Page", "Image-Age"]


def _run(monkeypatch: pytest.MonkeyPatch, head: str) -> dict[str, object]:
    raw = ("HTTP/1.1 200 OK\r\n" + head + "\r\n").encode("latin-1")
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert main([]) == 0
    report: dict[str, object] = json.loads(out.getvalue())
    return report


@pytest.mark.parametrize("name", LOOKALIKES)
def test_a_field_whose_name_only_contains_age_is_ignored(name: str) -> None:
    assert age_of([(name, "5")]) == 0


@pytest.mark.parametrize("name", LOOKALIKES)
def test_the_real_age_field_is_read_next_to_a_lookalike(name: str) -> None:
    assert age_of([(name, "7"), ("Age", "3")]) == 3
    assert age_of([("Age", "3"), (name, "7")]) == 3


@pytest.mark.parametrize("name", ["AGE", "age", "aGe"])
def test_the_age_field_name_is_case_insensitive(name: str) -> None:
    assert age_of([("X-Age", "9"), (name, "4")]) == 4


def test_a_cache_age_field_does_not_change_the_reported_age(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _run(monkeypatch, "X-Cache-Age: 500\r\nCache-Control: max-age=60\r\n")
    assert report["age"] == 0
    assert report["fresh"] is True
