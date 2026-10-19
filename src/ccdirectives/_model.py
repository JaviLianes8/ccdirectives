"""Typed structure for the HTTP Cache-Control header."""

from __future__ import annotations

from collections.abc import ItemsView, Iterable, Iterator, KeysView, ValuesView
from dataclasses import dataclass, field

from ._access import DirectiveValue, key
from ._chars import ascii_lower
from ._checks import is_a, plain_int, plain_str, shown, type_name
from ._props import Properties


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
    raw = cache_control.directives
    if not is_a(raw, dict):
        raise TypeError("directives must be a dict of name to value")
    pairs = [(plain_str("directive names", n), _checked(n, v)) for n, v in dict.items(raw)]
    # False means absent, also when it was set directly in ``directives``.
    return [(name, value) for name, value in pairs if value is not False]


def _compared(
    cache_control: CacheControl,
) -> tuple[dict[str, tuple[str, DirectiveValue]], frozenset[str]]:
    # A dict takes False for 0 and True for 1, but "max-age=0" and no max-age differ.
    pairs = {name: (type(value).__name__, value) for name, value in checked_items(cache_control)}
    return pairs, frozenset(key(name) for name in cache_control.duplicates)


@dataclass(eq=False)
class CacheControl(Properties):
    """An ordered, case-insensitive collection of Cache-Control directives.

    ``duplicates`` names the directives that appeared more than once; the stored value is
    the first occurrence. A value of ``False`` means absent: construction and assignment
    drop the name, so it is neither stored nor counted as an occurrence.
    Names are stored with ASCII letters in lower case, and values as plain ``int``,
    ``str`` or ``bool``. Two structures are equal when they hold the same names, values of
    the same type and duplicates, in any order, so ``0`` and ``False`` differ.

    >>> cc = CacheControl({"Max-Age": 60, "private": "Set-Cookie", "MAX-AGE": 5})
    >>> cc.max_age, cc["PRIVATE"], cc.private_fields, sorted(cc.duplicates)
    (60, 'Set-Cookie', ('set-cookie',), ['max-age'])
    >>> cc["no-store"] = True
    >>> list(cc), "no-store" in cc, cc.has("public"), cc.seconds("max-age")
    (['max-age', 'private', 'no-store'], True, False, 60)
    >>> CacheControl({"max-age": 0}) == CacheControl({"max-age": False})
    False
    >>> CacheControl({"public": False}) == CacheControl(), len(CacheControl({"public": False}))
    (True, 0)
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
            if checked is False:
                continue
            if folded in normalised:
                repeated.add(folded)
                continue
            normalised[folded] = checked
        self.directives = normalised
        self.duplicates = frozenset(repeated)

    def __eq__(self, other: object) -> bool:
        if type(other) is not type(self):
            return NotImplemented
        return _compared(self) == _compared(other)

    def __getitem__(self, name: str) -> DirectiveValue:
        folded = key(name)
        try:
            return dict.__getitem__(self.directives, folded)
        except KeyError:
            raise KeyError(_cut(folded)) from None

    def __setitem__(self, name: str, value: DirectiveValue) -> None:
        checked = _checked(name, value)
        if checked is False:
            dict.pop(self.directives, key(name), None)
        else:
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
        """The value of ``name``, or ``default`` when it is absent.

        >>> CacheControl({"max-age": 60}).get("Max-Age"), CacheControl().get("public", False)
        (60, False)
        """
        return dict.get(self.directives, key(name), default)

    def items(self) -> ItemsView[str, DirectiveValue]:
        """The (name, value) pairs in header order.

        >>> list(CacheControl({"no-store": True, "Max-Age": 0}).items())
        [('no-store', True), ('max-age', 0)]
        """
        return dict.items(self.directives)

    def keys(self) -> KeysView[str]:
        """The names in header order.

        >>> list(CacheControl({"Private": "ETag", "max-age": 5}).keys())
        ['private', 'max-age']
        """
        return dict.keys(self.directives)

    def values(self) -> ValuesView[DirectiveValue]:
        """The values in header order.

        >>> list(CacheControl({"private": "ETag", "max-age": 5}).values())
        ['ETag', 5]
        """
        return dict.values(self.directives)
