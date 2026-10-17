# ccdirectives 1.0.0 certification report

Progress:
- [x] Branch `release/1.0.0` created from `main` (0.2.0, d76796f; PyPI has 0.2.0)
- [x] Baseline gates run on 0.2.0
- [ ] API review and 1.0.0 API changes (item 1)
- [ ] Real ground truth: fetched sources and live reference parsers (item 7)
- [ ] Errors, typing, docstrings and doctests (items 2 to 5)
- [ ] Contract, fuzz and author mutation round (items 6, 9, 18)
- [ ] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [ ] Packaging, e2e and upgrade from PyPI 0.2.0 (items 8, 10, 13, 14), author run
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)
- [ ] Gates (item 15), final run
- [ ] PR and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Baseline on 0.2.0 (before any change)

Clone of `main` (d76796f) on this PC, CPython 3.13.2, references fetched by
`scripts/fetch_upstream.py` (every file matched its manifest hash): `ruff format --check .`,
`ruff check .` and `mypy --strict src tests` exit 0; `pytest` 206 passed, 1 skipped (the
opt-in wheel test). PyPI has 0.2.0 only.
