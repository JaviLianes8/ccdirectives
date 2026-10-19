"""The public API is typed: mypy infers the documented types and rejects wrong ones."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

SNIPPET = """
from ccdirectives import CacheControl, assess, build, build_targeted, current_age, parse
from ccdirectives import REQUEST_DIRECTIVES, freshness_lifetime, may_store, parse_targeted, select
reveal_type(parse("max-age=1"))
reveal_type(build(CacheControl()))
reveal_type(parse_targeted("max-age=1"))
reveal_type(select({}, ["CDN-Cache-Control"]))
reveal_type(assess(CacheControl(), age=1))
reveal_type(assess(CacheControl(), age=1).lifetime)
reveal_type(freshness_lifetime(CacheControl()))
reveal_type(current_age(date_value=0, request_time=0, response_time=0, now=0))
reveal_type(CacheControl().max_age)
reveal_type(CacheControl().no_cache_fields)
reveal_type(REQUEST_DIRECTIVES)
parse("max-age=1", True)
parse(b"max-age=1")
parse("max-age=1", context="both")
CacheControl({"max-age": 1.5})
assess(CacheControl(), 1)
parse(["max-age=1", "public"], strict=True, context="request")
select([("Cache-Control", "no-store")])
CacheControl().extensions("both")
select([["CDN-Cache-Control", "max-age=1"]], ["CDN-Cache-Control"])
"""


@pytest.fixture(scope="module")
def mypy_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    folder = tmp_path_factory.mktemp("typing")
    target = folder / "snippet.py"
    target.write_text(SNIPPET, encoding="utf-8")
    config = folder / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(folder / "cache")
    args = ["--strict", "--config-file", str(config), "--cache-dir", cache, str(target)]
    # mypy must run in this interpreter: one from elsewhere on PATH cannot see the
    # installed package and would report every name as Any.
    api = pytest.importorskip("mypy.api")
    out, err, _ = api.run(args)
    return str(out) + str(err)


def test_functions_return_plain_types(mypy_output: str) -> None:
    revealed = [_revealed(mypy_output, line) for line in range(4, 15)]
    assert revealed == [
        "ccdirectives._model.CacheControl",
        "str",
        "ccdirectives._model.CacheControl | None",
        "tuple[str, ccdirectives._model.CacheControl]",
        "ccdirectives._fresh.Freshness",
        "int | None",
        "int | None",
        "int",
        "int | None",
        "tuple[str, ...]",
        "frozenset[str]",
    ]


def test_misuse_is_rejected(mypy_output: str) -> None:
    expected = (
        (15, "call-arg"),
        (16, "arg-type"),
        (17, "arg-type"),
        (18, "dict-item"),
        (19, "call-arg"),
        (22, "arg-type"),
    )
    for line, code in expected:
        assert re.search(rf"snippet\.py:{line}: error: .*\[{code}\]", mypy_output), mypy_output


def test_documented_calls_type_check(mypy_output: str) -> None:
    assert "snippet.py:20:" not in mypy_output, mypy_output
    assert "snippet.py:21:" not in mypy_output, mypy_output


def _revealed(output: str, line: int) -> str:
    match = re.search(rf"snippet\.py:{line}: note: Revealed type is \"(.+)\"", output)
    assert match, output
    # Older mypy releases spell builtins with their module prefix.
    return match.group(1).replace("builtins.", "")


def test_select_takes_lists_of_two_as_documented(mypy_output: str) -> None:
    assert "snippet.py:23:" not in mypy_output, mypy_output
