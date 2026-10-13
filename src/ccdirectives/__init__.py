"""Parse and build the HTTP Cache-Control header as a typed, zero-dependency structure."""

from __future__ import annotations

from ._build import build
from ._chars import DELTA_MAX
from ._errors import CacheControlError
from ._fresh import Freshness, assess, current_age, freshness_lifetime, may_store
from ._model import CacheControl, DirectiveValue
from ._parse import parse
from ._registry import REGISTERED_DIRECTIVES, REQUEST_DIRECTIVES, RESPONSE_DIRECTIVES
from ._targeted import build_targeted, parse_targeted, select

__version__ = "0.2.0"

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
