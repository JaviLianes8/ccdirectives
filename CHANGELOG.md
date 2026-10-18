# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-17

The public API is now stable: the seventeen names in `__all__`, their signatures and
defaults, the error types and the command line options are kept for the 1.x series.
Results on valid input are the same as in 0.2.0, except for the two corrections listed
under Fixed.

### Added

- `CacheControl.keys()` and `values()`, so `dict(cc)` copies the directives.

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
- Public names report `ccdirectives` as their module; the stray `annotations` attribute is
  gone from the package.
- Command line: `--age` takes ASCII digits only (no sign, underscore or other digits);
  on POSIX an argument is read as the octets it was given, like standard input; a closed
  output (also a stream object closed in the calling process) exits 1 without a traceback,
  an interrupt exits 130, a closed standard input is a
  usage error; folded header lines are joined in linear time.
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

## [0.2.0]

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
