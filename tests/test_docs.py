"""The README examples run and print what their comments say; docs and versions agree."""

from __future__ import annotations

import contextlib
import io
import itertools
import re
from pathlib import Path

import ccdirectives

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _python_blocks() -> list[str]:
    return re.findall(r"```python\n(.*?)```", README, flags=re.DOTALL)


def _expected_output(block: str) -> list[str]:
    """Each print line is followed by the comment lines that hold what it prints."""
    expected: list[str] = []
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if not line.strip().startswith("print("):
            continue
        for following in itertools.takewhile(
            lambda text: text.strip().startswith("# "), lines[index + 1 :]
        ):
            expected.append(following.strip()[2:])
    return expected


def test_every_readme_example_runs_and_prints_its_comment() -> None:
    checked = 0
    for block in _python_blocks():
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exec(compile(block, "README.md", "exec"), {"__name__": "readme"})
        expected = _expected_output(block)
        assert expected, block
        assert out.getvalue().splitlines() == expected
        checked += len(expected)
    assert len(_python_blocks()) == 6
    assert checked == 11


def test_every_print_in_the_readme_shows_its_output() -> None:
    for block in _python_blocks():
        lines = block.splitlines()
        for index, line in enumerate(lines):
            if line.strip().startswith("print("):
                assert lines[index + 1].strip().startswith("# "), line


def test_the_api_table_lists_every_public_name() -> None:
    table = README.split("## API", 1)[1].split("\n## ", 1)[0]
    for name in ccdirectives.__all__:
        assert f"`{name}" in table, name


def test_version_matches_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == ccdirectives.__version__


def test_changelog_has_an_entry_for_this_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{ccdirectives.__version__}]" in text


def test_no_em_dash_anywhere_in_the_tree() -> None:
    suffixes = {".py", ".md", ".toml", ".ps1", ".txt", ".yml"}
    for path in ROOT.rglob("*"):
        parts = path.relative_to(ROOT).parts
        if not path.is_file() or path.suffix not in suffixes or parts[:2] == ("tests", "upstream"):
            continue
        if any(
            (part.startswith(".") and part != ".github") or part == "__pycache__" for part in parts
        ):
            continue
        assert chr(0x2014) not in path.read_text(encoding="utf-8"), path


def test_source_files_stay_under_two_hundred_lines() -> None:
    for path in [*ROOT.joinpath("src").rglob("*.py"), *ROOT.joinpath("tests").rglob("*.py")]:
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 200, path


def test_every_strict_reason_in_the_guide_is_one_the_code_raises() -> None:
    guide = (ROOT / "GUIDE.md").read_text(encoding="utf-8")
    table = guide.split("| Reason | When |", 1)[1].split("\n\n", 1)[0]
    reasons = re.findall(r"^\| `([^`]+)`(?:, `([^`]+)`)? \|", table, flags=re.MULTILINE)
    source = "".join(p.read_text(encoding="utf-8") for p in ROOT.joinpath("src").rglob("*.py"))
    found = [r for pair in reasons for r in pair if r]
    assert len(found) == 14
    for reason in found:
        text = reason.replace("'NAME'", "{shown(name)}")
        assert f'"{text}"' in source or f'f"{text}"' in source, reason


def test_readme_and_guide_links_are_absolute() -> None:
    for name in ("README.md", "GUIDE.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            assert target.startswith("https://"), (name, target)
