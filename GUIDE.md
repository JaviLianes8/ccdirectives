# ccdirectives guide

The README shows the common calls. This guide is the reference: what every public name
does, which input it refuses and with which error, how the command line behaves, how the
results compare with other libraries, and what changed from 0.2.0.

## Reading a field: `parse`

`parse(header, *, strict=False, context=None)` takes one field value, or several field
lines as an iterable of `str` (joined with `", "`, as RFC 9110 section 5.3 combines them),
and returns a `CacheControl`.

- Names keep their spelling except that ASCII letters are lower-cased; other letters are
  never folded, so a look-alike such as the Kelvin sign does not turn into `k`.
- The first occurrence of a repeated directive wins (RFC 9111 section 4.2.1) and the name
  is listed in `duplicates`.
- The arguments of the delta-seconds directives (`max-age`, `s-maxage`, `max-stale`,
  `min-fresh`, `stale-while-revalidate`, `stale-if-error`) become `int` when they are
  ASCII digits, in token or quoted form; anything larger than 2147483648 is read as
  2147483648 (section 1.2.2). Other arguments stay text, unescaped.
- A bare directive is `True`; a bare `max-stale` reads as 2147483648 (any staleness).

The lenient default never raises on content. CR, LF and NUL become spaces (RFC 9110
section 5.5), an unterminated quoted string keeps the directives after it, and a name
followed by junk is kept bare, so `no-store; private` still says `no-store`.

`strict=True` checks what a recipient must accept and raises `CacheControlError` at the
first problem, with the offset into the (joined) value. `context="request"` or
`"response"` applies the argument rules of that direction; a registered name of the other
direction is then an extension. Without a context the more permissive rule of the two is
used. Strict mode accepts `max-age="60"` and `no-cache=ETag`: a sender must not write
them, but a recipient has to read them.

| Reason | When |
| --- | --- |
| `control character in the field value` | a control other than HTAB, or DEL |
| `expected a directive name` | a separator or other text where a name should start |
| `whitespace before '='`, `whitespace after '='` | `max-age = 5` |
| `expected a token or a quoted string after '='` | `max-age=` |
| `expected ',' after a directive` | `max-age=5 6`, `no-store;` |
| `character not allowed in a quoted string` | a character above U+00FF inside quotes |
| `character not allowed after a backslash` | a character above U+00FF after a backslash |
| `unterminated quoted string` | no closing quote (offset of the opening one) |
| `repeated directive 'NAME'` | the second occurrence |
| `'NAME' takes no argument` | `no-store=1`, `immutable=1` |
| `'NAME' needs delta-seconds` | a bare `max-age` |
| `'NAME' argument is not delta-seconds` | `max-age=-1`, `max-age=1.5` |
| `'NAME' argument is not a list of field names` | `private="a b"` |

## The structure: `CacheControl`

`CacheControl(directives={}, duplicates=frozenset())` is an ordered mapping from name to
`DirectiveValue` (`int`, `str` or `bool`). Construction lower-cases the ASCII letters of
every name, keeps the first of two names that fold together and adds it to
`duplicates`, and stores plain `int`, `str` and `bool` values (subclasses are converted, so
their methods cannot change what `build` writes). `False` means absent. Two structures
are equal when they hold the same names, values and duplicates, in any order.

- Item access, `in`, `len`, iteration, `get`, `keys`, `values`, `items`, assignment and
  `del` ignore case; `dict(cc)` copies the directives.
- `has(name)` is true for any value but `False`; `seconds(name)` reads delta-seconds.
- `extensions(context=None)` lists the names outside the registry, or outside the request
  or response set.
- Properties: `max_age`, `s_maxage`, `min_fresh`, `max_stale`, `stale_while_revalidate`,
  `stale_if_error` (`int` or None); `no_cache`, `private`, `no_store`, `no_transform`,
  `only_if_cached`, `must_revalidate`, `proxy_revalidate`, `must_understand`, `public`,
  `immutable` (`bool`); `no_cache_fields`, `private_fields` (lower-cased names).

Names must be `str` (`TypeError` otherwise), except that `in` answers False for anything
that is not a `str`; values of another type raise `TypeError`.

## Writing a field: `build`

`build(cache_control)` writes the directives as a field value that `parse(strict=True)`
always accepts. delta-seconds go out as tokens (capped at 2147483648, leading zeros
dropped), `no-cache` and `private` lists as quoted strings, other text as a token when it
is one and quoted otherwise. It raises `CacheControlError` for a name that is not a token,
a negative number, a missing or non-numeric delta-seconds, an argument on a registered
directive that takes none, a control character or non-ASCII text, a field list that is
not one, and an extension integer too large for the interpreter to write as text (past
4300 digits by default). Messages show at most 40
characters of the name and never the value.

## Targeted fields

`parse_targeted(value)` reads a field such as `CDN-Cache-Control` as a structured field
Dictionary (RFC 9651) and returns None for an empty or invalid field, which RFC 9213 says
to ignore. Booleans, Integers, Strings and Tokens map to directive values; parameters are
ignored; a member that breaks its directive's rules (a Decimal `max-age`, a String
`s-maxage`) is left out, except that a restrictive directive (`no-store`, `no-cache`,
`private`, `must-revalidate`, `proxy-revalidate`, `no-transform`) is kept bare so a cache
never loosens a policy. A repeated key keeps the last value, as Dictionaries do.

`build_targeted(cache_control)` applies the rules of `build` and writes a Dictionary; an
extension integer may have at most 15 digits there, the limit of a structured field
Integer (delta-seconds are capped at 2147483648 first). A list of pairs given to
`select` must hold tuples or lists of two (`TypeError` otherwise).
`select(headers, targets=("CDN-Cache-Control",))` takes a mapping, a header object with
`items()` or a list of pairs, and returns the first target field with a valid, non-empty
value, or `"Cache-Control"` parsed leniently.

## Freshness

- `freshness_lifetime(response, *, shared=False, expires=None, date=None)`: `s-maxage`
  for a shared cache, then `max-age`, then `expires - date` (seconds since the epoch),
  else None. A present but invalid directive gives 0. No heuristic lifetime is applied.
- `current_age(*, date_value, request_time, response_time, now, age_value=0)`: the
  calculation of RFC 9111 section 4.2.3, rounded up.
- `assess(response, *, age, shared=False, request=None, expires=None, date=None)` returns
  `Freshness(lifetime, age, fresh, reusable, stale_while_revalidate, stale_if_error)` and
  its `staleness`. A `no-cache` response, qualified or not, is never reusable without
  validation; this is stricter than a cache that strips the listed fields.
- `may_store(response, *, shared=False, authorized=False, understood_status=False)`
  judges the directives only (RFC 9111 sections 3 and 3.5).

Times must be finite `int` or `float` values (`ValueError` for NaN, infinities and an
`int` beyond the range of a float, `TypeError` for `bool` and other types); ages are
non-negative `int`. An `age` or `age_value` past 2147483648 is read as 2147483648 before
any calculation, every lifetime and age returned is at most 2147483648, and a
calculation that overflows gives 2147483648. The flags
must be `bool`. `response` and `request` must be `CacheControl` (`TypeError`).

## Command line

`ccdirectives [--strict] [--shared] [--age SECONDS] [--target FIELD]... [VALUE]` prints
the chosen field, its directives and the verdict as JSON (ASCII only). Without VALUE it
reads standard input as octets (ISO-8859-1): a response head (the last one of a `curl -sI`
dump) or a bare value. From a head it takes `Age`, and `Expires` and `Date` when
`Cache-Control` applies; an `Expires` that does not parse means already expired. On POSIX
an argument is read as the octets it was given, like standard input. `--strict` checks a
response head with the response rules; a VALUE or a bare value on standard input has no
known direction, so it is checked with the more permissive rule of the two (a request
directive with an argument it never takes, such as `only-if-cached=1`, is still refused
there, while a head treats it as a response extension).

Exit status: 0 printed, 1 rejected by `--strict` or an output that closed or failed, 2 a
usage error (including a `--age` that is not ASCII digits and a closed standard input),
130 interrupted. Messages go to standard error and are dropped when it is closed.

## Compared with other libraries

`tests/test_oracle.py` runs 1,000 seeded well-formed headers through Werkzeug 3.1.9,
hishel 1.4.0 and CacheControl 0.14.4 (answers recorded by `scripts/oracle_fixture.py`,
rerun live when those versions are installed). They agree on every name, value, field list
and extension, on hishel's freshness lifetime and stale rule, with these differences:

- hishel reads a bare `max-stale`, and any delta-seconds past its cap, as 2147483647;
  RFC 9111 section 1.2.2 names 2147483648. It title-cases listed field names.
- CacheControl reads a bare `max-stale` as None and splits the value at every comma, so
  a quoted list is not read as one.
- hishel and Werkzeug keep the last of a repeated directive; this library keeps the first.

`tests/test_examples.py` runs every assertion of hishel's own parser tests against this
library with those differences, plus Werkzeug's Cache-Control test and the two values the
WHATWG Fetch Standard sends for its cache modes.

## Sources

`scripts/fetch_upstream.py` downloads RFC 9111, 9110, 5861, 8246, 9213 and 9651, the IANA
cache directive registry, the httpwg structured field tests, the Fetch Standard source and
the Werkzeug and hishel test files into the git-ignored `tests/upstream/`, checked against
`tests/upstream/MANIFEST.json`. Their tests skip while the files are absent; none of them
is part of the repository or the packages.

## Upgrading from 0.2.0

Results on valid input are unchanged. What changed is listed under 1.0.0 in
[CHANGELOG.md](https://github.com/JaviLianes8/ccdirectives/blob/main/CHANGELOG.md): option
flags must be `bool`, arguments of the wrong type raise `TypeError`, times must be finite,
overflowing calculations give 2147483648, messages are bounded, subclasses are read as
plain values, and the command line handles closed streams and reads `--age` as
delta-seconds.
