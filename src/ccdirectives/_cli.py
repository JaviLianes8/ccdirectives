"""Command line: show the cache policy in a header value or a response head as JSON."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Sequence
from dataclasses import dataclass

from ._chars import ascii_lower, delta_seconds
from ._cliio import (
    OutputClosed,
    OutputFailed,
    Parser,
    octets,
    read_input,
    report,
    silence_stdout,
    write,
)
from ._dates import http_date
from ._errors import CacheControlError
from ._fresh import assess
from ._head import age_of, field, head_fields
from ._model import CacheControl
from ._parse import parse
from ._targeted import select

EXIT_INVALID = 1
EXIT_INTERRUPTED = 130
_SPACE = " \t\r\n"


@dataclass
class _Clock:
    age: int
    shared: bool
    expires: float | None = None
    date: float | None = None


def _report(name: str, policy: CacheControl, clock: _Clock) -> dict[str, object]:
    verdict = assess(
        policy, age=clock.age, shared=clock.shared, expires=clock.expires, date=clock.date
    )
    return {
        "field": name,
        "directives": policy.directives,
        "duplicates": sorted(policy.duplicates),
        "extensions": list(policy.extensions()),
        "lifetime": verdict.lifetime,
        "age": verdict.age,
        "fresh": verdict.fresh,
        "reusable": verdict.reusable,
        "stale_while_revalidate": verdict.stale_while_revalidate,
        "stale_if_error": verdict.stale_if_error,
    }


def _from_head(
    fields: list[tuple[str, str]], args: argparse.Namespace, clock: _Clock
) -> tuple[str, CacheControl]:
    targets = args.target or (["CDN-Cache-Control"] if args.shared else [])
    name, policy = select(fields, targets)
    if args.strict and name == "Cache-Control":
        values = [v for n, v in fields if ascii_lower(n) == "cache-control"]
        policy = parse(values, strict=True, context="response")
    if args.age is None:
        clock.age = age_of(fields)
    expires = field(fields, "Expires")
    if name == "Cache-Control" and expires is not None:
        # RFC 9111 section 5.3: an Expires that does not parse means already expired.
        date = http_date(field(fields, "Date"))
        received = date if date is not None else time.time()
        stamp = http_date(expires)
        clock.expires = stamp if stamp is not None else received - 1
        clock.date = received
    return name, policy


def _age(text: str) -> int:
    # delta-seconds, like the Age field: ASCII digits only, so "1_0" or "-0" are refused.
    seconds = delta_seconds(text)
    if seconds is None:
        raise argparse.ArgumentTypeError("must be a whole number of seconds (ASCII digits)")
    return seconds


def _parser() -> Parser:
    parser = Parser(
        prog="ccdirectives",
        description="Show the cache policy of a Cache-Control value, or of a response head "
        "read from standard input (for example the output of curl -sI). Exit status 1 "
        "means an invalid value in --strict mode or an output that closed early, 2 a usage "
        "error, 130 an interrupt.",
    )
    parser.add_argument("value", nargs="?", metavar="VALUE", help="a Cache-Control field value")
    parser.add_argument("--strict", action="store_true", help="reject values outside the RFC")
    parser.add_argument("--shared", action="store_true", help="judge as a shared cache (a CDN)")
    parser.add_argument(
        "--age", type=_age, metavar="SECONDS", help="age in seconds (default: the Age field, or 0)"
    )
    parser.add_argument(
        "--target",
        action="append",
        metavar="FIELD",
        help="targeted field to prefer, in order (default CDN-Cache-Control with --shared)",
    )
    return parser


def _policy(args: argparse.Namespace, clock: _Clock) -> tuple[str, CacheControl] | None:
    if args.value is not None:
        value = args.value
        if ascii_lower(value).startswith("cache-control:"):
            value = value.partition(":")[2]
        return "Cache-Control", parse(value.strip(_SPACE), strict=args.strict)
    text = read_input()
    if text is None:
        return None
    fields = head_fields(text)
    if fields is None:
        return "Cache-Control", parse(text.strip(_SPACE), strict=args.strict)
    return _from_head(fields, args, clock)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the process exit status.

    0 when the policy was printed, 1 when ``--strict`` rejects the value or the output
    closes early, 2 for a usage error and 130 when interrupted.
    """
    parser = _parser()
    try:
        # Inside the handlers: --help writes to standard output like the report does.
        args = parser.parse_args(argv)
        if argv is None:
            if args.value is not None:
                args.value = octets(args.value)
            args.target = [octets(target) for target in args.target or []]
        clock = _Clock(args.age or 0, args.shared)
        chosen = _policy(args, clock)
        if chosen is None:
            parser.error("no VALUE given and standard input is closed")
        write(json.dumps(_report(*chosen, clock), indent=2))
    except CacheControlError as error:
        report(str(error))
        return EXIT_INVALID
    except OutputClosed:
        silence_stdout()
        return EXIT_INVALID
    except OutputFailed as error:
        report(f"cannot write the output (errno {error.args[0]})")
        silence_stdout()
        return EXIT_INVALID
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    return 0
