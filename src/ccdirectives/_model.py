"""Typed structure for the HTTP Cache-Control header."""

from __future__ import annotations

from collections.abc import ItemsView, Iterator
from dataclasses import dataclass, field

DirectiveValue = int | str | bool
"""A directive value: int for seconds, str for a textual argument, bool for a bare flag."""

NUMERIC_DIRECTIVES: frozenset[str] = frozenset(
    {
        "max-age",
        "s-maxage",
        "min-fresh",
        "max-stale",
        "stale-while-revalidate",
        "stale-if-error",
    }
)


@dataclass
class CacheControl:
    """An ordered, case-insensitive collection of Cache-Control directives."""

    directives: dict[str, DirectiveValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.directives = {name.lower(): value for name, value in self.directives.items()}

    def __getitem__(self, name: str) -> DirectiveValue:
        return self.directives[name.lower()]

    def __setitem__(self, name: str, value: DirectiveValue) -> None:
        self.directives[name.lower()] = value

    def __delitem__(self, name: str) -> None:
        del self.directives[name.lower()]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name.lower() in self.directives

    def __iter__(self) -> Iterator[str]:
        return iter(self.directives)

    def __len__(self) -> int:
        return len(self.directives)

    def get(self, name: str, default: DirectiveValue | None = None) -> DirectiveValue | None:
        return self.directives.get(name.lower(), default)

    def items(self) -> ItemsView[str, DirectiveValue]:
        return self.directives.items()

    def _seconds(self, name: str) -> int | None:
        value = self.directives.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    def _flag(self, name: str) -> bool:
        return bool(self.directives.get(name, False))

    @property
    def max_age(self) -> int | None:
        return self._seconds("max-age")

    @property
    def s_maxage(self) -> int | None:
        return self._seconds("s-maxage")

    @property
    def min_fresh(self) -> int | None:
        return self._seconds("min-fresh")

    @property
    def max_stale(self) -> int | None:
        return self._seconds("max-stale")

    @property
    def stale_while_revalidate(self) -> int | None:
        return self._seconds("stale-while-revalidate")

    @property
    def stale_if_error(self) -> int | None:
        return self._seconds("stale-if-error")

    @property
    def no_cache(self) -> bool:
        return self._flag("no-cache")

    @property
    def no_store(self) -> bool:
        return self._flag("no-store")

    @property
    def no_transform(self) -> bool:
        return self._flag("no-transform")

    @property
    def only_if_cached(self) -> bool:
        return self._flag("only-if-cached")

    @property
    def must_revalidate(self) -> bool:
        return self._flag("must-revalidate")

    @property
    def proxy_revalidate(self) -> bool:
        return self._flag("proxy-revalidate")

    @property
    def must_understand(self) -> bool:
        return self._flag("must-understand")

    @property
    def public(self) -> bool:
        return self._flag("public")

    @property
    def private(self) -> bool:
        return self._flag("private")

    @property
    def immutable(self) -> bool:
        return self._flag("immutable")
