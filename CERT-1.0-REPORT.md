# ccdirectives 1.0.0 certification report

Progress:
- [x] Branch `release/1.0.0` created from `main` (0.2.0, d76796f; PyPI has 0.2.0)
- [x] Baseline gates run on 0.2.0
- [x] API review and 1.0.0 API changes (item 1)
- [x] Real ground truth: fetched sources and live reference parsers (item 7)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e and upgrade from PyPI 0.2.0 (items 8, 10, 13, 14), author run
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)
- [ ] Gates (item 15), final run
- [ ] PR and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Baseline on 0.2.0 (before any change)

Clone of `main` (d76796f) on this PC, CPython 3.13.2, references fetched by
`scripts/fetch_upstream.py`: `ruff format --check .`, `ruff check .` and
`mypy --strict src tests` exit 0; `pytest` 206 passed, 1 skipped (the opt-in wheel test).
PyPI has 0.2.0 only.

Defects of 0.2.0 found by the API review, each probed on the real 0.2.0 from PyPI (the
upgrade test checks them):

- An `int` subclass whose `__str__` returned `"1\r\nX: y"` was written by `build` as
  `max-age=1\r\nX: y`: a header injection through a value the type checks accepted.
- `strict`, `shared`, `authorized` and `understood_status` used the truth value of
  anything: `strict="no"` and `shared=1` were accepted.
- `current_age` raised `OverflowError` for an infinite time and an unrelated `ValueError`
  for NaN; `freshness_lifetime` did the same through `expires` and `date`, and returned
  integers of hundreds of digits for extreme finite times.
- `CacheControl.get(1)`, `has(1)` and item access with a non-string name raised
  `AttributeError`; `build`, `assess` and the other functions given a plain dict raised
  `AttributeError` from inside.
- Error messages repeated the input: a 100,000-character name or value gave a
  100,000-character message, an unknown `context` was echoed whole.
- `build` of an extension integer of more than 4,300 digits raised the interpreter's own
  `ValueError` about integer string conversion.
- Public names reported private modules (`ccdirectives._parse`) and the package exposed a
  stray `annotations` attribute.
- Command line: `--age` accepted `1_0` and other digits through `int()`; a closed output
  (`| head`) or an interrupt gave a traceback; on POSIX an argument was read as file
  system text while standard input was read as octets; folded header lines were joined
  in quadratic time.
- The sdist took every file not ignored by git; the README linked LICENSE relatively
  (broken on PyPI) and there was no guide.

## API review (item 1)

Kept from 0.2.0 with the same names, signatures, defaults and results on valid input: all
seventeen public names. `tests/test_contract_api.py` freezes every signature, the module of
every public name, the methods and typed properties of `CacheControl`, pickling and the
flag type checks; `tests/test_contract_types.py` pins the `TypeError` of every wrong
argument. Changed, all in CHANGELOG 1.0.0: flags must be `bool`; names and structures of
the wrong type raise `TypeError`; values are stored as plain `int`, `str` and `bool`;
times must be finite and overflowing calculations give 2147483648; messages are bounded
and never repeat a value; `build` raises `CacheControlError` for a huge extension integer;
`duplicates` takes any iterable of names but not a string; public names report
`ccdirectives`; the command line reads `--age` as delta-seconds, reads POSIX arguments as
octets and handles closed streams and interrupts. Considered and kept: the first
occurrence of a repeated directive wins (RFC 9111 section 4.2.1, where hishel and
Werkzeug keep the last); a qualified `no-cache` still blocks reuse without validation
(documented as stricter than needed); `CacheControl` stays a dataclass with mapping
methods rather than a `MutableMapping`, so its `isinstance` behaviour does not change.

## Ground truth (item 7)

`scripts/fetch_upstream.py` downloads 25 sources into the git-ignored `tests/upstream/`
and checks them against `tests/upstream/MANIFEST.json` (URL, revision, date, size,
SHA-256, licence): RFC 9111, 9110, 5861, 8246, 9213 and 9651, the IANA HTTP Cache
Directive Registry, the httpwg structured field test corpus at a pinned commit, the WHATWG
Fetch Standard source at a pinned commit, Werkzeug 3.1.9's `tests/test_http.py` and hishel
1.4.0's `tests/_core/test_headers.py` (the last three fetched 2026-10-17). The live IANA
CSV no longer matched the 2026-10-13 hash: the registry now writes "RFC 9111" where it
wrote "RFC9111"; the sixteen names are the same and the manifest entry was refreshed.
Nothing fetched is committed or shipped.

- `tests/test_sources.py` (from 0.2.0): the registry equals the IANA names, the request
  and response sets follow RFC 9111 sections 5.2.1 and 5.2.2, `DELTA_MAX` is the value of
  section 1.2.2, tchar and qdtext match RFC 9110, and the examples of RFC 9110, 9111, 5861,
  8246 and 9213 parse as their text says.
- `tests/test_sources_rules.py`: the argument rule of every directive in each direction
  (none, delta-seconds, optional delta-seconds, field list, ignored) is derived from the
  fetched RFC 9111, 5861 and 8246 text and equals the registry; strict mode accepts and
  refuses exactly what each derived rule says.
- `tests/test_sf_corpus.py` (from 0.2.0): the structured field parser against the httpwg
  corpus.
- `tests/test_examples.py`: every assertion of hishel's own parser tests (over 80 headers)
  is read from the fetched file with `ast` and holds for this library, with the
  differences GUIDE.md lists (cap 2^31 against 2^31 - 1, first against last occurrence,
  lower-case against title-case field names); Werkzeug's Cache-Control test; the two
  values the Fetch Standard appends for its cache modes parse strictly as request
  directives.
- `tests/test_oracle.py` with `tests/fixtures/oracle_runs.json` (program output recorded
  by `scripts/oracle_fixture.py`, CPython 3.13.2, Werkzeug 3.1.9, hishel 1.4.0,
  CacheControl 0.14.4; 1,000 seeded well-formed headers): Werkzeug's `parse_dict_header`
  gives the same names and unescaped values; hishel's `parse_cache_control` the same
  numbers, flags, field lists and extensions, its `get_freshness_lifetime` the same
  lifetime for private and shared caches and its `allowed_stale` the same stale rule;
  CacheControl's `parse_cache_control` the same known directives and numbers. The three
  libraries are rerun live when the pinned versions are installed (they are in the dev
  extras).

## Errors, typing, docs (items 2 to 5)

- `__all__` lists the seventeen public names; `tests/test_contract.py` and
  `test_contract_api.py` pin it and that nothing else is public.
- Every public class and function has a runnable docstring example and the package
  docstring shows the four constants and `DirectiveValue`;
  `test_every_public_name_has_a_passing_example` runs them (over 40 examples). Every
  README example runs and prints what its comment says (`tests/test_docs.py`); every
  strict reason in the GUIDE table is one the code raises.
- `mypy --strict src tests scripts` clean; `py.typed` shipped; `tests/test_typing.py`
  checks what mypy infers for a consumer and what it rejects. No `Any` in the public API.
- Errors: GUIDE.md lists every `CacheControlError` reason, every `TypeError` and
  `ValueError`; messages show at most 40 characters of a name, never a value or an unknown
  context; type names are cut to 40 characters and read from the type slot, so a
  metaclass cannot replace them (`tests/test_contract_hostile.py`).

## Contracts, fuzz and mutations (items 6, 9, 18)

New contract files: `test_contract_api.py`, `test_contract_types.py`,
`test_contract_hostile.py` (bounded messages, plain values from hostile subclasses,
finite times, overflow capping, linear time on ten 200,000-character hostile patterns
and on folded heads), `test_contract_cli.py` (real processes for every exit status,
octets in, closed and failing outputs, a reader that closes early),
`test_contract_install.py`, `test_contract_author.py`, `test_sources_rules.py`,
`test_examples.py`, `test_oracle.py`, `test_properties.py` (seeded freshness invariants,
monotonic age, any code point through every reader), `test_e2e_upgrade.py`. 308 tests in
all (306 by default, 2 opt-in).

Author mutation round: 82 mutations over every module, each applied alone to a fresh
clone of the pushed branch at 589f3f7 on Elena's PC (CPython 3.14.2, three auto:cpu
turns), suite with `-x`, no bytecode and a 300-second timeout, the two end-to-end modules
left out for time, file restored after; baseline green before each batch.

| Id | Module | Mutation | Caught by |
| --- | --- | --- | --- |
| C01 | `_chars` | token loses the vertical bar | `test_oracle::test_recorded_answers_match_with_the_documented_differences` |
| C02 | `_chars` | length shortcut off by one | `survived; equivalent (see below)` |
| C03 | `_chars` | delta-seconds not capped | `test_parse::test_delta_seconds_overflow_to_two_to_the_31` |
| C04 | `_chars` | unicode digits accepted | `test_contract_cli::test_exit_statuses_in_a_real_process[args5-2]` |
| C05 | `_chars` | qdtext drops HTAB | `test_build::test_tab_inside_an_argument_is_quoted` |
| C06 | `_chars` | qdtext takes any code point | `test_sources::test_quoted_string_characters_match_rfc_9110` |
| C07 | `_chars` | names folded with unicode rules | `test_parse::test_only_ascii_letters_fold` |
| C08 | `_chars` | empty list element refused | `test_model::test_field_lists_are_split_and_lower_cased` |
| S01 | `_scan` | space before = check off by one | `test_build::test_tab_inside_an_argument_is_quoted` |
| S02 | `_scan` | name before junk dropped | `test_parse::test_a_name_followed_by_junk_is_kept_bare` |
| S03 | `_scan` | unterminated quote argument lost | `test_parse::test_an_unterminated_quote_does_not_hide_later_directives` |
| S04 | `_scan` | junk after argument kept for quoted | `test_parse::test_delta_seconds_are_ascii_digits_only[\uff15]` |
| S05 | `_scan` | quoted-pair keeps the backslash | `test_examples::test_hishel_parser_tests_hold_with_the_documented_differences` |
| S06 | `_scan` | unterminated offset at the end | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[x="open-unterminated quoted string-2]` |
| S07 | `_scan` | trailing backslash reads past the end | `test_properties::test_any_code_point_is_parsed_without_surprises` |
| S08 | `_scan` | whitespace offset after the spaces | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[max-age= 60-whitespace after '='-8]` |
| P01 | `_parse` | last occurrence wins | `test_cli::test_a_value_on_the_command_line` |
| P02 | `_parse` | DEL allowed in strict mode | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[x="a\x7fb"-control character-4]` |
| P03 | `_parse` | NUL kept in lenient mode | `survived; then test_contract_author::test_nul_inside_a_value_becomes_a_space_in_lenient_mode` |
| P04 | `_parse` | bare max-age accepted | `test_oracle::test_recorded_answers_match_with_the_documented_differences` |
| P05 | `_parse` | immutable argument accepted strictly | `test_review_fixes::test_immutable_with_an_argument_is_not_generated` |
| P06 | `_parse` | lines joined without space | `survived; then test_contract_author::test_field_lines_are_joined_with_a_comma_and_a_space` |
| P07 | `_parse` | strict flag unchecked | `test_contract_api::test_flags_must_be_real_bools[None]` |
| P08 | `_parse` | quoted delta left as text only for unicode digits | `survived; equivalent (see below)` |
| R01 | `_registry` | max-stale needs an argument | `test_build::test_bare_max_stale_is_allowed` |
| R02 | `_registry` | stale-if-error not a request directive | `test_sources_rules::test_every_argument_rule_follows_the_rfcs` |
| R03 | `_registry` | strictest rule without context | `test_build::test_field_lists_are_always_quoted` |
| R04 | `_registry` | private not a field list | `test_build::test_field_lists_are_always_quoted` |
| B01 | `_build` | False written as present | `test_build::test_false_flag_is_omitted` |
| B02 | `_build` | minus one accepted | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives3-cannot be negative]` |
| B03 | `_build` | build does not cap | `test_build::test_delta_seconds_go_out_as_tokens` |
| B04 | `_build` | obs-text written | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives11-cannot carry]` |
| B05 | `_build` | arguments never quoted | `test_build::test_other_arguments_are_quoted_when_not_tokens` |
| B06 | `_build` | backslash not escaped | `test_build::test_quotes_and_backslashes_are_escaped` |
| B07 | `_build` | field lists in token form | `test_build::test_field_lists_are_always_quoted` |
| B08 | `_build` | huge int limit too high | `test_contract_hostile::test_a_huge_extension_integer_is_a_cache_control_error` |
| A01 | `_access` | has false for empty argument | `test_model::test_flags_are_true_for_any_present_value_but_false` |
| A03 | `_access` | bare max-stale not unlimited | `test_docs::test_every_readme_example_runs_and_prints_its_comment` |
| A04 | `_access` | seconds not capped | `test_model::test_seconds_rejects_flags_text_and_negative_numbers` |
| A05 | `_access` | s_maxage reads max-age | `test_examples::test_hishel_parser_tests_hold_with_the_documented_differences` |
| A06 | `_access` | private_fields reads no-cache | `test_contract_api::test_every_public_name_has_a_passing_example` |
| D01 | `_model` | constructor keeps the last | `test_contract_api::test_every_public_name_has_a_passing_example` |
| D02 | `_model` | int subclass kept | `test_contract_hostile::test_subclasses_are_read_as_their_plain_values` |
| D03 | `_model` | in is case-sensitive | `test_contract_hostile::test_subclasses_are_read_as_their_plain_values` |
| K01 | `_checks` | names not cut | `survived; then test_contract_author::test_a_long_name_is_cut_to_forty_characters_in_messages[41]` |
| K02 | `_checks` | int accepted as a flag | `test_contract_api::test_flags_must_be_real_bools[0]` |
| K03 | `_checks` | infinity accepted as a time | `test_contract_hostile::test_times_must_be_finite[nan]` |
| K04 | `_checks` | minus one second accepted | `test_fresh::test_negative_age_is_refused` |
| L01 | `_lifetime` | max-age before s-maxage | `test_cli::test_a_response_head_prefers_the_cdn_field_for_a_shared_cache` |
| L02 | `_lifetime` | invalid directive gives None | `test_fresh::test_invalid_freshness_information_counts_as_stale` |
| L03 | `_lifetime` | response delay ignored | `test_contract_api::test_every_public_name_has_a_passing_example` |
| L04 | `_lifetime` | age rounded down | `test_fresh::test_current_age_uses_the_more_conservative_estimate` |
| L05 | `_lifetime` | NaN not caught | `test_contract_hostile::test_overflowing_time_arithmetic_gives_two_to_the_31` |
| F01 | `_fresh` | fresh at the boundary | `test_fresh::test_fresh_and_reusable` |
| F02 | `_fresh` | request max-age boundary | `test_fresh::test_request_limits_narrow_reuse` |
| F03 | `_fresh` | min-fresh boundary | `test_fresh::test_request_limits_narrow_reuse` |
| F04 | `_fresh` | s-maxage does not forbid stale | `test_fresh::test_directives_that_forbid_stale_use[max-age=60, s-maxage=60-True]` |
| F05 | `_fresh` | request stale-if-error ignored | `test_fresh::test_request_stale_if_error_takes_precedence` |
| F06 | `_fresh` | request no-cache allows background revalidation | `test_fresh::test_stale_windows_apply_only_once_stale` |
| F07 | `_fresh` | private cache stores no-store | `test_fresh::test_may_store_follows_the_directives` |
| F08 | `_fresh` | must-revalidate does not allow authorized | `test_fresh::test_may_store_follows_the_directives` |
| T01 | `_targeted` | only no-store kept on a bad value | `test_targeted::test_restrictive_directives_survive_a_bad_value` |
| T02 | `_targeted` | negative max-age kept | `test_targeted::test_values_that_break_a_directive_rule_are_left_out` |
| T03 | `_targeted` | empty field not ignored | `test_targeted::test_an_empty_or_invalid_field_is_ignored[]` |
| T04 | `_targeted` | invalid target wins | `test_properties::test_any_code_point_is_parsed_without_surprises` |
| T05 | `_targeted` | token field list accepted | `test_targeted::test_restrictive_directives_survive_a_bad_value` |
| T06 | `_sf` | 16-digit integer accepted | `test_sf_corpus::test_the_corpus_file_parses_as_expected[date]` |
| T07 | `_sf` | escaped n accepted | `test_sf_corpus::test_the_corpus_file_parses_as_expected[string-generated]` |
| T08 | `_sfdict` | trailing comma accepted | `test_sf_corpus::test_the_corpus_file_parses_as_expected[dictionary]` |
| T09 | `_sfdict` | upper-case key written | `survived; then test_contract_author::test_build_targeted_refuses_a_key_that_is_not_lower_case_ascii[x-A]` |
| H01 | `_head` | first head used | `test_cli::test_a_response_head_prefers_the_cdn_field_for_a_shared_cache` |
| H02 | `_head` | Age field ignored | `test_contract_cli::test_standard_input_is_read_as_octets_in_a_real_process` |
| H03 | `_head` | space folding ignored | `test_review_fixes::test_the_command_line_reads_age_expires_and_folded_lines` |
| I01 | `_cli` | shared does not prefer the CDN field | `test_cli::test_a_response_head_prefers_the_cdn_field_for_a_shared_cache` |
| I02 | `_cli` | bad Expires not treated as expired | `test_review_fixes::test_the_command_line_reads_age_expires_and_folded_lines` |
| I03 | `_cli` | interrupt exits 1 | `test_contract_cli::test_an_interrupt_exits_130_without_a_traceback` |
| I04 | `_cli` | closed output exits 0 | `test_contract_cli::test_a_closed_output_exits_1_quietly[error0]` |
| I05 | `_cli` | field name prefix case-sensitive | `test_review_fixes::test_the_command_line_accepts_a_value_with_its_field_name` |
| I06 | `_cliio` | octets on the wrong platform | `test_contract_cli::test_posix_arguments_are_read_back_as_their_octets` |
| I07 | `_cliio` | EINVAL not a closed pipe | `test_contract_cli::test_a_closed_output_exits_1_quietly[error1]` |
| E01 | `_errors` | pickle loses the offset | `test_contract_api::test_errors_and_values_survive_pickling` |
| E02 | `__init__` | public names keep private modules | `test_contract_api::test_public_names_report_the_package_as_their_module` |

Result: 76 killed, 6 survived. Four were missing contracts, pinned in
`tests/test_contract_author.py` and each confirmed to fail on its mutant: P03 (NUL kept
inside a lenient value), P06 (field lines joined without the space, which moves strict
offsets), K01 (names under 40,000 characters not cut), T09 (an upper-case key written by
`build_targeted` after a direct edit of `directives`). Two are equivalent: C02 moves the
length shortcut of `delta_seconds` by one digit, and an 11-digit value is then capped by
`min` with the same result; P08 adds `raw.isdigit()` before `delta_seconds`, which returns
None for every string that test refuses, so the value stays text either way.

## Packaging, e2e and supported Pythons (items 8, 10, 13, 14), author run

Fresh clone of `release/1.0.0` on Elena's PC (CPython 3.14.2, auto:cpu turn): format,
lint, `mypy --strict src` and `mypy --strict src tests scripts` exit 0; `pytest` with both
end-to-end variables passed with one skip (the IANA file, whose live hash had changed; the
manifest was then refreshed); `python -m build` and `twine check --strict` passed. The
wheel test installs into a fresh venv and drives the console script and
`python -m ccdirectives` by subprocess from an empty folder; the upgrade test installs
0.2.0 from PyPI, probes 37,000 results and 5 command lines, upgrades in place and gets the
same answers, with the CHANGELOG changes probed apart.

Interpreter matrix: the interpreters on this PC were staged without their site-packages,
together with the wheel and the unpacked sdist (its `src` removed, the fetched sources
added), and run under an auto:cpu turn on Elena's PC: CPython 3.10.19, 3.11.5, 3.12.12,
3.13.2, 3.14.2 and 3.14.2 free-threaded, each a fresh venv with the 1.0.0 wheel and the
whole sdist suite against the installed package, exit 0 on each, only the two opt-in
end-to-end modules skipped. CPython 3.8.20 and 3.9.25 are below `requires-python`: pip
refuses the wheel on both. The first matrix run found two tests that only worked from a
checkout (one read `src`, one used a mypy from PATH that cannot see the installed
package); both now use the installed package (bd9ef8b).

Packaging: version 1.0.0, `Development Status :: 5 - Production/Stable`, Python 3.10 to
3.14 classifiers, MIT, URLs Homepage, Source, Issues and Changelog, keywords, no runtime
dependency; the sdist is an explicit list (src, tests, the two scripts, README, GUIDE,
CHANGELOG, CONTRIBUTING, LICENSE, requirements-dev.txt) without fetched files, this
report or improvement notes; the wheel holds the package, `py.typed`, the entry point and
the licence.
