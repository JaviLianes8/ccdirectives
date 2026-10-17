"""Record what established Cache-Control parsers answer for seeded, well-formed headers.

Runs Werkzeug (`parse_dict_header`, the reader behind `parse_cache_control_header`),
hishel (`parse_cache_control`, `get_freshness_lifetime`, `allowed_stale`) and CacheControl
(`CacheController.parse_cache_control`) on the same seeded headers and writes their answers
to tests/fixtures/oracle_runs.json, which tests/test_oracle.py compares with ccdirectives.
That file is program output of those tools, not a copy of them.

    pip install werkzeug==3.1.9 hishel==1.4.0 CacheControl==0.14.4
    python scripts/oracle_fixture.py
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import platform
import random
import sys
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "oracle_runs.json"
SEED = 9111
COUNT = 1000
VERSIONS = {"werkzeug": "3.1.9", "hishel": "1.4.0", "CacheControl": "0.14.4"}
FLAGS = [
    "no-store",
    "no-transform",
    "only-if-cached",
    "must-revalidate",
    "must-understand",
    "public",
    "proxy-revalidate",
    "immutable",
]
DELTAS = ["max-age", "s-maxage", "min-fresh", "stale-while-revalidate", "stale-if-error"]
FIELDS = ["no-cache", "private"]
NAMES = ["set-cookie", "authorization", "x-trace", "etag", "vary"]
TOKEN_TEXT = "abcxyz019-._~!#$%&'+^`|"
QUOTED_TEXT = 'abc xyz,;=/"\\()'


def _token(rng: random.Random) -> str:
    return "".join(rng.choice(TOKEN_TEXT) for _ in range(rng.randint(1, 6)))


def _quoted(rng: random.Random, text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _directive(rng: random.Random, name: str) -> str:
    if name in DELTAS or (name == "max-stale" and rng.random() < 0.7):
        return f"{name}={rng.choice([0, 1, 59, 600, 86400, rng.randrange(2**31 - 1)])}"
    if name in FIELDS and rng.random() < 0.5:
        listed = ", ".join(rng.sample(NAMES, rng.randint(1, 3)))
        return f"{name}={_quoted(rng, listed)}"
    if name.startswith("x-") and rng.random() < 0.7:
        if rng.random() < 0.5:
            return f"{name}={_token(rng)}"
        text = "".join(rng.choice(QUOTED_TEXT) for _ in range(rng.randint(0, 8)))
        return f"{name}={_quoted(rng, text)}"
    return name


def cases() -> list[str]:
    """Well-formed headers: no repeated names, delta-seconds below 2^31 - 1."""
    rng = random.Random(SEED)
    pool = [*FLAGS, *DELTAS, *FIELDS, "max-stale", "x-a", "x-b", "x-ext"]
    out: list[str] = []
    for _ in range(COUNT):
        names = rng.sample(pool, rng.randint(1, 6))
        separator = rng.choice([", ", ",", " , ", ",\t"])
        out.append(separator.join(_directive(rng, name) for name in names))
    return out


def _hishel(value: str) -> dict[str, Any]:
    headers = importlib.import_module("hishel._core._headers")
    cc = headers.parse_cache_control(value)
    fields = [
        "max_age", "s_maxage", "max_stale", "min_fresh", "stale_if_error",
        "stale_while_revalidate", "no_store", "no_transform", "only_if_cached",
        "must_revalidate", "must_understand", "public", "proxy_revalidate", "immutable",
        "no_cache", "private", "extensions",
    ]  # fmt: skip
    found = {name: getattr(cc, name) for name in fields}
    # Defaults are left out to keep the file small; 0 is kept (it equals False).
    return {k: v for k, v in found.items() if v is not None and v is not False and v != []}


def _hishel_freshness(value: str) -> list[Any]:
    spec = importlib.import_module("hishel._core._spec")
    models = importlib.import_module("hishel._core.models")
    response = models.Response(200, headers=models.Headers({"cache-control": value}))
    return [
        spec.get_freshness_lifetime(response, is_cache_shared=False),
        spec.get_freshness_lifetime(response, is_cache_shared=True),
        spec.allowed_stale(response, allow_stale_option=True),
    ]


def oracles(values: list[str]) -> dict[str, list[Any]]:
    """Run the three reference libraries; needs them installed at VERSIONS."""
    http = importlib.import_module("werkzeug.http")
    controller = importlib.import_module("cachecontrol.controller").CacheController()
    return {
        "werkzeug": [http.parse_dict_header(v) for v in values],
        "hishel": [_hishel(v) for v in values],
        "hishel_freshness": [_hishel_freshness(v) for v in values],
        "cachecontrol": [controller.parse_cache_control({"cache-control": v}) for v in values],
    }


def installed() -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in VERSIONS:
        try:
            found[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            found[name] = None
    return found


def main() -> int:
    if installed() != VERSIONS:
        print(f"install {VERSIONS} first; found {installed()}")
        return 1
    values = cases()
    record = {
        "seed": SEED,
        "python": platform.python_version(),
        "versions": VERSIONS,
        "cases": values,
        **oracles(values),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(record, indent=0, sort_keys=True) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {len(values)} cases to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
