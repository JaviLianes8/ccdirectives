"""Typed structure for the HTTP Cache-Control header."""

from __future__ import annotations

from collections.abc import ItemsView, Iterator
from dataclasses import dataclass, field

from ._chars import DELTA_MAX, ascii_lower, field_names
from ._registry import REGISTERED_DIRECTIVES, REQUEST_DIRECTIVES, RESPONSE_DIRECTIVES

DirectiveValue = int | str | bool
"""A directive value: int for seconds, str for a textual argument, bool for a bare flag."""


def _checked(name: object, value: object) -> DirectiveValue:
    if not isinstance(name, str):
        raise TypeError(f"directive names must be str, not {type(name).__name__}")
    if not isinstance(value, (bool, int, str)):
        raise TypeError(f"{name!r}: value must be int, str or bool, not {type(value).__name__}")
    return value


@dataclass
class CacheControl:
    """An ordered, case-insensitive collection of Cache-Control directives.

    ``duplicates`` names the directives that appeared more than once; the stored value is
    the first occurrence. A value of ``False`` means absent: ``build`` leaves it out.
    """

    directives: dict[str, DirectiveValue] = field(default_factory=dict)
    duplicates: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        normalised: dict[str, DirectiveValue] = {}
        repeated = {ascii_lower(name) for name in self.duplicates}
        for name, value in self.directives.items():
            checked = _checked(name, value)
            key = ascii_lower(name)
            if key in normalised:
                repeated.add(key)
                continue
            normalised[key] = checked
        self.directives = normalised
        self.duplicates = frozenset(repeated)

    def __getitem__(self, name: str) -> DirectiveValue:
        return self.directives[ascii_lower(name)]

    def __setitem__(self, name: str, value: DirectiveValue) -> None:
        self.directives[ascii_lower(name)] = _checked(name, value)

    def __delitem__(self, name: str) -> None:
        del self.directives[ascii_lower(name)]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and ascii_lower(name) in self.directives

    def __iter__(self) -> Iterator[str]:
        return iter(self.directives)

    def __len__(self) -> int:
        return len(self.directives)

    def get(self, name: str, default: DirectiveValue | None = None) -> DirectiveValue | None:
        """The value of ``name``, or ``default`` when it is absent."""
        return self.directives.get(ascii_lower(name), default)

    def items(self) -> ItemsView[str, DirectiveValue]:
        """The (name, value) pairs in header order."""
        return self.directives.items()

    def has(self, name: str) -> bool:
        """True when ``name`` is present with any value other than ``False``."""
        return self.directives.get(ascii_lower(name), False) is not False

    def seconds(self, name: str) -> int | None:
        """The delta-seconds value of ``name``, or None when absent or not a number."""
        value = self.directives.get(ascii_lower(name))
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return min(value, DELTA_MAX)

    def extensions(self, context: str | None = None) -> tuple[str, ...]:
        """Names outside the registry, or outside its request or response set."""
        known = {"request": REQUEST_DIRECTIVES, "response": RESPONSE_DIRECTIVES}
        if context is not None and context not in known:
            raise ValueError(f"context must be 'request', 'response' or None, not {context!r}")
        registry = known[context] if context else REGISTERED_DIRECTIVES
        return tuple(name for name in self.directives if name not in registry)

    def _fields(self, name: str) -> tuple[str, ...]:
        value = self.directives.get(name)
        return (field_names(value) or ()) if isinstance(value, str) else ()

    @property
    def max_age(self) -> int | None:
        return self.seconds("max-age")

    @property
    def s_maxage(self) -> int | None:
        return self.seconds("s-maxage")

    @property
    def min_fresh(self) -> int | None:
        return self.seconds("min-fresh")

    @property
    def max_stale(self) -> int | None:
        """Seconds of staleness accepted; a bare ``max-stale`` accepts any, read as 2^31."""
        if self.directives.get("max-stale") is True:
            return DELTA_MAX
        return self.seconds("max-stale")

    @property
    def stale_while_revalidate(self) -> int | None:
        return self.seconds("stale-while-revalidate")

    @property
    def stale_if_error(self) -> int | None:
        return self.seconds("stale-if-error")

    @property
    def no_cache(self) -> bool:
        return self.has("no-cache")

    @property
    def no_cache_fields(self) -> tuple[str, ...]:
        """Field names of a qualified ``no-cache``, lower-cased; empty when unqualified."""
        return self._fields("no-cache")

    @property
    def private(self) -> bool:
        return self.has("private")

    @property
    def private_fields(self) -> tuple[str, ...]:
        """Field names of a qualified ``private``, lower-cased; empty when unqualified."""
        return self._fields("private")

    @property
    def no_store(self) -> bool:
        return self.has("no-store")

    @property
    def no_transform(self) -> bool:
        return self.has("no-transform")

    @property
    def only_if_cached(self) -> bool:
        return self.has("only-if-cached")

    @property
    def must_revalidate(self) -> bool:
        return self.has("must-revalidate")

    @property
    def proxy_revalidate(self) -> bool:
        return self.has("proxy-revalidate")

    @property
    def must_understand(self) -> bool:
        return self.has("must-understand")

    @property
    def public(self) -> bool:
        return self.has("public")

    @property
    def immutable(self) -> bool:
        return self.has("immutable")
