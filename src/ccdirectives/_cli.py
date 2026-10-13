"""Command line: show the cache policy in a header value or a response head as JSON."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass

from ._errors import CacheControlError
from ._fresh import assess
from ._head import age_of, field, head_fields, http_date
from ._model import CacheControl
from ._parse import parse
from ._targeted import select

EXIT_INVALID = 1


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
        values = [v for n, v in fields if n.lower() == "cache-control"]
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="ccdirectives",
        description="Show the cache policy of a Cache-Control value, or of a response head "
        "read from standard input (for example the output of curl -sI). Exit status 1 "
        "means an invalid value in --strict mode, 2 a usage error.",
    )
    parser.add_argument("value", nargs="?", help="a Cache-Control field value")
    parser.add_argument("--strict", action="store_true", help="reject values outside the RFC")
    parser.add_argument("--shared", action="store_true", help="judge as a shared cache (a CDN)")
    parser.add_argument("--age", type=int, help="age in seconds (default: the Age field, or 0)")
    parser.add_argument(
        "--target",
        action="append",
        help="targeted field to prefer, in order (default CDN-Cache-Control with --shared)",
    )
    args = parser.parse_args(argv)
    if args.age is not None and args.age < 0:
        parser.error("--age cannot be negative")
    clock = _Clock(args.age or 0, args.shared)
    try:
        if args.value is not None:
            value = args.value
            if value.lower().startswith("cache-control:"):
                value = value.partition(":")[2]
            name, policy = "Cache-Control", parse(value.strip(), strict=args.strict)
        else:
            # ISO-8859-1 maps every octet, so no input byte can stop the program.
            text = sys.stdin.buffer.read().decode("iso-8859-1")
            fields = head_fields(text)
            if fields is None:
                name, policy = "Cache-Control", parse(text.strip(), strict=args.strict)
            else:
                name, policy = _from_head(fields, args, clock)
    except CacheControlError as error:
        print(f"ccdirectives: {error}", file=sys.stderr)
        return EXIT_INVALID
    print(json.dumps(_report(name, policy, clock), indent=2))
    return 0
