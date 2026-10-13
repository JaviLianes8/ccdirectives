"""The exception raised for input that breaks the rules in strict mode or on build."""

from __future__ import annotations


class CacheControlError(ValueError):
    """A header value or a directive set that breaks the RFC rules.

    ``offset`` is the index in the header value where the problem starts, or None when the
    error is about a structure rather than a position in text.
    """

    def __init__(self, message: str, offset: int | None = None) -> None:
        super().__init__(message if offset is None else f"{message} at offset {offset}")
        self.reason = message
        self.offset = offset
