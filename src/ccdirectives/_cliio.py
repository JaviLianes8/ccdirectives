"""Standard streams for the command line: octets in, text out, and closed streams handled."""

from __future__ import annotations

import argparse
import contextlib
import errno
import os
import sys
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

# Usage errors are cut here: argparse repeats an unrecognized argument whole.
USAGE_LIMIT = 200


class OutputClosed(Exception):
    """The reader of standard output went away."""


class OutputFailed(Exception):
    """Standard output refused the data for another reason (a full disk, say)."""


def read_input() -> str | None:
    """Standard input as ISO-8859-1 text, or None when the process has no standard input.

    ISO-8859-1 maps every octet, so no input byte can stop the program and a field value
    keeps its octets.
    """
    if sys.stdin is None:
        return None
    buffer = getattr(sys.stdin, "buffer", None)
    return buffer.read().decode("iso-8859-1") if buffer is not None else sys.stdin.read()


def octets(arg: str) -> str:
    """An argument as the ISO-8859-1 reading of its octets, like standard input.

    POSIX passes arguments as bytes decoded with the file system codec; Windows passes text,
    which is used as it is.
    """
    if sys.platform == "win32":
        return arg
    return os.fsencode(arg).decode("iso-8859-1")


def report(message: str) -> None:
    """Print a message on standard error, or drop it when standard error is closed.

    A message is never moved to standard output, where it would mix with the data.
    """
    to_stderr(f"ccdirectives: {message}\n")


def to_stderr(text: str) -> None:
    """Write ``text`` to standard error and flush it; nothing happens when it is closed."""
    if sys.stderr is not None:
        with contextlib.suppress(OSError, ValueError):
            sys.stderr.write(text)
            sys.stderr.flush()


def write(text: str) -> None:
    """Write ``text`` and a newline to standard output, raising OutputClosed or OutputFailed."""
    if sys.stdout is None:
        raise OutputClosed
    try:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    except OSError as error:
        # A closed pipe is EPIPE on POSIX and EINVAL on Windows.
        if isinstance(error, BrokenPipeError) or error.errno == errno.EINVAL:
            raise OutputClosed from error
        raise OutputFailed(error.errno) from error
    except ValueError as error:
        # A stream object closed in this process (sys.stdout.close()) or detached.
        raise OutputClosed from error


def silence_stdout() -> None:
    """Point standard output at the null device so the flush at exit cannot fail again."""
    with contextlib.suppress(OSError, ValueError, AttributeError):
        target = sys.stdout.fileno()
        null = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null, target)
        finally:
            os.close(null)


class Parser(argparse.ArgumentParser):
    """argparse with bounded usage errors, and help that follows the rules of the output.

    Help goes through ``write``, so a closed or failing standard output ends the program
    like the report does; usage errors never echo more than ``USAGE_LIMIT`` characters.
    """

    def print_help(self, file: SupportsWrite[str] | None = None) -> None:
        write(self.format_help().removesuffix("\n"))

    def error(self, message: str) -> NoReturn:
        if len(message) > USAGE_LIMIT:
            message = message[:USAGE_LIMIT] + "..."
        to_stderr(f"{self.format_usage()}{self.prog}: error: {message}\n")
        raise SystemExit(2)
