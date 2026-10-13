"""Command line: show the cache policy in a header value or a response head as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from ._errors import CacheControlError
from ._fresh import assess
from ._model import CacheControl
from ._parse import parse
from ._targeted import select


def _head_fields(text: str) -> list[tuple[str, str]] | None:
    """The fields of the last response head in a ``curl -sI`` dump, or None if not a head."""
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("HTTP/")]
    if not starts:
        return None
    fields: list[tuple[str, str]] = []
    for line in lines[starts[-1] + 1 :]:
        line = line.rstrip("\r")
        if not line:
            break
        name, colon, value = line.partition(":")
        if colon and name and name == name.strip():
            fields.append((name, value.strip(" \t")))
    return fields


def _report(field: str, policy: CacheControl, args: argparse.Namespace) -> dict[str, object]:
    verdict = assess(policy, age=args.age, shared=args.shared)
    return {
        "field": field,
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


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="ccdirectives",
        description="Show the cache policy of a Cache-Control value, or of a response head "
        "read from standard input (for example the output of curl -sI).",
    )
    parser.add_argument("value", nargs="?", help="a Cache-Control field value")
    parser.add_argument("--strict", action="store_true", help="reject values outside the RFC")
    parser.add_argument("--shared", action="store_true", help="judge as a shared cache (a CDN)")
    parser.add_argument("--age", type=int, default=0, help="age of the stored response, seconds")
    parser.add_argument(
        "--target",
        action="append",
        help="targeted field to prefer, in order (default CDN-Cache-Control with --shared)",
    )
    args = parser.parse_args(argv)
    if args.age < 0:
        parser.error("--age cannot be negative")
    try:
        if args.value is not None:
            field, policy = "Cache-Control", parse(args.value, strict=args.strict)
        else:
            # ISO-8859-1 maps every octet, so no input byte can stop the program.
            text = sys.stdin.buffer.read().decode("iso-8859-1")
            fields = _head_fields(text)
            if fields is None:
                field, policy = "Cache-Control", parse(text.strip(), strict=args.strict)
            else:
                targets = args.target or (["CDN-Cache-Control"] if args.shared else [])
                field, policy = select(fields, targets)
                if args.strict and field == "Cache-Control":
                    values = [v for n, v in fields if n.lower() == "cache-control"]
                    policy = parse(values, strict=True)
    except CacheControlError as error:
        print(f"ccdirectives: {error}", file=sys.stderr)
        return 2
    print(json.dumps(_report(field, policy, args), indent=2))
    return 0
