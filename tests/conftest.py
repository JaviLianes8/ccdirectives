from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

UPSTREAM = Path(__file__).resolve().parent / "upstream"


def read_upstream(name: str) -> str:
    """Return a third-party reference file as text.

    The files are not committed: `python scripts/fetch_upstream.py` fetches them. Their
    tests skip while a file is absent and fail if it differs from the manifest.
    """
    path = UPSTREAM / name
    if not path.is_file():
        pytest.skip(f"{name} is not fetched; run python scripts/fetch_upstream.py")
    entry = json.loads((UPSTREAM / "MANIFEST.json").read_text(encoding="utf-8"))[name]
    body = path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == entry["sha256"], f"{name} differs from MANIFEST"
    return body.decode("utf-8")


@pytest.fixture(scope="session")
def rfc9111() -> str:
    """RFC 9111, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc9111.txt")


@pytest.fixture(scope="session")
def rfc9110() -> str:
    """RFC 9110, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc9110.txt")


@pytest.fixture(scope="session")
def rfc5861() -> str:
    """RFC 5861, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc5861.txt")


@pytest.fixture(scope="session")
def rfc8246() -> str:
    """RFC 8246, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc8246.txt")


@pytest.fixture(scope="session")
def rfc9213() -> str:
    """RFC 9213, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc9213.txt")


@pytest.fixture(scope="session")
def iana_csv() -> str:
    """The IANA cache directive registry, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("cache-directives.csv")
