"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with CCDIRECTIVES_E2E=1.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("CCDIRECTIVES_E2E") != "1", reason="set CCDIRECTIVES_E2E=1 to build and install"
)

PROGRAM = r"""
import importlib.metadata, importlib.resources
import ccdirectives
from ccdirectives import (
    DELTA_MAX, REGISTERED_DIRECTIVES, CacheControl, CacheControlError, assess, build,
    build_targeted, current_age, freshness_lifetime, may_store, parse, parse_targeted, select,
)

assert "site-packages" in ccdirectives.__file__, ccdirectives.__file__
assert importlib.metadata.version("ccdirectives") == ccdirectives.__version__
assert importlib.resources.files("ccdirectives").joinpath("py.typed").is_file()

cc = parse(['max-age=600, no-cache="Set-Cookie"', "MAX-AGE=5, x-a"])
assert cc.max_age == 600 and cc.no_cache_fields == ("set-cookie",)
assert cc.duplicates == {"max-age"} and cc.extensions() == ("x-a",)
assert parse("max-age=99999999999").max_age == DELTA_MAX == 2147483648
assert parse(build(cc), strict=True) == CacheControl(cc.directives)
assert len(REGISTERED_DIRECTIVES) == 16
verdict = assess(parse("max-age=600, stale-while-revalidate=30"), age=620)
assert not verdict.fresh and verdict.stale_while_revalidate
assert freshness_lifetime(parse("s-maxage=9, max-age=1"), shared=True) == 9
assert current_age(date_value=0, request_time=0, response_time=1, now=5, age_value=10) == 15
assert not may_store(parse("private"), shared=True)
assert parse_targeted("max-age=1.5") == CacheControl() and parse_targeted("a,") is None
targeted = build_targeted(CacheControl({"private": "ETag", "max-age": 1}))
assert targeted == 'private="ETag", max-age=1'
field, policy = select({"CDN-Cache-Control": "max-age=600", "Cache-Control": "no-store"})
assert field == "CDN-Cache-Control" and policy.max_age == 600
for call in (
    lambda: parse("max-age=x", strict=True),
    lambda: build(CacheControl({"x": "a\r\nSet-Cookie: b"})),
    lambda: build_targeted(CacheControl({"X!": True})),
):
    try:
        call()
    except CacheControlError as error:
        assert isinstance(error, ValueError)
    else:
        raise AssertionError("expected CacheControlError")
print("e2e ok")
"""


def _run(
    *cmd: str | Path, cwd: Path | None = None, stdin: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, input=stdin, capture_output=True, check=False
    )


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("ccdirectives-*.whl")
    (sdist,) = dist.glob("ccdirectives-*.tar.gz")
    names = zipfile.ZipFile(wheel).namelist()
    assert "ccdirectives/py.typed" in names and "ccdirectives/__main__.py" in names
    assert not any(name.startswith(("tests/", "scripts/")) for name in names)
    entry_points = next(name for name in names if name.endswith("entry_points.txt"))
    text = zipfile.ZipFile(wheel).read(entry_points).decode()
    assert "ccdirectives = ccdirectives._cli:main" in text
    listing = _run(sys.executable, "-m", "tarfile", "-l", sdist).stdout.decode()
    assert "IMPROVEMENTS-round" not in listing and "CERT-1.0-REPORT" not in listing
    assert "GUIDE.md" in listing and "tests/fixtures/oracle_runs.json" in listing
    assert "tests/upstream/MANIFEST.json" in listing
    assert ".txt" not in listing.replace("requirements-dev.txt", "")
    assert ".csv" not in listing and "upstream/sf" not in listing
    assert "tests/test_sources.py" in listing and "scripts/fetch_upstream.py" in listing

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    installed = _run(python, "-m", "pip", "install", "-q", wheel)
    assert installed.returncode == 0, installed.stderr

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    result = _run(python, "-I", "-c", PROGRAM, cwd=work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.decode().strip() == "e2e ok"

    head = b"HTTP/2 200\r\ncache-control: max-age=60\r\nCDN-Cache-Control: max-age=600\r\n\r\n"
    script = bindir / ("ccdirectives.exe" if sys.platform == "win32" else "ccdirectives")
    for command in ([script], [python, "-m", "ccdirectives"]):
        shown = _run(*command, "--shared", cwd=work, stdin=head)
        assert shown.returncode == 0, shown.stderr
        report = json.loads(shown.stdout)
        assert report["field"] == "CDN-Cache-Control" and report["lifetime"] == 600
    failed = _run(script, "--strict", "max-age=x", cwd=work)
    assert failed.returncode == 1 and b"not delta-seconds" in failed.stderr
