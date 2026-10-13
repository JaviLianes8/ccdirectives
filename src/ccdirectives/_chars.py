"""Character classes and value rules shared by the parser and the builder."""

from __future__ import annotations

# RFC 9110 section 5.6.2: tchar is any VCHAR except the delimiters.
TCHAR = frozenset("!#$%&'*+-.^_`|~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
DIGITS = frozenset("0123456789")
OWS = " \t"

# RFC 9111 section 1.2.2: an overflowing delta-seconds is read as 2^31, meaning "forever".
DELTA_MAX = 2147483648


def is_token(text: str) -> bool:
    """True when ``text`` is a non-empty RFC 9110 token."""
    return bool(text) and all(char in TCHAR for char in text)


def ascii_lower(text: str) -> str:
    # str.lower() folds non-ASCII letters too (the Kelvin sign becomes "k"), which would let a
    # look-alike name match a registered directive.
    return text.translate(_LOWER)


_LOWER = {code: code + 32 for code in range(ord("A"), ord("Z") + 1)}


def delta_seconds(text: str) -> int | None:
    """Read ``1*DIGIT`` as an int capped at 2^31, or None when it is not delta-seconds."""
    if not text or any(char not in DIGITS for char in text):
        return None
    # Compare by length first so a huge string is never converted in full.
    stripped = text.lstrip("0") or "0"
    if len(stripped) > len(str(DELTA_MAX)):
        return DELTA_MAX
    return min(int(stripped), DELTA_MAX)


def is_qdtext(char: str) -> bool:
    """True for a character allowed unescaped inside an RFC 9110 quoted-string."""
    code = ord(char)
    return (
        code in (0x09, 0x20, 0x21)
        or 0x23 <= code <= 0x5B
        or 0x5D <= code <= 0x7E
        or (0x80 <= code <= 0xFF)
    )


def is_quotable(char: str) -> bool:
    """True for a character that may follow a backslash in a quoted-pair."""
    code = ord(char)
    return code in (0x09, 0x20) or 0x21 <= code <= 0x7E or 0x80 <= code <= 0xFF


def field_names(text: str) -> tuple[str, ...] | None:
    """Split a ``#field-name`` list, lower-cased, or None when an element is not a token."""
    names: list[str] = []
    for element in text.split(","):
        name = element.strip(OWS)
        if not name:
            continue
        if not is_token(name):
            return None
        names.append(ascii_lower(name))
    return tuple(names)
