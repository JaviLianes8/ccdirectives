# Contributing

Thanks for taking the time. This project keeps a small, predictable shape.

## Setup

```
pip install -r requirements-dev.txt
```

## Before you open a pull request

- Keep public API in `src/ccdirectives/__init__.py`; internals live in `_`-prefixed modules.
- Add a test for the behaviour you change. Tests work in pytest's temporary folders and
  never depend on the clock or the network, except the linear-time checks, which compare
  timings, and the two opt-in end-to-end tests below, which use the network.
- Run `python scripts/fetch_upstream.py` once: it downloads the RFCs, the IANA registry,
  the structured field test corpus, the Fetch Standard and the Werkzeug and hishel test
  files listed in `tests/upstream/MANIFEST.json`, which are not committed. Their tests
  skip without them. The dev extras install the pinned Werkzeug, hishel and CacheControl
  that `tests/test_oracle.py` compares with live.
- Run `scripts/check.ps1` (format, lint, types, tests) and make sure it passes. Set
  `CCDIRECTIVES_E2E=1` to also build the wheel and drive the installed package and its
  command, and `CCDIRECTIVES_E2E_PYPI=1` to upgrade the PyPI release in place to it.
- One logical change per commit, imperative subject line.

Open an issue first if the change is large or shifts the public API.
