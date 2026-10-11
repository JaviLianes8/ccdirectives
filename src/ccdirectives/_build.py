"""Build a Cache-Control header string from a CacheControl structure."""

from __future__ import annotations

from ._model import CacheControl

_TOKEN_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$%&'*+-.^_`|~"
)


def build(cache_control: CacheControl) -> str:
    """Render a CacheControl back into a header value, quoting arguments when required."""
    parts: list[str] = []
    for name, value in cache_control.directives.items():
        if isinstance(value, bool):
            if value:
                parts.append(name)
        elif isinstance(value, int):
            parts.append(f"{name}={value}")
        else:
            parts.append(f"{name}={_format(value)}")
    return ", ".join(parts)


def _format(value: str) -> str:
    if value and all(char in _TOKEN_CHARS for char in value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
