# ccdirectives guide

The README shows the common calls. This guide is the reference: what every public name
does, which input it refuses and with which error, how the command line behaves, how the
results compare with other libraries, and what changed from 0.2.0.

## Reading a field: `parse`

`parse(header, *, strict=False, context=None)` takes one field value, or several field
lines as an iterable of `str` (joined with `", "`, as RFC 9110 section 5.3 combines them),
and returns a `CacheControl`. It raises `TypeError` for `bytes` (decode them first, as
ISO-8859-1 keeps every octet), for a header that is neither a `str` nor iterable and for a
line that is not a `str`, and `ValueError` for a `context` other than `"request"`,
`"response"` or None, in lenient mode too.

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

`strict=True` checks what a recipient must accept, with two exceptions: it reports an
argument on `immutable`, which RFC 8246 says to ignore, and every repeated directive, where
RFC 9111 section 4.2.1 lets a recipient use the first (and RFC 8246 reads a repeated
`immutable` as one). It raises `CacheControlError` at the
first problem, with the offset into the (joined) value. `context="request"` or
`"response"` applies the argument rules of that direction; a registered name of the other
direction is then an extension. Without a context the more permissive rule of the two is
used. Strict mode accepts `max-age="60"` and `no-cache=ETag`: a sender must not write
the first and should not write the second, but a recipient has to read both.

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
their methods cannot change what `build` writes). `False` means absent: construction
leaves such a name out (it is not an occurrence, so it is never a duplicate), assigning
`False` removes the name. A `False` placed directly in `directives` is stored, but it
still means absent to `build`, `build_targeted`, equality, `has()` and the properties;
`in`, `len`, iteration, `keys`, `values`, `items`, `get`, `dict(cc)` and `extensions()`
read the stored dict and still see it. Two structures
are equal when they hold the same names, values of the same type and duplicates, in any
order: unlike in a `dict`, `0` and `False` (`max-age=0` against no `max-age`) and `1` and
`True` differ. A structure is never equal to an object of another type, and comparing one
whose `directives` were edited to hold a value of another type raises `TypeError`.

- Item access, `in`, `len`, iteration, `get`, `keys`, `values`, `items`, assignment and
  `del` ignore case; `dict(cc)` copies the directives.
- `has(name)` is true for any stored value but `False`; `seconds(name)` reads delta-seconds.
- `extensions(context=None)` lists the names outside the registry, or outside the request
  or response set.
- Properties: `max_age`, `s_maxage`, `min_fresh`, `max_stale`, `stale_while_revalidate`,
  `stale_if_error` (`int` or None); `no_cache`, `private`, `no_store`, `no_transform`,
  `only_if_cached`, `must_revalidate`, `proxy_revalidate`, `must_understand`, `public`,
  `immutable` (`bool`); `no_cache_fields`, `private_fields` (lower-cased names). Each has
  a docstring with an example.

Types are checked on the real type of a value, so an object whose `__class__` claims
another type is refused, and values placed directly in `directives` are read as plain
values. A missing name raises `KeyError` with the name cut to 40 characters. Names must
be `str` (`TypeError` otherwise), except that `in` answers False for anything
that is not a `str`; values of another type raise `TypeError`.

## Writing a field: `build`

`build(cache_control)` writes the directives as a field value that `parse(strict=True)`
always accepts. delta-seconds go out as tokens (capped at 2147483648, leading zeros
dropped), `no-cache` and `private` lists as quoted strings, other text as a token when it
is one and quoted otherwise. It raises `CacheControlError` for a name that is not a token,
a negative number, a missing or non-numeric delta-seconds, an argument on a registered
directive that takes none, a control character or non-ASCII text, a `no-cache` or
`private` argument that is not a list of field names (a number included: the structure
reads `private=5` as bare `private`, a parser as a list naming field `5`), and an extension integer too large for the interpreter to write as text (past
4300 digits by default). Messages show at most 40
characters of the name and never the value.

## Targeted fields

`parse_targeted(value)` reads a field such as `CDN-Cache-Control` as a structured field
Dictionary (RFC 9651) and returns None for an empty or invalid field, which RFC 9213 says
to ignore. Booleans, Integers, Strings and Tokens map to directive values; parameters are
ignored; a member that breaks its directive's rules (a Decimal `max-age`, a String
`s-maxage`) is left out, except that a restrictive directive (`no-store`, `no-cache`,
`private`, `must-revalidate`, `proxy-revalidate`, `no-transform`, and `s-maxage`, which
forbids stale use in a shared cache) is kept bare so a cache never loosens a policy; a
bare `s-maxage` gives a shared cache a lifetime of 0, as an invalid one does in
`Cache-Control`. A repeated key keeps the last value, as Dictionaries do.

`build_targeted(cache_control)` applies the rules of `build` and writes a Dictionary; an
extension integer may have at most 15 digits there, the limit of a structured field
Integer (delta-seconds are capped at 2147483648 first). A list of pairs given to
`select` must hold tuples or lists of two (`TypeError` otherwise), and both are in its
type. Headers or targets that are not iterable raise `TypeError`, with the type name cut
to 40 characters.
`select(headers, targets=("CDN-Cache-Control",))` takes a mapping, a header object with
`items()` or a list of pairs, and returns the first field in the order of `targets` with a
valid, non-empty value, or `"Cache-Control"` parsed leniently.

## Freshness

- `freshness_lifetime(response, *, shared=False, expires=None, date=None)`: `s-maxage`
  for a shared cache, then `max-age`, then `expires - date` (seconds since the epoch)
  rounded down to whole seconds, else None. `expires` without `date` raises `ValueError`
  (pass the time the response was received when it has no Date); `assess` does the same.
  A present but invalid directive gives 0. No heuristic lifetime is applied.
- `current_age(*, date_value, request_time, response_time, now, age_value=0)`: the
  calculation of RFC 9111 section 4.2.3, rounded up.
- `assess(response, *, age, shared=False, request=None, expires=None, date=None)` returns
  `Freshness(lifetime, age, fresh, reusable, stale_while_revalidate, stale_if_error)` and
  its `staleness`. A `no-cache` response, qualified or not, is never reusable without
  validation; this is stricter than a cache that strips the listed fields. `min-fresh`
  only judges a fresh response; a stale one is judged by `max-stale`. A request
  `stale-if-error` replaces the response's for that request (RFC 5861 section 4 scopes
  it to the request; the precedence is this library's reading).
- `may_store(response, *, shared=False, authorized=False, understood_status=False)`
  judges the refusals of RFC 9111 sections 3 and 3.5: `no-store` (unless
  `must-understand` with a status the cache understands), unqualified `private` for a
  shared cache (an empty list counts as unqualified, as section 5.2.2.7 qualifies it only
  with one or more field names), and Authorization for a shared cache. The method, the
  status and the last condition of section 3 (an explicit lifetime, `public`, `private`,
  an extension or a heuristically cacheable status) stay with the caller.

Times must be finite `int` or `float` values (`ValueError` for NaN, infinities and an
`int` beyond the range of a float, `TypeError` for `bool` and other types); ages are
non-negative `int`. An `age` or `age_value` past 2147483648 is read as 2147483648 before
any calculation, every lifetime and age returned is at most 2147483648, and a
calculation that overflows gives 2147483648. The arithmetic is exact: ints and floats are
combined without rounding. The flags
must be `bool`. `response` and `request` must be `CacheControl` (`TypeError`).

## Command line

`ccdirectives [--strict] [--shared] [--age SECONDS] [--target FIELD]... [VALUE]` prints
the chosen field, its directives and the verdict as JSON (ASCII only). Without VALUE it
reads standard input as octets (ISO-8859-1): a response head (the last one of a `curl -sI`
dump) or a bare value. From a head it takes `Age` (all `Age` lines form one list, empty
members do not count, and the first other member is used, as RFC 9111 section 5.1 asks;
spaces and tabs around it are the only whitespace allowed), and
`Expires` and `Date` when `Cache-Control` applies. Dates are read in the three formats
of RFC 9110 section 5.6.7, all as UTC: IMF-fixdate and RFC 850 dates must say `GMT` (a
date in another zone is invalid, as RFC 9111 section 4.2 asks for expiration), a
four-digit year is read as written, and a two-digit RFC 850 year gives the latest instant
with those digits that is at most 50 years after the current time (one more than 50
years ahead is moved 100 years back). Day and month names and `GMT` ignore case (ASCII
only); the day name must be a real one, long in RFC 850 dates and short in the others, but
is not checked against the date. Second 60 (a leap second) is read as the next second. An `Expires` that does not parse means
already expired, and a `Date` that does not parse is replaced by the current time. Field names compare
case-insensitively, the head ends at the first empty line, folded lines join their field
with a space, and a line whose name has whitespace before the colon is skipped together
with its folded lines. On POSIX an argument is read as the octets it was given, like
standard input. `--strict` checks a response head with the response rules; a VALUE or a
bare value on standard input has no known direction, so it is checked with the more
permissive rule of the two (a request directive with an argument it never takes, such as
`only-if-cached=1`, is still refused there, while a head treats it as a response
extension).

Exit status: 0 printed (also the help of `--help`), 1 rejected by `--strict` or an output
that closed or failed (also while writing the help), 2 a usage error (including a `--age`
that is not ASCII digits and a closed standard input), 130 interrupted. Messages go to
standard error and are dropped when it is closed; a usage error shows at most 200
characters of the problem.

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

Those headers are lower case, without repeats, in token form and under 2^31 - 1. On other
input the libraries also differ in these ways: CacheControl keeps the last of a repeated
directive, ignores quoted delta-seconds (`max-age="60"`), does not cap large values and
does not match upper-case names; hishel keeps every occurrence of a repeated extension;
Werkzeug keeps the case of names. This library folds names to lower case, reads both
argument forms and caps at 2147483648.

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

Results on valid input are unchanged, with three exceptions besides the fixes: ages and
lifetimes are capped at 2147483648, the time arithmetic is exact, and equality tells `0`
from `False`. The 1.0.0 section of
[CHANGELOG.md](https://github.com/JaviLianes8/ccdirectives/blob/main/CHANGELOG.md) lists
every change: option flags must be `bool`, arguments of the wrong type raise `TypeError`,
times must be finite, overflowing calculations give 2147483648, messages are bounded,
subclasses are read as plain values, and the command line handles closed streams, bounds
usage errors and reads `--age` as delta-seconds.
