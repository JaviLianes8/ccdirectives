"""Parse and build the HTTP Cache-Control header as a typed, zero-dependency structure.

The constants:

>>> from ccdirectives import DELTA_MAX, REGISTERED_DIRECTIVES, REQUEST_DIRECTIVES
>>> from ccdirectives import RESPONSE_DIRECTIVES, DirectiveValue
>>> DELTA_MAX == 2**31
True
>>> len(REGISTERED_DIRECTIVES), "immutable" in RESPONSE_DIRECTIVES - REQUEST_DIRECTIVES
(16, True)
>>> sorted(REQUEST_DIRECTIVES - RESPONSE_DIRECTIVES)
['max-stale', 'min-fresh', 'only-if-cached']
>>> isinstance(60, DirectiveValue), isinstance(1.5, DirectiveValue)
(True, False)
"""

from ._access import DirectiveValue
from ._build import build
from ._chars import DELTA_MAX
from ._errors import CacheControlError
from ._fresh import Freshness, assess, current_age, freshness_lifetime, may_store
from ._model import CacheControl
from ._parse import parse
from ._registry import REGISTERED_DIRECTIVES, REQUEST_DIRECTIVES, RESPONSE_DIRECTIVES
from ._targeted import build_targeted, parse_targeted, select

__version__ = "1.0.0"

__all__ = [
    "DELTA_MAX",
    "REGISTERED_DIRECTIVES",
    "REQUEST_DIRECTIVES",
    "RESPONSE_DIRECTIVES",
    "CacheControl",
    "CacheControlError",
    "DirectiveValue",
    "Freshness",
    "assess",
    "build",
    "build_targeted",
    "current_age",
    "freshness_lifetime",
    "may_store",
    "parse",
    "parse_targeted",
    "select",
]

# Public classes and functions report the package, not the private module that holds them,
# so reprs, pickles and documentation tools point at the stable import path.
for _public in (
    CacheControl,
    CacheControlError,
    Freshness,
    assess,
    build,
    build_targeted,
    current_age,
    freshness_lifetime,
    may_store,
    parse,
    parse_targeted,
    select,
):
    _public.__module__ = __name__
del _public
