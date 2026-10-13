# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
