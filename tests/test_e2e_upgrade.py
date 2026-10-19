"""Install ccdirectives 0.2.0 from PyPI, probe it, upgrade in place to this wheel, probe again.

Needs the network and the build backend, so it runs only with CCDIRECTIVES_E2E_PYPI=1.
Results on the probed inputs must be identical; the changes listed in the 1.0.0 section of
CHANGELOG.md are probed on their own and checked to differ exactly that way.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("CCDIRECTIVES_E2E_PYPI") != "1", reason="set CCDIRECTIVES_E2E_PYPI=1 to run"
)

PROBE = r"""
import json, math, os, random, subprocess, sys
import ccdirectives as c

def outcome(call, detail=True):
    try:
        result = call()
    except c.CacheControlError as error:
        return ["CacheControlError", error.reason if detail else None, error.offset]
    except (TypeError, ValueError, OverflowError, AttributeError) as error:
        return [type(error).__name__]
    return ["ok", repr(result)]

rng = random.Random(1)
alphabet = list('abm-x=,;" \t\\0123456789') + ["max-age", "private", "no-cache", "\xe9", "\r"]
values = ["".join(rng.choice(alphabet) for _ in range(rng.randrange(14))) for _ in range(1500)]
results = []
for value in values:
    for strict in (False, True):
        for context in (None, "request", "response"):
            results.append(outcome(lambda: c.parse(value, strict=strict, context=context)))
    lenient = c.parse(value)
    results.append(outcome(lambda: c.build(lenient), detail=False))
    results.append(outcome(lambda: c.parse_targeted(value)))
    results.append(outcome(lambda: c.build_targeted(lenient), detail=False))
    results.append(outcome(lambda: c.select({"CDN-Cache-Control": value, "Cache-Control": value})))
    for shared in (False, True):
        results.append(outcome(lambda: c.freshness_lifetime(lenient, shared=shared)))
        results.append(outcome(lambda: c.may_store(lenient, shared=shared, authorized=True)))
        for age in (0, 59, 60, 61, 10**6):
            request = c.parse(rng.choice(["", "max-stale", "min-fresh=5", "no-cache"]))
            judge = lambda: c.assess(lenient, age=age, shared=shared, request=request)
            results.append(outcome(judge))
for _ in range(500):
    t = [rng.choice([0, 1.5, 10**6, -3.25, 1_700_000_000]) for _ in range(4)]
    results.append(outcome(lambda: c.current_age(date_value=t[0], request_time=t[1],
                                                 response_time=t[2], now=t[3], age_value=7)))
    results.append(outcome(lambda: c.freshness_lifetime(c.CacheControl(), expires=t[0], date=t[1])))
HEAD = b"HTTP/1.1 200 OK\r\nCDN-Cache-Control: max-age=9\r\nAge: 3\r\n\r\n"
cli = []
for args, stdin in ((["max-age=5"], b""), (["--strict", "max-age=x"], b""),
                    (["--shared"], HEAD),
                    ([], b"no-store, x=1\n"), (["--age", "-1", "a"], b"")):
    run = subprocess.run([sys.executable, "-m", "ccdirectives", *args], input=stdin,
                         capture_output=True)
    cli.append([run.returncode, run.stdout.decode("latin-1").replace("\r\n", "\n")])
age = subprocess.run([sys.executable, "-m", "ccdirectives", "--age", "1_0", "a"],
                     capture_output=True)
huge = b"HTTP/1.1 200 OK\r\nExpires: Mon, 01 Jan 99999999999 00:00:00 GMT\r\n\r\n"
dated = subprocess.run([sys.executable, "-m", "ccdirectives"], input=huge, capture_output=True)
noisy = subprocess.run([sys.executable, "-m", "ccdirectives", "--x" + "a" * 5000],
                       capture_output=True)
gone, pipe = os.pipe()
os.close(gone)
helped = subprocess.run([sys.executable, "-m", "ccdirectives", "--help"], stdout=pipe,
                        stderr=subprocess.PIPE)
os.close(pipe)
class Loud(int):
    def __str__(self): return "1\r\nX: y"
changed = {
    "strict_string": outcome(lambda: c.parse("a", strict="no")),
    "shared_int": outcome(lambda: c.may_store(c.parse("private"), shared=1)),
    "get_int": outcome(lambda: c.CacheControl().get(1)),
    "nan": outcome(lambda: c.current_age(date_value=0, request_time=0, response_time=0,
                                         now=math.nan)),
    "inf": outcome(lambda: c.current_age(date_value=0, request_time=0, response_time=0,
                                         now=math.inf)),
    "build_dict": outcome(lambda: c.build({"a": True})),
    "loud": outcome(lambda: c.build(c.CacheControl({"max-age": Loud(1)}))),
    "huge": outcome(lambda: c.build(c.CacheControl({"x": 10**5000}))),
    "module": c.parse.__module__,
    "annotations": hasattr(c, "annotations"),
    "age_underscore": age.returncode,
    "empty_private": c.may_store(c.parse('private=""'), shared=True),
    "bad_s_maxage": outcome(lambda: c.parse_targeted("s-maxage=1.5")),
    "zero_is_false": c.CacheControl({"max-age": 0}) == c.CacheControl({"max-age": False}),
    "huge_date": [dated.returncode, b"Traceback" in dated.stderr],
    "usage_echo": [noisy.returncode, len(noisy.stderr) > 1000],
    "help_closed": [helped.returncode, helped.stderr != b""],
}
print(json.dumps({"version": c.__version__, "results": results, "cli": cli, "changed": changed}))
"""


def _run(*cmd: str | Path, cwd: Path | None = None) -> str:
    done = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def test_upgrade_from_pypi_0_2_0_keeps_every_result(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    (wheel,) = dist.glob("ccdirectives-1.0.0-*.whl")
    venv.create(tmp_path / "venv", with_pip=True)
    bindir = tmp_path / "venv" / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    work = tmp_path / "work"
    work.mkdir()
    _run(python, "-m", "pip", "install", "-q", "--no-cache-dir", "ccdirectives==0.2.0")
    old = json.loads(_run(python, "-I", "-c", PROBE, cwd=work))
    _run(python, "-m", "pip", "install", "-q", "--no-cache-dir", "--upgrade", wheel)
    new = json.loads(_run(python, "-I", "-c", PROBE, cwd=work))

    assert (old["version"], new["version"]) == ("0.2.0", "1.0.0")
    assert len(new["results"]) > 30_000
    assert new["results"] == old["results"]
    assert new["cli"] == old["cli"]
    # 0.2.0 fails on a closed output: Python 3.10 with a traceback (exit 1), later versions
    # with exit 120 and a flush warning, or exit 1 with no output on some Windows builds.
    status, _noise = old["changed"].pop("help_closed")
    assert status in (1, 120)
    assert old["changed"] == {
        "strict_string": ["ok", "CacheControl(directives={'a': True}, duplicates=frozenset())"],
        "shared_int": ["ok", "False"],
        "get_int": ["AttributeError"],
        "nan": ["ValueError"],
        "inf": ["OverflowError"],
        "build_dict": ["AttributeError"],
        "loud": ["ok", "'max-age=1\\r\\nX: y'"],
        "huge": ["ValueError"],
        "module": "ccdirectives._parse",
        "annotations": True,
        "age_underscore": 0,
        "empty_private": True,
        "bad_s_maxage": ["ok", "CacheControl(directives={}, duplicates=frozenset())"],
        "zero_is_false": True,
        "huge_date": [1, True],
        "usage_echo": [2, True],
    }
    assert new["changed"] == {
        "strict_string": ["TypeError"],
        "shared_int": ["TypeError"],
        "get_int": ["TypeError"],
        "nan": ["ValueError"],
        "inf": ["ValueError"],
        "build_dict": ["TypeError"],
        "loud": ["ok", "'max-age=1'"],
        "huge": ["CacheControlError", "'x' argument is too large to write", None],
        "module": "ccdirectives",
        "annotations": False,
        "age_underscore": 2,
        "empty_private": False,
        "bad_s_maxage": [
            "ok",
            "CacheControl(directives={'s-maxage': True}, duplicates=frozenset())",
        ],
        "zero_is_false": False,
        "huge_date": [0, False],
        "usage_echo": [2, False],
        "help_closed": [1, False],
    }
