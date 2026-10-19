"""Examples read from third-party sources fetched into tests/upstream (see MANIFEST.json).

hishel 1.4.0's own parser tests, Werkzeug 3.1.9's Cache-Control test and the Cache-Control
values the WHATWG Fetch Standard sends for its cache modes. The files are only read: each
example is taken from the fetched text, and the expected values are those the source
asserts, mapped onto this library's types. The tests skip while a file is absent.
"""

from __future__ import annotations

import ast
import re
from typing import Any

import pytest
from conftest import read_upstream

from ccdirectives import DELTA_MAX, CacheControl, parse

# Where this library answers differently, on purpose; each is listed in GUIDE.md.
# hishel caps at 2^31 - 1, RFC 9111 section 1.2.2 says 2^31.
HISHEL_CAP = 2147483647
# hishel keeps the last of a repeated directive; RFC 9111 section 4.2.1 uses the first.
LAST_WINS = {"max-age=100, max-age=200": ("max_age", 200, 100)}


def _calls() -> list[tuple[str, list[ast.Assert]]]:
    tree = ast.parse(read_upstream("hishel-test_headers.py.txt"))
    found: list[tuple[str, list[ast.Assert]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        header: str | None = None
        asserts: list[ast.Assert] = []
        for statement in node.body:
            if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call):
                call = statement.value
                if getattr(call.func, "id", "") == "parse_cache_control" and call.args:
                    argument = call.args[0]
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        header = argument.value
            elif isinstance(statement, ast.Assert) and header is not None:
                asserts.append(statement)
        if header is not None:
            found.append((header, asserts))
    return found


def _field_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.attr if node.value.id == "cc" else None
    return None


def _check(header: str, test: ast.expr, cc: CacheControl) -> bool:
    """Check one hishel assertion on our result; False when its form is not mapped."""
    if isinstance(test, ast.Compare) and len(test.ops) == 1:
        left, op, right = test.left, test.ops[0], test.comparators[0]
        attr = _field_name(left)
        if attr is not None and isinstance(right, (ast.Constant, ast.List)):
            expected: Any = ast.literal_eval(right)
            ours = getattr(cc, attr) if attr != "extensions" else list(cc.extensions())
            if header in LAST_WINS and LAST_WINS[header][:2] == (attr, expected):
                expected = LAST_WINS[header][2]
            if expected == HISHEL_CAP:
                expected = DELTA_MAX
            if isinstance(op, ast.Is) and expected is True and attr in ("no_cache", "private"):
                assert ours is True and not getattr(cc, f"{attr}_fields"), header
            else:
                assert ours == expected, (header, attr)
            return True
        if (
            isinstance(op, ast.In)
            and isinstance(left, ast.Constant)
            and isinstance(left.value, str)
        ):
            item, where = str(left.value), _field_name(right)
            if where in ("no_cache", "private"):
                assert item.lower() in getattr(cc, f"{where}_fields"), header
                return True
            if where == "extensions":
                name, _, value = item.partition("=")
                assert name in cc.extensions(), header
                assert cc[name] == (value or True), header
                return True
    if isinstance(test, ast.Call) and getattr(test.func, "id", "") == "isinstance":
        attr = _field_name(test.args[0])
        if attr in ("no_cache", "private"):
            assert getattr(cc, attr) and getattr(cc, f"{attr}_fields"), header
        return attr in ("no_cache", "private") or getattr(test.args[1], "id", "") == "CacheControl"
    return False


def test_hishel_parser_tests_hold_with_the_documented_differences() -> None:
    calls = _calls()
    unmapped: list[str] = []
    checked = 0
    for header, asserts in calls:
        cc = parse(header)
        for statement in asserts:
            if _check(header, statement.test, cc):
                checked += 1
            else:
                unmapped.append(ast.unparse(statement.test))
    assert len(calls) > 80 and checked > 150
    # Only the generator form over extensions is left to the explicit check below.
    assert unmapped == ["any(('value with \"quotes\"' in ext for ext in cc.extensions))"]
    assert parse('custom="value with \\"quotes\\""')["custom"] == 'value with "quotes"'


def test_werkzeug_cache_control_test_holds() -> None:
    source = read_upstream("werkzeug-test_http.py.txt")
    body = source.split("def test_cache_control_header(self):", 1)[1].split("def test_", 1)[0]
    headers = re.findall(r"parse_cache_control_header\(\s*(\"[^\"]*\"|'[^']*')", body)
    first, second = (ast.literal_eval(header) for header in headers)
    assert (first, second) == ("max-age=0, no-cache", 'private, community="UCI"')
    assert "assert cc.max_age == 0" in body and "assert cc.no_cache is True" in body
    cc = parse(first, strict=True, context="request")
    assert (cc.max_age, cc.no_cache, cc.no_cache_fields) == (0, True, ())
    assert 'assert cc["community"] == "UCI"' in body
    cc = parse(second, strict=True, context="response")
    assert (cc.private, cc["community"], cc.extensions("response")) == (True, "UCI", ("community",))


@pytest.mark.parametrize("value", ["max-age=0", "no-cache"])
def test_the_values_fetch_appends_for_its_cache_modes(value: str) -> None:
    source = read_upstream("whatwg-fetch.bs.txt")
    appended = re.findall(r"\(`<code>Cache-Control</code>`, `<code>([^<]+)</code>`\)", source)
    assert value in appended
    cc = parse(value, strict=True, context="request")
    assert cc.extensions("request") == ()
    assert (cc.max_age, cc.no_cache) == ((0, False) if value == "max-age=0" else (None, True))
