"""Parse and build the HTTP Cache-Control header as a typed, zero-dependency structure."""

from __future__ import annotations

from ._build import build
from ._model import CacheControl, DirectiveValue
from ._parse import parse

__version__ = "0.1.0"

__all__ = ["CacheControl", "DirectiveValue", "build", "parse"]
