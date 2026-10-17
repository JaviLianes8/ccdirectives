"""ccdirectives against Werkzeug, hishel and CacheControl on the same seeded headers.

tests/fixtures/oracle_runs.json holds what those libraries answered, recorded by
scripts/oracle_fixture.py; the comparison is rerun live when the pinned versions are
installed. Every difference is one GUIDE.md lists: hishel reads a bare max-stale as
2^31 - 1 and title-cases field names, CacheControl reads a bare max-stale as None.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from ccdirectives import DELTA_MAX, CacheControl, assess, freshness_lifetime, parse

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "oracle_runs.json").read_text("utf-8"))
NUMBERS = ["max_age", "s_maxage", "min_fresh", "stale_if_error", "stale_while_revalidate"]
FLAGS = [
    "no_store",
    "no_transform",
    "only_if_cached",
    "must_revalidate",
    "must_understand",
    "public",
    "proxy_revalidate",
    "immutable",
]
CACHECONTROL_KNOWN = {
    "max-age": True,
    "max-stale": True,
    "min-fresh": True,
    "s-maxage": True,
    "no-cache": False,
    "no-store": False,
    "no-transform": False,
    "only-if-cached": False,
    "must-revalidate": False,
    "public": False,
    "private": False,
    "proxy-revalidate": False,
}


def as_werkzeug(cc: CacheControl) -> dict[str, str | None]:
    return {name: None if value is True else str(value) for name, value in cc.items()}


def _listed(cc: CacheControl, name: str) -> Any:
    if not cc.has(name):
        return False
    fields = cc.no_cache_fields if name == "no-cache" else cc.private_fields
    return list(fields) if isinstance(cc[name], str) else True


def as_hishel(cc: CacheControl) -> dict[str, Any]:
    found: dict[str, Any] = {name: getattr(cc, name) for name in [*NUMBERS, *FLAGS]}
    stale = cc.max_stale
    found["max_stale"] = 2**31 - 1 if stale == DELTA_MAX else stale
    found["no_cache"] = _listed(cc, "no-cache")
    found["private"] = _listed(cc, "private")
    found["extensions"] = [n if cc[n] is True else f"{n}={cc[n]}" for n in cc.extensions()]
    return {k: v for k, v in found.items() if v is not None and v is not False and v != []}


def hishel_fields(recorded: dict[str, Any]) -> dict[str, Any]:
    out = dict(recorded)
    for name in ("no_cache", "private"):
        if isinstance(out.get(name), list):
            out[name] = [field.lower() for field in out[name]]
    return out


def as_hishel_freshness(cc: CacheControl) -> list[Any]:
    lifetime = freshness_lifetime(cc) or 0
    stale = assess(cc, age=lifetime + 1, request=parse("max-stale")).reusable
    return [freshness_lifetime(cc), freshness_lifetime(cc, shared=True), stale]


def as_cachecontrol(cc: CacheControl) -> dict[str, int | None]:
    out: dict[str, int | None] = {}
    for name, numeric in CACHECONTROL_KNOWN.items():
        if name in cc:
            seconds = cc.seconds(name) if numeric else None
            out[name] = None if name == "max-stale" and cc[name] is True else seconds
    return out


def _compare(results: dict[str, list[Any]]) -> None:
    for index, value in enumerate(FIXTURE["cases"]):
        cc = parse(value, strict=True)
        assert as_werkzeug(cc) == results["werkzeug"][index], value
        assert as_hishel(cc) == hishel_fields(results["hishel"][index]), value
        assert as_hishel_freshness(cc) == results["hishel_freshness"][index], value
        assert as_cachecontrol(cc) == results["cachecontrol"][index], value


def _script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "oracle_fixture", ROOT / "scripts" / "oracle_fixture.py"
    )
    if spec is None or spec.loader is None or not spec.origin or not Path(spec.origin).is_file():
        pytest.skip("scripts/oracle_fixture.py is not in this tree")
    module = importlib.util.module_from_spec(spec)
    sys.modules["oracle_fixture"] = module
    spec.loader.exec_module(module)
    return module


def test_the_fixture_holds_the_seeded_cases() -> None:
    script = _script()
    assert FIXTURE["cases"] == script.cases()
    assert FIXTURE["versions"] == script.VERSIONS
    assert len(FIXTURE["cases"]) == 1000


def test_recorded_answers_match_with_the_documented_differences() -> None:
    _compare(FIXTURE)


def test_the_reference_libraries_answer_the_same_when_rerun_live() -> None:
    script = _script()
    if script.installed() != script.VERSIONS:
        pytest.skip(f"install {script.VERSIONS} to rerun the reference libraries")
    live = script.oracles(FIXTURE["cases"])
    live["hishel"] = [dict(entry) for entry in live["hishel"]]
    assert json.loads(json.dumps(live)) == {key: FIXTURE[key] for key in live}
    _compare(live)
