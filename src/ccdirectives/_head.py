"""Read the fields of a response head, as printed by ``curl -sI``, for the command line."""

from __future__ import annotations

import email.utils

from ._chars import ascii_lower, delta_seconds


def head_fields(text: str) -> list[tuple[str, str]] | None:
    """The fields of the last response head in a dump, or None when it holds no head.

    A redirect chain prints one head per response; the last is the one a cache stores.
    Continuation lines (obs-fold) join the previous field with a space, as RFC 9112
    section 5.2 allows a recipient to do.
    """
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("HTTP/")]
    if not starts:
        return None
    fields: list[tuple[str, list[str]]] = []
    kept = False
    for raw in lines[starts[-1] + 1 :]:
        line = raw.rstrip("\r")
        if not line:
            break
        if line[0] in " \t":
            # Parts are joined once at the end: joining on every line would be quadratic.
            # A continuation of a line that was not kept is dropped with it.
            if kept:
                fields[-1][1].append(line.strip(" \t"))
            continue
        name, colon, value = line.partition(":")
        kept = bool(colon and name and name == name.strip())
        if kept:
            fields.append((name, [value.strip(" \t")]))
    return [(name, " ".join(part for part in parts if part)) for name, parts in fields]


def field(fields: list[tuple[str, str]], name: str) -> str | None:
    """The first value of ``name``, compared case-insensitively."""
    wanted = ascii_lower(name)
    return next((value for key, value in fields if ascii_lower(key) == wanted), None)


def age_of(fields: list[tuple[str, str]]) -> int:
    """The Age field as delta-seconds, 0 when absent or invalid (RFC 9111 section 5.1)."""
    value = field(fields, "Age")
    return (delta_seconds(value.strip()) or 0) if value is not None else 0


def http_date(value: str | None) -> float | None:
    """Seconds since the epoch for an HTTP-date, or None when it does not parse."""
    if value is None:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        # OverflowError: a year or an offset too large for a date, which is no HTTP-date either.
        return None
    return parsed.timestamp() if parsed.tzinfo is not None else None
