"""Run the httpwg structured field test corpus against the dictionary and item parsers.

The corpus files are fetched into tests/upstream/sf (see MANIFEST.json); these tests skip
until `python scripts/fetch_upstream.py` has fetched them. List tests are out of scope:
targeted fields are dictionaries.
"""

from __future__ import annotations

import base64
import json
from decimal import Decimal
from typing import Any

import pytest
from conftest import read_upstream

from ccdirectives._sf import Date, DisplayString, Reader, StructuredError, Token
from ccdirectives._sfdict import parse_dictionary, parse_item, serialize_dictionary

FILES = [
    "binary",
    "boolean",
    "date",
    "dictionary",
    "display-string",
    "examples",
    "item",
    "key-generated",
    "large-generated",
    "number",
    "number-generated",
    "param-dict",
    "string",
    "string-generated",
    "token",
    "token-generated",
]


def _plain(value: Any) -> Any:
    """Convert a parsed value to the corpus JSON shape."""
    if isinstance(value, bool):
        return value
    if isinstance(value, Date):
        return {"__type": "date", "value": int(value)}
    if isinstance(value, Token):
        return {"__type": "token", "value": str(value)}
    if isinstance(value, DisplayString):
        return {"__type": "displaystring", "value": str(value)}
    if isinstance(value, bytes):
        return {"__type": "binary", "value": base64.b32encode(value).decode()}
    if isinstance(value, Decimal):
        return value
    if isinstance(value, list):
        return [[_plain(item), _params(params)] for item, params in value]
    return value


def _params(params: dict[str, Any]) -> list[list[Any]]:
    return [[key, _plain(value)] for key, value in params.items()]


def _expected(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_expected(item) for item in value]
    return value


def _run_item(text: str) -> Any:
    r = Reader(text)
    r.skip(" ")
    item, params = parse_item(r)
    r.skip(" ")
    if not r.done():
        raise StructuredError("trailing text")
    return [_plain(item), _params(params)]


@pytest.mark.parametrize("name", FILES)
def test_the_corpus_file_parses_as_expected(name: str) -> None:
    tests = json.loads(read_upstream(f"sf/{name}.json"))
    checked = 0
    for case in tests:
        if case["header_type"] == "list":
            continue
        text = ", ".join(case["raw"])
        must_fail = case.get("must_fail", False)
        try:
            if case["header_type"] == "dictionary":
                parsed = parse_dictionary(text)
                got: Any = [[key, [_plain(v), _params(p)]] for key, (v, p) in parsed.items()]
            else:
                got = _run_item(text)
        except StructuredError:
            assert must_fail or case.get("can_fail", False), case["name"]
        else:
            assert not must_fail, case["name"]
            assert got == _expected(case["expected"]), case["name"]
        checked += 1
    assert checked > 0


def test_dictionary_serialization_matches_canonical_forms() -> None:
    tests = json.loads(read_upstream("sf/dictionary.json"))
    checked = 0
    for case in tests:
        if case.get("must_fail") or "canonical" not in case or not case["canonical"]:
            continue
        parsed = parse_dictionary(", ".join(case["raw"]))
        simple = {k: v for k, (v, p) in parsed.items() if not p and not isinstance(v, list)}
        if len(simple) != len(parsed) or any(isinstance(v, bytes) for v in simple.values()):
            continue
        assert serialize_dictionary(simple) == case["canonical"][0], case["name"]
        checked += 1
    assert checked >= 3
