# ccdirectives

Parse and build the HTTP Cache-Control header as a typed, zero-dependency structure.

## Install

```
pip install ccdirectives
```

## Usage

```python
from ccdirectives import build, parse

cc = parse("max-age=600, no-store, private=\"Set-Cookie\", x-vendor=custom")

cc.max_age          # 600  (numeric directives come back as ints)
cc.no_store         # True (bare flags are booleans)
cc.private          # True
cc["x-vendor"]      # "custom"  (unknown directives are preserved)
"MAX-AGE" in cc     # True  (names are case-insensitive)

build(cc)           # 'max-age=600, no-store, private=Set-Cookie, x-vendor=custom'
```

Construct one directly and render it:

```python
from ccdirectives import CacheControl, build

build(CacheControl({"max-age": 3600, "s-maxage": 60, "immutable": True}))
# 'max-age=3600, s-maxage=60, immutable'
```

`parse` never raises: malformed tokens are skipped and unparseable numeric values are
kept as strings. Arguments that contain characters outside the token set are quoted and
escaped on `build`, so a parse then build round-trip preserves the directives.

## Why

Every HTTP client, server and cache has to read `Cache-Control`, yet there is no small,
typed, zero-dependency library that both parses and builds it. The parsers that exist are
framework-bound: `werkzeug.http.parse_cache_control_header` ties you to Werkzeug and
`webob.cachecontrol` to WebOb, while packages such as `CacheControl` and `hishel` are
full cache transports, not directive codecs. So the logic gets hand-written and
re-written in project after project. This library is just the codec: a typed structure in,
a correct header out, and nothing else to install.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
