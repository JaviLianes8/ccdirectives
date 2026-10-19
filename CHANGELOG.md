# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-19

The public API is now stable: the seventeen names in `__all__`, their signatures and
defaults, the error types and the command line options are kept for the 1.x series.
Results on valid input are the same as in 0.2.0, except for the corrections listed under
Fixed and three changes listed under Changed: ages and lifetimes are capped at
2147483648, the time arithmetic is exact, and equality tells `0` from `False`.

### Added

- `CacheControl.keys()` and `values()`, so `dict(cc)` copies the directives.
- `GUIDE.md`, the reference for every rule, error and option, the command line, the
  differences from Werkzeug, hishel and CacheControl, and upgrading from 0.2.0.
- A runnable example in the docstring of every public name and `CacheControl` method.

### Changed

- `strict`, `shared`, `authorized` and `understood_status` must be `bool`; any other
  value raises `TypeError` instead of being read by its truth value.
- Directive names must be `str` in every `CacheControl` method (`get`, `has`, `seconds`,
  item access and deletion), raising `TypeError` instead of `AttributeError`.
- `build`, `build_targeted`, `assess`, `freshness_lifetime` and `may_store` raise
  `TypeError` for an argument that is not a `CacheControl`; `select` and
  `parse_targeted` raise `TypeError` for names, values or targets that are not `str`, and
  `select` for an item of a list that is not a (name, value) tuple or list (a
  two-character string was read as a name and a value).
- Values are stored as plain `int`, `str` and `bool`: a subclass can no longer change what
  `build` writes through its own methods (an `int` whose `__str__` returned a line break
  was written into the header). Types are checked on the real type, so an object whose
  `__class__` claims to be `bool`, `int` or `str` is refused, and values set directly in
  `directives` (even in a `dict` subclass) are read as plain values.
- Times passed to `current_age` and `freshness_lifetime` must be finite numbers
  (`ValueError` for NaN, infinities and an `int` beyond the range of a float, `TypeError`
  for `bool`, strings and other types); `age_value` must be an `int`. An `age` given to
  `assess` or an `age_value` past 2147483648 is read as 2147483648 before the calculation
  (so with skewed clocks such an `age_value` can give a different age than in 0.2.0); a
  calculation that overflows, and any lifetime or age past 2147483648, is 2147483648, as
  RFC 9111 section 1.2.2 says. The time arithmetic is exact (ints and floats are mixed
  without rounding), so huge ints next to floats no longer raise `OverflowError`; where
  float rounding used to cross a whole second the result is now the exact one.
- Error messages show at most 40 characters of a directive name and never a directive
  value or an unknown `context`; type names in messages are cut to 40 characters.
- `build` raises `CacheControlError` for an extension integer past the interpreter's limit
  on int to str conversion (4300 digits by default) instead of that `ValueError`.
- `build_targeted` refuses an extension integer of more than 15 digits with a message that
  names the directive (it was refused before, without the name).
- `CacheControl.extensions` types `context` as `"request"`, `"response"` or None, like
  `parse`; other values still raise `ValueError` at run time.
- `CacheControl(duplicates=...)` takes any iterable of names but refuses a string. A
  missing name raises `KeyError` with the name cut to 40 characters.
- Two `CacheControl` structures are equal only when their values also have the same
  type: `max-age=0` and a `max-age` of `False` (absent), or `1` and `True`, no longer
  compare equal. Comparing a structure whose `directives` were edited to hold a value of
  another type raises `TypeError`, as `build` does.
- A `False` value means absent everywhere: `CacheControl` leaves such a name out when it
  is built (so it is not counted as a duplicate either) and assigning `False` removes the
  name, so `in`, `len`, iteration, `keys`, `dict(cc)`, `extensions()` and equality agree
  with `has()`, the properties and `build`. A `False` placed directly in `directives` is
  skipped by `build`, `build_targeted` and equality and is absent to `has()` and the
  properties, while `in`, `len`, iteration, `dict(cc)` and `extensions()` still see it.
- `build` and `build_targeted` raise `CacheControlError` for a number on `no-cache` or
  `private`: the structure read `private=5` as bare `private`, while the written
  `private=5` reads as a list naming field `5`, which loosened what a shared cache may
  store.
- `select` types its pairs as tuples or lists of two, as documented, and raises a
  `TypeError` with a bounded message for headers or targets that are not iterable (the
  interpreter's message repeated the whole type name).
- `CacheControl` properties each have a docstring with an example.
- Public names report `ccdirectives` as their module; the stray `annotations` attribute is
  gone from the package.
- Command line: `--age` takes ASCII digits only (no sign, underscore or other digits);
  on POSIX an argument is read as the octets it was given, like standard input; a closed
  output (also a stream object closed in the calling process) exits 1 without a traceback,
  an interrupt exits 130, a closed standard input is a
  usage error; folded header lines are joined in linear time. Usage errors show at most
  200 characters of the problem (an unrecognized argument was repeated whole), and
  `--help` follows the rules of the report: a closed output exits 1 quietly (it exited
  120 with a warning, or with a traceback on Python 3.10).
- Command line help: the placeholders read `VALUE`, `SECONDS` and `FIELD`, and the
  description lists every exit status.
- Packaging: `Development Status :: 5 - Production/Stable`; the project URL `Repository`
  is now `Source`; the `dev` extra adds pytest-timeout and the pinned Werkzeug, hishel and
  CacheControl used as reference parsers. The sdist is built from an explicit list of
  files.

### Fixed

- `may_store` treats `private` with an empty list (`private=""`, `private=`) as
  unqualified, so a shared cache does not store the response: RFC 9111 section 5.2.2.7
  qualifies `private` only with one or more field names.
- `parse_targeted` keeps an invalid `s-maxage` bare instead of dropping it, so a shared
  cache gets a lifetime of 0 and no stale use, as with an invalid value in
  `Cache-Control`.
- The command line no longer stops with a traceback when a response head has an
  `Expires` or `Date` with a year or a time zone offset too large for a date. Such a
  value does not parse, so `Expires` means already expired (RFC 9111 section 5.3) and
  `Date` is replaced by the current time.
- The command line reads HTTP dates by RFC 9110 section 5.6.7 instead of the e-mail date
  rules: the asctime format is accepted (an asctime `Expires` was read as already
  expired and an asctime `Date` replaced by the current time), a two-digit RFC 850 year
  follows the 50-year rule (`70` is 2070 in 2026, not 1970), a four-digit year is read as
  written (`0049` was read as 2049, making a long past `Expires` fresh for decades), a
  two-digit year in an IMF-fixdate is invalid, and a zone other than `GMT` is invalid, as
  RFC 9111 section 4.2 asks for expiration.
- The command line reads a list-based `Age` (`Age: 100, 5`) by its first member as RFC
  9111 section 5.1 asks; it was read as 0, so a stale response was reported fresh. Only
  spaces and tabs around the value are stripped, so `Age` with a no-break space or another
  control character before the digits is invalid (0).
- The command line reads every `Age` line as one list and skips its empty members, as
  RFC 9110 section 5.6.1.2 asks: `Age: , 100`, or an empty `Age` line before `Age: 100`,
  was read as 0, so a stale response was reported fresh.
- HTTP dates accept `GMT` in any case (ASCII only), as RFC 9111 section 4.2 asks of a
  cache; an `Expires` ending in `gmt` was read as already expired and such a `Date`
  replaced by the current time.
- The RFC 850 50-year rule compares whole instants, not years: with the current time
  2026-10-19, `31-Dec-76` is more than 50 years ahead and is now 1976, not 2076.
- The RFC 850 year is chosen among the years that have the day: read in 2060,
  `29-Feb-00` is 2000-02-29; it was invalid because 2100 has no 29 February, so such an
  `Expires` was read as already expired and such a `Date` replaced by the current time.
- The command line drops the continuation lines of a response head field it does not
  read (a name with whitespace before the colon); they were added to the field above it.

## [0.2.0] - 2026-10-17

### Added

- Strict mode: `parse(header, strict=True, context=...)` raises `CacheControlError` with the
  offset for syntax outside RFC 9111 section 5.2, control characters, repeated directives,
  malformed delta-seconds, arguments on directives that take none and field lists that are
  not field names.
- Several field lines can be passed as a list.
- Freshness helpers: `assess` and `Freshness`, `freshness_lifetime`, `current_age` and
  `may_store`, covering RFC 9111 section 4.2, RFC 5861 and request directives.
- Targeted fields (RFC 9213): `parse_targeted`, `build_targeted` and `select`, on a
  structured field dictionary parser checked against the httpwg test corpus.
- `REGISTERED_DIRECTIVES`, `REQUEST_DIRECTIVES`, `RESPONSE_DIRECTIVES`, `DELTA_MAX`,
  `CacheControl.duplicates`, `extensions()`, `has()`, `seconds()`, `no_cache_fields` and
  `private_fields`.
- A `ccdirectives` command that prints the policy of a header value or a response head.

### Fixed

- delta-seconds accept ASCII digits only (no sign, underscore or other digits) and values
  above 2147483648 become 2147483648.
- The first occurrence of a repeated directive wins instead of the last.
- `no-cache=""` and `private=""` count as present; a bare `max-stale` reads as unlimited.
- An unterminated quote no longer swallows the directives after it.
- CR, LF and NUL in a value become spaces; names fold ASCII letters only.
- `build` refuses names that are not tokens, control characters, non-ASCII text, negative
  numbers and malformed delta-seconds, and writes field lists in quoted-string form.

## [0.1.0]

- Parse a Cache-Control header into a typed, case-insensitive `CacheControl` structure.
- Build a header string back from a `CacheControl`, quoting and escaping arguments when needed.
- Typed accessors for the common directives, with unknown directives preserved verbatim.
