"""Typed structure for the HTTP Cache-Control header."""

from __future__ import annotations

from collections.abc import ItemsView, Iterable, Iterator, KeysView, ValuesView
from dataclasses import dataclass, field

from ._access import Accessors, DirectiveValue, key
from ._chars import ascii_lower
from ._checks import is_a, plain_int, plain_str, shown, type_name


def _checked(name: object, value: object) -> DirectiveValue:
    # Plain values only: a subclass could change what build writes through its methods.
    text = plain_str("directive names", name)
    if is_a(value, bool):
        return value
    if is_a(value, int):
        return plain_int(value)
    if is_a(value, str):
        return str.__str__(value)
    raise TypeError(f"{shown(text)}: value must be int, str or bool, not {type_name(value)}")


def _cut(name: str) -> str:
    # A missing name is reported, cut like names in messages.
    return name if len(name) <= 40 else name[:40] + "..."


def checked_items(cache_control: CacheControl) -> list[tuple[str, DirectiveValue]]:
    """The directives as plain (name, value) pairs, checked again after any direct edit."""
    if not is_a(cache_control.directives, dict):
        raise TypeError("directives must be a dict of name to value")
    pairs = dict.items(cache_control.directives)
    return [(plain_str("directive names", name), _checked(name, value)) for name, value in pairs]


@dataclass
class CacheControl(Accessors):
    """An ordered, case-insensitive collection of Cache-Control directives.

    ``duplicates`` names the directives that appeared more than once; the stored value is
    the first occurrence. A value of ``False`` means absent: ``build`` leaves it out.
    Names are stored with ASCII letters in lower case, and values as plain ``int``,
    ``str`` or ``bool``.

    >>> cc = CacheControl({"Max-Age": 60, "private": "Set-Cookie", "MAX-AGE": 5})
    >>> cc.max_age, cc["PRIVATE"], cc.private_fields, sorted(cc.duplicates)
    (60, 'Set-Cookie', ('set-cookie',), ['max-age'])
    >>> cc["no-store"] = True
    >>> list(cc), "no-store" in cc, cc.has("public"), cc.seconds("max-age")
    (['max-age', 'private', 'no-store'], True, False, 60)
    """

    directives: dict[str, DirectiveValue] = field(default_factory=dict)
    duplicates: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        normalised: dict[str, DirectiveValue] = {}
        if not is_a(self.directives, dict):
            raise TypeError("directives must be a dict of name to value")
        if is_a(self.duplicates, (str, bytes)) or not issubclass(type(self.duplicates), Iterable):
            raise TypeError("duplicates must be an iterable of names")
        repeated = {key(name) for name in self.duplicates}
        for name, value in dict.items(self.directives):
            checked = _checked(name, value)
            folded = key(name)
            if folded in normalised:
                repeated.add(folded)
                continue
            normalised[folded] = checked
        self.directives = normalised
        self.duplicates = frozenset(repeated)

    def __getitem__(self, name: str) -> DirectiveValue:
        folded = key(name)
        try:
            return dict.__getitem__(self.directives, folded)
        except KeyError:
            raise KeyError(_cut(folded)) from None

    def __setitem__(self, name: str, value: DirectiveValue) -> None:
        checked = _checked(name, value)
        dict.__setitem__(self.directives, key(name), checked)

    def __delitem__(self, name: str) -> None:
        folded = key(name)
        try:
            dict.__delitem__(self.directives, folded)
        except KeyError:
            raise KeyError(_cut(folded)) from None

    def __contains__(self, name: object) -> bool:
        return is_a(name, str) and dict.__contains__(self.directives, ascii_lower(name))

    def __iter__(self) -> Iterator[str]:
        return iter(dict.keys(self.directives))

    def __len__(self) -> int:
        return dict.__len__(self.directives)

    def get(self, name: str, default: DirectiveValue | None = None) -> DirectiveValue | None:
        """The value of ``name``, or ``default`` when it is absent."""
        return dict.get(self.directives, key(name), default)

    def items(self) -> ItemsView[str, DirectiveValue]:
        """The (name, value) pairs in header order."""
        return dict.items(self.directives)

    def keys(self) -> KeysView[str]:
        """The names in header order."""
        return dict.keys(self.directives)

    def values(self) -> ValuesView[DirectiveValue]:
        """The values in header order."""
        return dict.values(self.directives)
