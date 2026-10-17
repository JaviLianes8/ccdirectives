"""Argument checks shared by the public functions, with messages of bounded length."""

from __future__ import annotations

import math

_SHOWN = 40
# The slot of type itself: a metaclass property named __name__ cannot replace what it reads.
_TYPE_NAME = type.__dict__["__name__"]


def type_name(value: object) -> str:
    """The name of the type of ``value``, cut so a hostile class cannot inflate a message."""
    name: str = _TYPE_NAME.__get__(type(value))
    return str.__getitem__(name, slice(0, _SHOWN))


def shown(text: str) -> str:
    """``repr`` of at most the first 40 characters of ``text``, marked when cut."""
    plain = str.__str__(text)
    if len(plain) <= _SHOWN:
        return repr(plain)
    return repr(plain[:_SHOWN]) + "..."


def check_bool(name: str, value: object) -> bool:
    """``value`` when it is a real bool; any other truth value is refused."""
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool, got {type_name(value)}")
    return value


def plain_str(name: str, value: object) -> str:
    """``value`` as a plain str, so a subclass cannot steer the result through its methods."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be str, not {type_name(value)}")
    return str.__str__(value)


def plain_int(value: int) -> int:
    """A plain int with the value of an int (or a subclass), without calling its methods."""
    return int.__int__(value)


def check_time(name: str, value: object) -> float:
    """A finite int or float, as a plain number; bool and other types are refused.

    An int stays an int so the arithmetic is exact; one beyond the range of a float is
    refused like an infinity, since it cannot be mixed with float times.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be an int or a float, got {type_name(value)}")
    number = float.__float__(value) if isinstance(value, float) else plain_int(value)
    try:
        finite = math.isfinite(number)
    except OverflowError:
        raise ValueError(f"{name} is out of the range of a float") from None
    if not finite:
        raise ValueError(f"{name} must be finite")
    return number


def check_seconds(name: str, value: object) -> int:
    """A whole, non-negative number of seconds as a plain int."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type_name(value)}")
    seconds = plain_int(value)
    if seconds < 0:
        raise ValueError(f"{name} cannot be negative")
    return seconds
