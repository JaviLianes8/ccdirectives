"""Typed properties of the registered directives, shared by CacheControl."""

from __future__ import annotations

from ._access import Accessors
from ._chars import DELTA_MAX


class Properties(Accessors):
    """One property per registered directive: seconds, flags and field lists."""

    @property
    def max_age(self) -> int | None:
        """``max-age`` in seconds (capped at 2^31), or None when absent or not a number.

        >>> from ccdirectives import parse
        >>> parse("max-age=60").max_age, parse("max-age=x").max_age, parse("public").max_age
        (60, None, None)
        """
        return self.seconds("max-age")

    @property
    def s_maxage(self) -> int | None:
        """``s-maxage`` in seconds (capped at 2^31), or None when absent or not a number.

        >>> from ccdirectives import parse
        >>> parse("s-maxage=99999999999").s_maxage, parse("max-age=1").s_maxage
        (2147483648, None)
        """
        return self.seconds("s-maxage")

    @property
    def min_fresh(self) -> int | None:
        """``min-fresh`` in seconds, or None when absent or not a number.

        >>> from ccdirectives import parse
        >>> parse('min-fresh="30"').min_fresh, parse("min-fresh").min_fresh
        (30, None)
        """
        return self.seconds("min-fresh")

    @property
    def max_stale(self) -> int | None:
        """Seconds of staleness accepted; a bare ``max-stale`` accepts any, read as 2^31.

        >>> from ccdirectives import parse
        >>> parse("max-stale=5").max_stale, parse("max-stale").max_stale
        (5, 2147483648)
        """
        if dict.get(self.directives, "max-stale") is True:
            return DELTA_MAX
        return self.seconds("max-stale")

    @property
    def stale_while_revalidate(self) -> int | None:
        """``stale-while-revalidate`` in seconds (RFC 5861), or None.

        >>> from ccdirectives import parse
        >>> parse("max-age=1, stale-while-revalidate=30").stale_while_revalidate
        30
        """
        return self.seconds("stale-while-revalidate")

    @property
    def stale_if_error(self) -> int | None:
        """``stale-if-error`` in seconds (RFC 5861), or None.

        >>> from ccdirectives import parse
        >>> parse("stale-if-error=600").stale_if_error, parse("public").stale_if_error
        (600, None)
        """
        return self.seconds("stale-if-error")

    @property
    def no_cache(self) -> bool:
        """True when ``no-cache`` is present, qualified or not.

        >>> from ccdirectives import parse
        >>> parse("no-cache").no_cache, parse('no-cache="ETag"').no_cache, parse("").no_cache
        (True, True, False)
        """
        return self.has("no-cache")

    @property
    def no_cache_fields(self) -> tuple[str, ...]:
        """Field names of a qualified ``no-cache``, lower-cased; empty when unqualified.

        >>> from ccdirectives import parse
        >>> parse('no-cache="ETag, Age"').no_cache_fields, parse("no-cache").no_cache_fields
        (('etag', 'age'), ())
        """
        return self._fields("no-cache")

    @property
    def private(self) -> bool:
        """True when ``private`` is present, qualified or not.

        >>> from ccdirectives import parse
        >>> parse("private").private, parse('private="Set-Cookie"').private, parse("").private
        (True, True, False)
        """
        return self.has("private")

    @property
    def private_fields(self) -> tuple[str, ...]:
        """Field names of a qualified ``private``, lower-cased; empty when unqualified.

        >>> from ccdirectives import parse
        >>> parse('private="Set-Cookie"').private_fields, parse("private").private_fields
        (('set-cookie',), ())
        """
        return self._fields("private")

    @property
    def no_store(self) -> bool:
        """True when ``no-store`` is present.

        >>> from ccdirectives import parse
        >>> parse("no-store").no_store, parse("no-cache").no_store
        (True, False)
        """
        return self.has("no-store")

    @property
    def no_transform(self) -> bool:
        """True when ``no-transform`` is present.

        >>> from ccdirectives import parse
        >>> parse("no-transform").no_transform, parse("public").no_transform
        (True, False)
        """
        return self.has("no-transform")

    @property
    def only_if_cached(self) -> bool:
        """True when the request directive ``only-if-cached`` is present.

        >>> from ccdirectives import parse
        >>> parse("only-if-cached").only_if_cached, parse("max-age=0").only_if_cached
        (True, False)
        """
        return self.has("only-if-cached")

    @property
    def must_revalidate(self) -> bool:
        """True when ``must-revalidate`` is present.

        >>> from ccdirectives import parse
        >>> parse("must-revalidate").must_revalidate, parse("public").must_revalidate
        (True, False)
        """
        return self.has("must-revalidate")

    @property
    def proxy_revalidate(self) -> bool:
        """True when ``proxy-revalidate`` is present.

        >>> from ccdirectives import parse
        >>> parse("proxy-revalidate").proxy_revalidate, parse("public").proxy_revalidate
        (True, False)
        """
        return self.has("proxy-revalidate")

    @property
    def must_understand(self) -> bool:
        """True when ``must-understand`` is present.

        >>> from ccdirectives import parse
        >>> parse("must-understand, no-store").must_understand, parse("").must_understand
        (True, False)
        """
        return self.has("must-understand")

    @property
    def public(self) -> bool:
        """True when ``public`` is present.

        >>> from ccdirectives import CacheControl, parse
        >>> parse("public").public, CacheControl({"public": False}).public
        (True, False)
        """
        return self.has("public")

    @property
    def immutable(self) -> bool:
        """True when ``immutable`` is present (RFC 8246), with or without an argument.

        >>> from ccdirectives import parse
        >>> parse("max-age=31536000, immutable").immutable, parse("public").immutable
        (True, False)
        """
        return self.has("immutable")
