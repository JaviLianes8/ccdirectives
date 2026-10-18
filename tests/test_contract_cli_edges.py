"""Command line edges: HTTP dates no date can hold, bounded usage errors, help output."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ccdirectives._cli import main
from ccdirectives._head import http_date

_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
SRC = str(_SRC_DIR) if _SRC_DIR.is_dir() else ""
CODE = f"import sys; sys.path[:0] = [p for p in [{SRC!r}] if p]; "
CODE += "from ccdirectives._cli import main; sys.exit(main())"
HUGE_YEAR = "Mon, 01 Jan 99999999999 00:00:00 GMT"
HUGE_OFFSET = "Mon, 01 Jan 2026 00:00:00 +99999999999999999999"


def _run(*args: str, stdin: bytes = b"", stdout: Any = subprocess.PIPE) -> Any:
    return subprocess.run(
        [sys.executable, "-c", CODE, *args],
        input=stdin,
        stdout=stdout,
        stderr=subprocess.PIPE,
        check=False,
    )


@pytest.mark.parametrize("value", [HUGE_YEAR, HUGE_OFFSET, "Mon, 01 Jan 10000 00:00:00 GMT"])
def test_an_http_date_no_date_can_hold_does_not_parse(value: str) -> None:
    assert http_date(value) is None


@pytest.mark.parametrize("field", ["Expires", "Date"])
@pytest.mark.parametrize("value", [HUGE_YEAR, HUGE_OFFSET])
def test_a_head_with_such_a_date_is_judged_without_a_traceback(field: str, value: str) -> None:
    other = "Date: Sun, 18 Oct 2026 00:00:00 GMT" if field == "Expires" else "Expires: x"
    head = f"HTTP/1.1 200 OK\r\nCache-Control: public\r\n{field}: {value}\r\n{other}\r\n\r\n"
    result = _run(stdin=head.encode())
    assert result.returncode == 0, result.stderr
    assert result.stderr == b""
    report = json.loads(result.stdout)
    # An Expires that does not parse means already expired (RFC 9111 section 5.3).
    assert (report["lifetime"], report["fresh"]) == (0, False)


def test_a_huge_unrecognized_argument_is_not_echoed_whole() -> None:
    result = _run("--x" + "a" * 20_000)
    assert result.returncode == 2
    lines = result.stderr.decode().splitlines()
    assert lines[-1].startswith("ccdirectives: error: unrecognized arguments: --xaaa")
    assert lines[-1].endswith("...") and len(lines[-1]) < 260
    assert lines[0].startswith("usage: ccdirectives")


def test_usage_errors_survive_a_closed_standard_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stderr", None)
    with pytest.raises(SystemExit) as caught:
        main(["--nope"])
    assert caught.value.code == 2


def test_help_goes_to_standard_output() -> None:
    result = _run("--help")
    assert result.returncode == 0 and result.stderr == b""
    text = result.stdout.decode().replace("\r\n", "\n")
    assert text.startswith("usage: ccdirectives") and "--target FIELD" in text
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_help_into_a_closed_pipe_exits_1_quietly() -> None:
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        result = _run("--help", stdout=write_end)
    finally:
        os.close(write_end)
    assert result.returncode == 1
    assert result.stderr == b""


class _Refusing(io.StringIO):
    def __init__(self, error: OSError) -> None:
        super().__init__()
        self.error = error

    def write(self, text: str) -> int:
        raise self.error


@pytest.mark.parametrize(
    ("stdout", "status", "message"),
    [
        (None, 1, ""),
        (_Refusing(BrokenPipeError(32, "pipe")), 1, ""),
        (
            _Refusing(OSError(28, "no space")),
            1,
            "ccdirectives: cannot write the output (errno 28)\n",
        ),
    ],
)
def test_help_follows_the_rules_of_the_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stdout: Any,
    status: int,
    message: str,
) -> None:
    monkeypatch.setattr(sys, "stdout", stdout)
    assert main(["--help"]) == status
    assert capsys.readouterr().err == message
