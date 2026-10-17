"""The command line contract: exit statuses, octets in, closed streams, no tracebacks."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ccdirectives import _cli, _cliio
from ccdirectives._cli import main

# The checkout's sources when present; an installed wheel is tested as it is otherwise.
_SRC_DIR = Path(__file__).resolve().parents[1] / "src"
SRC = str(_SRC_DIR) if _SRC_DIR.is_dir() else ""
CODE = f"import sys; sys.path[:0] = [p for p in [{SRC!r}] if p]; "
CODE += "from ccdirectives._cli import main; sys.exit(main())"


def _run(*args: str, stdin: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-c", CODE, *args], input=stdin, capture_output=True, check=False
    )


@pytest.mark.parametrize(
    ("args", "status"),
    [
        (["max-age=60"], 0),
        (["--strict", "max-age=60, no-store=1"], 1),
        (["--strict", "max-age=x"], 1),
        (["--age", "-1", "max-age=1"], 2),
        (["--age", "1_0", "max-age=1"], 2),
        (["--age", chr(0x661), "max-age=1"], 2),
        (["--nope"], 2),
    ],
)
def test_exit_statuses_in_a_real_process(args: list[str], status: int) -> None:
    result = _run(*args)
    assert result.returncode == status, result.stderr
    assert b"Traceback" not in result.stderr
    if status == 1:
        assert result.stderr.startswith(b"ccdirectives: ") and result.stdout == b""


def test_age_takes_delta_seconds_with_leading_zeros() -> None:
    result = _run("--age", "0070", "max-age=60")
    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert (report["age"], report["fresh"]) == (70, False)


def test_standard_input_is_read_as_octets_in_a_real_process() -> None:
    head = b'HTTP/1.1 200 OK\r\nCache-Control: x="caf\xc3\xa9", max-age=5\r\nAge: 9\r\n\r\n'
    result = _run(stdin=head)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["directives"] == {"x": "caf\xc3\xa9", "max-age": 5}
    assert (report["age"], report["fresh"]) == (9, False)
    assert result.stdout.isascii()


def test_an_interrupt_exits_130_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupted() -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(_cli, "read_input", interrupted)
    assert main([]) == 130
    assert capsys.readouterr().err == ""


class _Closed(io.StringIO):
    def __init__(self, error: OSError) -> None:
        super().__init__()
        self.error = error

    def write(self, text: str) -> int:
        raise self.error

    def flush(self) -> None:
        raise self.error


@pytest.mark.parametrize("error", [BrokenPipeError(32, "pipe"), OSError(22, "invalid")])
def test_a_closed_output_exits_1_quietly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: OSError
) -> None:
    monkeypatch.setattr(sys, "stdout", _Closed(error))
    assert main(["max-age=5"]) == 1
    assert capsys.readouterr().err == ""


def test_a_failing_output_exits_1_with_its_errno(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdout", _Closed(OSError(28, "no space")))
    assert main(["max-age=5"]) == 1
    assert capsys.readouterr().err == "ccdirectives: cannot write the output (errno 28)\n"


def test_closed_standard_streams(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", None)
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
    assert "standard input is closed" in capsys.readouterr().err
    monkeypatch.setattr(sys, "stdout", None)
    assert main(["max-age=5"]) == 1
    monkeypatch.setattr(sys, "stderr", None)
    assert main(["--strict", "max-age=x"]) == 1


def _posix(monkeypatch: pytest.MonkeyPatch, platform: str, *args: str) -> dict[str, Any]:
    out = io.StringIO()
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(sys, "argv", ["ccdirectives", *args])
    monkeypatch.setattr(sys, "stdout", out)
    assert main() == 0
    report: dict[str, Any] = json.loads(out.getvalue())
    return report


def test_posix_arguments_are_read_back_as_their_octets(monkeypatch: pytest.MonkeyPatch) -> None:
    # The file system codec turned the octets of "caf\xc3\xa9" into "caf\xe9"; recover them.
    report = _posix(monkeypatch, "linux", 'x="caf\xe9"')
    assert report["directives"] == {"x": "caf\xc3\xa9"}
    report = _posix(monkeypatch, "win32", 'x="caf\xe9"')
    assert report["directives"] == {"x": "caf\xe9"}


def test_arguments_passed_to_main_are_used_as_given(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert main(['x="caf\xe9"']) == 0
    assert json.loads(capsys.readouterr().out)["directives"] == {"x": "caf\xe9"}


def test_a_reader_that_closes_early_gets_exit_1_without_a_traceback(tmp_path: Path) -> None:
    source = tmp_path / "big.txt"
    source.write_bytes(b", ".join(b"x%d" % n for n in range(300_000)) + b"\n")
    with source.open("rb") as stdin:
        process = subprocess.Popen(
            [sys.executable, "-c", CODE],
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stdout is not None and process.stderr is not None
        assert process.stdout.readline().rstrip(b"\r\n") == b"{"
        process.stdout.close()
        error = process.stderr.read()
        assert process.wait(timeout=120) == 1
        process.stderr.close()
    assert error == b""


def test_other_errors_are_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken() -> str:
        raise PermissionError(13, "denied")

    monkeypatch.setattr(_cli, "read_input", broken)
    with pytest.raises(PermissionError):
        main([])
    assert _cliio.octets("a") == "a"
