# ccdirectives improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [x] Pin the ground truth: RFC 9111, RFC 9110, RFC 5861, RFC 8246, RFC 9213, RFC 9651, IANA registry, structured field test corpus
- [x] Grammar-driven parser: `#cache-directive`, delta-seconds, first occurrence wins, duplicates reported
- [x] Strict mode with `CacheControlError` offsets
- [x] Directive registry: request and response sets, argument rules
- [x] Safe builder: token names, header injection guard, token and quoted forms per directive
- [x] Freshness helpers: lifetime, age, reuse, stale-while-revalidate, stale-if-error, request limits
- [x] Targeted fields: structured field dictionary parser and serializer, target list selection
- [x] Command line
- [ ] Contracts: pinned sources, README examples, typing, installed wheel
- [x] Docs and packaging: README, CHANGELOG, metadata, sdist contents
- [ ] Gates: ruff format, ruff check, mypy --strict, pytest
- [ ] Mutation run: removing guarded logic makes the suite fail
- [ ] Independent review findings fixed with regression tests
- [ ] Pull request opened, guard clean

## Starting point

`0.1.0` gives `parse`, `build` and a `CacheControl` mapping with typed accessors.
Probed against the sources below:

- delta-seconds is read with `int()`, so `max-age=-5` gives `-5`, `max-age=1_0` gives 10,
  `max-age=+7` gives 7 and a fullwidth digit is accepted. RFC 9111 section 1.2.2 allows
  only `1*DIGIT`, and a value too large to represent has to become 2147483648; today
  `max-age=99999999999` is returned unchanged.
- A repeated directive keeps the last value. Section 4.2.1 says the first occurrence is
  used (or the response is treated as stale); `max-age=60, max-age=5` gives 5.
- `no-cache=""` and `private=""` report `False`, although the directive is present.
- A bare `max-stale` (any staleness accepted, section 5.2.1.2) reads as `None`, the same as
  an absent one.
- An unterminated quote swallows every directive after it: in
  `private="a", x="unterminated, no-store` the `no-store` is lost.
- CR and LF are kept inside values instead of being refused or replaced by SP (RFC 9110
  section 5.5). Names are lower-cased with Unicode rules, so `MAX-AGE` followed by the Kelvin
  sign becomes `max-agek`.
- `build` writes anything: a CR LF in a value injects a header, a name with a space is
  copied, `max-age=-3` is written, and `private` field lists go out in token form although
  section 5.2.2.7 says senders SHOULD NOT use it.
- No strict mode, no request or response view, no freshness calculation, and no support
  for `CDN-Cache-Control`, which RFC 9213 defines as a structured field dictionary with
  different error handling.

## Sources (fetched 2026-10-13)

- RFC 9111, https://www.rfc-editor.org/rfc/rfc9111.txt: delta-seconds and the 2147483648
  cap (1.2.2), freshness (4.2), lifetime and duplicates (4.2.1), age (4.2.3), serving
  stale (4.2.4), the grammar and the directives (5.2), extensions (5.2.3). Errata page
  https://www.rfc-editor.org/errata/rfc9111 read: two reported technical errata (9004 on
  section 3.5, 9185 on section 4.3.4), neither verified and neither about directive syntax.
- RFC 9110, https://www.rfc-editor.org/rfc/rfc9110.txt: field order and combining lines
  (5.3), field values and CR, LF, NUL (5.5), lists and empty elements (5.6.1), token (5.6.2),
  whitespace (5.6.3), quoted-string (5.6.4).
- RFC 5861, https://www.rfc-editor.org/rfc/rfc5861.txt: stale-while-revalidate (3) and
  stale-if-error (4), with the worked examples of 3.1 and 4.1. Errata 2255 and 2256 are
  editorial (terminology only).
- RFC 8246, https://www.rfc-editor.org/rfc/rfc8246.txt: immutable takes no argument, an
  argument is ignored, repeats count once, no effect in a request (2).
- RFC 9213, https://www.rfc-editor.org/rfc/rfc9213.txt: targeted fields are structured
  field dictionaries, value mapping and error handling (2.1), target lists and fallback
  (2.2), the CDN-Cache-Control examples (3.1). No errata.
- RFC 9651, https://www.rfc-editor.org/rfc/rfc9651.txt: dictionary, item and bare item
  parsing (4.2) and serialization (4.1).
- IANA HTTP Cache Directive Registry,
  https://www.iana.org/assignments/http-cache-directives/cache-directives.csv (registry
  last updated 2022-06-08, 16 names).
- Structured field test corpus, httpwg/structured-field-tests at commit
  781ba38464b2ec4c547e1e14d007d4f5ace7457e (dictionary, parameter, key, item and example
  files).
- None of these files is committed. `tests/upstream/MANIFEST.json` records URL, revision,
  size, sha256 and licence, `scripts/fetch_upstream.py` fetches and checks them into the
  ignored `tests/upstream/` folder, and their tests skip while they are absent.

## Ranked improvements

1. **Correct delta-seconds.** ASCII digits only, values above 2147483648 become
   2147483648, quoted digits accepted on input (section 5.2 asks recipients to take both
   forms). Invalid values stay visible as text and count as stale for freshness.
2. **Grammar-driven parser.** A scanner on `#cache-directive`: token names compared
   ASCII case-insensitively, token or quoted-string arguments, empty list elements ignored,
   several field lines accepted, the first occurrence of a directive wins and repeated names
   are reported in `duplicates`. A broken quote resyncs at the next comma. CR, LF and NUL
   become SP. `bytes` gets a clear `TypeError`.
3. **Strict mode.** `parse(h, strict=True)` raises `CacheControlError` (a `ValueError`)
   with the offset for syntax outside the grammar, control characters, repeated directives,
   missing or malformed delta-seconds, arguments on directives that take none, and
   `no-cache` or `private` arguments that are not field-name lists. A `context` of
   `"request"` or `"response"` applies the rules of that direction.
4. **Freshness helpers.** `freshness_lifetime` (s-maxage for shared caches, max-age,
   Expires minus Date), `current_age` (section 4.2.3) and `assess`, which says whether a
   stored response is fresh, reusable for a given request (max-age, min-fresh, max-stale,
   no-cache), usable while revalidating in the background, or usable on error, with
   no-cache, must-revalidate, proxy-revalidate and s-maxage blocking stale use.
5. **Targeted cache control.** A structured field dictionary parser and serializer on RFC
   9651 section 4, checked against the httpwg corpus; `parse_targeted` maps members to
   directive values per RFC 9213 section 2.1 and ignores a field that is empty or fails to
   parse; `select` walks a target list and falls back on `Cache-Control`.
6. **Safe builder.** Refuses names that are not tokens, control characters and non-ASCII
   text, negative numbers and non-numeric delta-seconds; writes delta-seconds as tokens and
   `no-cache` and `private` field lists as quoted strings. `parse(build(cc), strict=True) == cc`
   holds for any normalised structure (delta-seconds as ints up to 2^31, extension
   arguments as text, no duplicates).
7. **Typed API.** Registry sets (`REQUEST_DIRECTIVES`, `RESPONSE_DIRECTIVES`), field list
   accessors (`no_cache_fields`, `private_fields`), `max_stale` reading a bare directive as
   unlimited, `extensions()` for names outside the registry, frozen result types.
8. **Command line.** `ccdirectives` reads a header value or a `curl -sI` dump and prints
   the chosen field, its directives and the freshness lifetime as JSON. It fits: checking
   what a CDN will do with a response is a shell task.
9. **Contracts.** RFC examples, the IANA names and the structured field corpus are read from
   the pinned files; README examples run; types are checked with mypy; the installed wheel
   and its console script are driven from an empty folder.
10. **Docs and packaging.** README with executed examples and an API table, CHANGELOG,
    keywords and classifiers, sdist without planning notes or fetched files.

## Out of scope

- HTTP-date parsing for Expires and Date: callers pass seconds, so the library needs no
  clock and no date parser of its own.
- Heuristic freshness (section 4.2.2): the fraction is a cache policy, not a rule.
- Pragma and Warning: obsolete or not about directives.
- Structured field lists and items at the top level: targeted fields are dictionaries only.
