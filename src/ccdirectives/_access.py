"""Typed reads of the registered directives, shared by CacheControl."""

from __future__ import annotations

from typing import Literal

from ._chars import DELTA_MAX, ascii_lower, delta_seconds, field_names
from ._checks import plain_str
from ._registry import REGISTERED_DIRECTIVES, REQUEST_DIRECTIVES, RESPONSE_DIRECTIVES

DirectiveValue = int | str | bool
"""A directive value: int for seconds, str for a textual argument, bool for a bare flag."""


def key(name: object) -> str:
    """A directive name as stored: a plain str with ASCII letters in lower case."""
    return ascii_lower(plain_str("directive names", name))


class Accessors:
    """Typed reads over ``directives``; CacheControl provides the mapping itself."""

    directives: dict[str, DirectiveValue]

    def has(self, name: str) -> bool:
        """True when ``name`` is present with any value other than ``False``."""
        return self.directives.get(key(name), False) is not False

    def seconds(self, name: str) -> int | None:
        """The delta-seconds value of ``name``, or None when absent or not a number."""
        value = self.directives.get(key(name))
        if isinstance(value, str):
            return delta_seconds(value)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        return min(value, DELTA_MAX)

    def extensions(self, context: Literal["request", "response"] | None = None) -> tuple[str, ...]:
        """Names outside the registry, or outside its request or response set."""
        known = {"request": REQUEST_DIRECTIVES, "response": RESPONSE_DIRECTIVES}
        if context is not None and not (isinstance(context, str) and context in known):
            raise ValueError("context must be 'request', 'response' or None")
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
