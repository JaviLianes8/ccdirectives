# ccdirectives

Parse, validate and build the HTTP `Cache-Control` header (RFC 9111) and targeted fields
such as `CDN-Cache-Control` (RFC 9213), and decide freshness, typed and zero-dependency.

The [guide](https://github.com/JaviLianes8/ccdirectives/blob/main/GUIDE.md) is the full reference (every rule, error and option) and
the [changelog](https://github.com/JaviLianes8/ccdirectives/blob/main/CHANGELOG.md) lists what changed in each release.

## Install

```
pip install ccdirectives
```

## Usage

Read what a response allows:

```python
from ccdirectives import parse

cc = parse('max-age=600, no-cache="Set-Cookie", x-vendor=custom, MAX-AGE=5')
print(cc.max_age, cc.no_cache, cc.no_cache_fields)
# 600 True ('set-cookie',)
print(cc["x-vendor"], cc.extensions(), sorted(cc.duplicates))
# custom ('x-vendor',) ['max-age']
```

Names compare case-insensitively (ASCII letters only), delta-seconds become ints, and the
first occurrence of a repeated directive wins, as RFC 9111 section 4.2.1 says; repeated
names are listed in `duplicates`. delta-seconds are ASCII digits only, and a value too
large to represent is read as 2147483648, the "forever" of section 1.2.2:

```python
from ccdirectives import parse

print(parse("max-age=99999999999").max_age, parse("max-age=-5").max_age)
# 2147483648 None
print(parse("max-stale").max_stale, parse(["max-age=60", "public"]).public)
# 2147483648 True
```

The default parser never raises on content: what it cannot read is skipped, and a broken
quote cannot hide the directives after it. Strict mode validates instead, with the rules
of a request or a response when you pass `context`. It holds a header to what a recipient
must accept, so `max-age="60"` passes although a sender should not write it:

```python
from ccdirectives import CacheControlError, parse

print(parse('private="a, x="open, no-store').no_store)
# True
try:
    parse("max-age=60, no-store=1", strict=True, context="response")
except CacheControlError as error:
    print(error)
# 'no-store' takes no argument at offset 12
```

`build` writes a value back and refuses what the grammar cannot carry, such as a line
break in an argument, a negative age or a name that is not a token. delta-seconds go out
as tokens and field lists as quoted strings, so the output always passes strict mode:

```python
from ccdirectives import CacheControl, build

print(build(CacheControl({"max-age": 3600, "private": "Set-Cookie", "immutable": True})))
# max-age=3600, private="Set-Cookie", immutable
```

### Freshness

`assess` applies RFC 9111 section 4.2 and RFC 5861 to a stored response of a given age,
optionally narrowed by the request directives:

```python
from ccdirectives import assess, parse

response = parse("max-age=600, stale-while-revalidate=30, stale-if-error=1200")
verdict = assess(response, age=620)
print(verdict.fresh, verdict.reusable, verdict.stale_while_revalidate, verdict.stale_if_error)
# False False True True
print(assess(response, age=620, request=parse("max-stale=60")).reusable)
# True
```

`freshness_lifetime` and `current_age` expose the two calculations on their own (Expires
and Date are passed as seconds since the epoch), and `may_store` says whether the
directives let a private or shared cache store a response at all.

### Targeted fields

Targeted fields are structured field dictionaries (RFC 9651) with their own error rules:
an empty or invalid field is ignored. `select` walks a cache's target list and falls back
on `Cache-Control`:

```python
from ccdirectives import assess, select

headers = {"Cache-Control": "max-age=60, s-maxage=120", "CDN-Cache-Control": "max-age=600"}
field, policy = select(headers, ["CDN-Cache-Control"])
print(field, assess(policy, age=0, shared=True).lifetime)
# CDN-Cache-Control 600
broken = {"CDN-Cache-Control": "max-age=1.5", "Cache-Control": "no-store"}
print(select(broken, ["CDN-Cache-Control"]))
# ('CDN-Cache-Control', CacheControl(directives={}, duplicates=frozenset()))
```

A `max-age` that is a Decimal breaks the directive's rules, so RFC 9213 says not to use
it; the field itself is valid, so it still wins over `Cache-Control`.

### Command line

```
$ curl -sI https://example.com/ | ccdirectives --shared
$ ccdirectives --strict --age 30 "max-age=60, stale-while-revalidate=30"
```

It reads a header value, or a response head on standard input (the last response of a
redirect chain), and prints the chosen field, its directives and the freshness verdict as
JSON. From a head it takes the age from `Age` and, when `Cache-Control` applies, the
lifetime fallback from `Expires` and `Date`. `--target` sets the target list; it defaults
to `CDN-Cache-Control` with `--shared`. The exit status is 1 for a value `--strict`
rejects or an output that closes early, 2 for a usage error and 130 when interrupted.

## API

| Name | What it does |
| --- | --- |
| `parse(header, *, strict=False, context=None)` | Read a field value or a list of field lines into a `CacheControl` |
| `build(cc)` | Write a `CacheControl` as a field value |
| `CacheControl` | Ordered, case-insensitive mapping with typed accessors and `duplicates` |
| `DirectiveValue` | `int`, `str` or `bool`, the type of a directive value |
| `CacheControlError` | `ValueError` with `reason` and `offset` for strict mode and `build` |
| `parse_targeted(value)` | Read a targeted field, or None when RFC 9213 says to ignore it |
| `build_targeted(cc)` | Write a `CacheControl` as a structured field dictionary |
| `select(headers, targets)` | The field name and policy a cache with that target list follows |
| `assess(response, *, age, ...)` | A `Freshness` verdict for a stored response |
| `Freshness` | Lifetime, age, fresh, reusable and the two stale windows |
| `freshness_lifetime(response, ...)` | Lifetime by the rules of RFC 9111 section 4.2.1 |
| `current_age(...)` | Age by the rules of RFC 9111 section 4.2.3 |
| `may_store(response, ...)` | Whether the directives allow a cache to store the response |
| `DELTA_MAX` | 2147483648, the value an overflowing delta-seconds becomes |
| `REGISTERED_DIRECTIVES` | The names in the IANA HTTP Cache Directive Registry |
| `REQUEST_DIRECTIVES`, `RESPONSE_DIRECTIVES` | The registered names defined for each direction |

## Why

Every HTTP client, server and cache has to read `Cache-Control`, yet the parsers that
exist come with something bigger: `werkzeug.http.parse_cache_control_header` and
`webob.cachecontrol` belong to those frameworks, and `CacheControl` and `hishel` are
caching layers for requests and httpx whose parsers serve their own transports
(`CacheControl` splits the value at every comma, so a quoted field list is not read as
one). None of them reads `CDN-Cache-Control` (checked in Werkzeug 3.1.9, WebOb 1.8.11,
CacheControl 0.14.4 and hishel 1.4.0). This library is the codec and the freshness
arithmetic: a typed structure in, a correct header out, strict validation with offsets
when you want it, and nothing else to install. Where it answers differently from those
libraries, the [guide](https://github.com/JaviLianes8/ccdirectives/blob/main/GUIDE.md#compared-with-other-libraries) says so.

## License

MIT. See [LICENSE](https://github.com/JaviLianes8/ccdirectives/blob/main/LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
