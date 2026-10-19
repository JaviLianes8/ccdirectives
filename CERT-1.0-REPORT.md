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
- [x] Gates (item 15), final run at a6c10d4
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

## Second author mutation round (item 18), at abf8e2a

The fixes after the first round touched eleven modules, so the round was redone on the
pushed head abf8e2a with a new list of 212 mutations over every module (the 82 above
rewritten for the new code plus 130 new ones), in three auto:cpu turns on Elena's PC
(CPython 3.14.2, four clones, baseline 367 passed on each). Each mutation alone: the test
files of its module with `-x`, then the whole suite with `-x` (the two opt-in end-to-end
modules left out), 300-second timeout, file restored and every clone clean afterwards.

Result: 199 killed, 13 survived. Nine were missing contracts, now in
`tests/test_contract_author.py`, each confirmed to fail on its mutant: C15 and P16 (names
folded before the rules apply: `MAX-AGE=5` became the text `"5"` and a later `max-age`
was not a duplicate), S12 (a semicolon after a bare directive accepted in strict mode),
X03 (a structured Boolean `?2`), T20 (only the first of several `Cache-Control` lines given
to `select`), H05 (an `Expires` without a time zone), H07 (the body after the empty line
read as fields), H08 (field names compared case-sensitively in a head) and I10 (`Expires`
applied to a targeted field). H06 (a field name with whitespace before the colon kept)
showed a real defect: the folded lines of such a refused field were added to the field
above it, so `X-Note : a` followed by ` , no-store` added `no-store` to `Cache-Control`.
The head reader now drops them with the refused line (CHANGELOG, Fixed); after the fix
H06 is equivalent, since a name with whitespace around it never equals a field the
command line reads. Four are equivalent: C02 (as in the first round), B13 (`code == 0x7F`
is already covered by `code > 0x7E` on the same line), Y01 (an upper-case first letter
is refused by the next check of `serialize_key` with the same message) and H06.

The same head also passed, on the laptop (CPython 3.14.2): format, lint, `mypy --strict`
on src, on src and tests and on src, tests and scripts, the whole suite, both end-to-end
modules (wheel and upgrade from PyPI 0.2.0, 4 passed), `python -m build` and
`twine check --strict`; and the interpreter matrix 3.10.19, 3.11.5, 3.12.12, 3.13.2,
3.14.2 and 3.14.2 free-threaded (367 passed, 2 opt-in skipped, each), with 3.8.20 and
3.9.25 refused by pip as below `requires-python`. The final runs on the release head are
recorded under Gates.

<details>
<summary>Mutation table, second round (212 rows)</summary>

| Id | Module | Mutation | Caught by |
| --- | --- | --- | --- |
| C01 | `_chars` | token loses the vertical bar | `test_sources::test_tchar_matches_rfc_9110` |
| C02 | `_chars` | length shortcut off by one | `survived; equivalent (see below)` |
| C03 | `_chars` | delta-seconds not capped | `test_parse::test_delta_seconds_overflow_to_two_to_the_31` |
| C04 | `_chars` | unicode digits accepted | `test_parse::test_delta_seconds_are_ascii_digits_only[\uff15]` |
| C05 | `_chars` | qdtext drops HTAB | `test_build::test_tab_inside_an_argument_is_quoted` |
| C06 | `_chars` | qdtext takes any code point | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[x="a\u0100"-character not allowed in a quoted string-4]` |
| C07 | `_chars` | names folded with unicode rules | `test_parse::test_only_ascii_letters_fold` |
| C08 | `_chars` | empty list element refused | `test_model::test_field_lists_are_split_and_lower_cased` |
| C09 | `_chars` | empty text is a token | `test_build::test_other_arguments_are_quoted_when_not_tokens` |
| C10 | `_chars` | qdtext takes the double quote | `test_sources::test_quoted_string_characters_match_rfc_9110` |
| C11 | `_chars` | qdtext takes the backslash | `test_sources::test_quoted_string_characters_match_rfc_9110` |
| C12 | `_chars` | quoted-pair refuses HTAB | `test_strict::test_quoted_pairs_and_obs_text_are_valid` |
| C13 | `_chars` | all zeros read as one | `test_strict::test_strict_mode_accepts_every_valid_form` |
| C14 | `_chars` | field names keep their case | `test_strict::test_strict_mode_accepts_every_valid_form` |
| C15 | `_chars` | Z not folded | `survived; then test_contract_author::test_names_are_folded_before_the_rules_apply` |
| C16 | `_chars` | HTAB is not whitespace | `test_strict::test_strict_mode_accepts_every_valid_form` |
| S01 | `_scan` | space before = check off by one | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[max-age=60 public-expected ','-11]` |
| S02 | `_scan` | name before junk dropped | `test_parse::test_a_name_followed_by_junk_is_kept_bare` |
| S03 | `_scan` | unterminated quote argument lost | `test_parse::test_an_unterminated_quote_does_not_hide_later_directives` |
| S04 | `_scan` | junk after argument kept for quoted | `test_parse::test_delta_seconds_are_ascii_digits_only[\uff15]` |
| S05 | `_scan` | quoted-pair keeps the backslash | `test_parse::test_escaped_quote_inside_a_quoted_argument` |
| S06 | `_scan` | unterminated offset at the end | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[x="open-unterminated quoted string-2]` |
| S07 | `_scan` | trailing backslash reads past the end | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[x="a\\-unterminated quoted string-2]` |
| S08 | `_scan` | whitespace offset after the spaces | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[max-age= 60-whitespace after '='-8]` |
| S09 | `_scan` | leading whitespace not skipped | `test_parse::test_parses_a_mix_of_boolean_and_valued_directives` |
| S10 | `_scan` | empty argument accepted strictly | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[x=-expected a token or a quoted string-2]` |
| S11 | `_scan` | any character inside quotes | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[x="a\u0100"-character not allowed in a quoted string-4]` |
| S12 | `_scan` | semicolon read as a separator | `survived; then test_contract_author::test_a_semicolon_is_not_a_separator` |
| S13 | `_scan` | closing quote not consumed | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[private="a b"-not a list of field names-0]` |
| P01 | `_parse` | last occurrence wins | `test_parse::test_the_first_occurrence_wins_and_repeats_are_reported` |
| P02 | `_parse` | DEL allowed in strict mode | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[x="a\x7fb"-control character-4]` |
| P03 | `_parse` | NUL kept in lenient mode | `test_contract_author::test_nul_inside_a_value_becomes_a_space_in_lenient_mode` |
| P04 | `_parse` | bare max-age accepted | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[max-age-'max-age' needs delta-seconds-0]` |
| P05 | `_parse` | immutable argument accepted strictly | `test_review_fixes::test_immutable_with_an_argument_is_not_generated` |
| P06 | `_parse` | lines joined without space | `test_contract_author::test_field_lines_are_joined_with_a_comma_and_a_space` |
| P07 | `_parse` | strict flag unchecked | `test_contract_api::test_flags_must_be_real_bools[None]` |
| P09 | `_parse` | contexts swapped | `test_strict::test_context_applies_the_rules_of_one_direction` |
| P10 | `_parse` | unknown context accepted | `test_parse::test_an_unknown_context_is_refused` |
| P11 | `_parse` | bytes read as an iterable | `test_parse::test_bytes_are_refused_with_a_hint` |
| P12 | `_parse` | repeated directive accepted strictly | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[no-store, no-store-repeated directive 'no-store'-10]` |
| P13 | `_parse` | bad field list accepted strictly | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[private="a b"-not a list of field names-0]` |
| P14 | `_parse` | bad max-stale accepted strictly | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[max-stale=x-not delta-seconds-0]` |
| P15 | `_parse` | delta-seconds kept as text | `test_parse::test_numeric_directive_becomes_an_int` |
| P16 | `_parse` | names keep their case | `survived; then test_contract_author::test_names_are_folded_before_the_rules_apply` |
| R01 | `_registry` | max-stale needs an argument | `test_sources_rules::test_every_argument_rule_follows_the_rfcs` |
| R02 | `_registry` | stale-if-error not a request directive | `test_sources_rules::test_every_argument_rule_follows_the_rfcs` |
| R03 | `_registry` | strictest rule without context | `test_strict::test_strict_mode_reports_the_problem_and_its_offset[no-cache="set-cookie, x y"-not a list of field names-0]` |
| R04 | `_registry` | private not a field list | `test_build::test_field_lists_are_always_quoted` |
| R05 | `_registry` | immutable argument not ignored | `test_sources_rules::test_every_argument_rule_follows_the_rfcs` |
| R06 | `_registry` | max-stale not a delta-seconds directive | `test_roundtrip::test_build_then_parse_gives_back_the_structure` |
| R07 | `_registry` | request context reads the response rule | `test_sources_rules::test_every_argument_rule_follows_the_rfcs` |
| R08 | `_registry` | bare min-fresh accepted | `test_sources_rules::test_every_argument_rule_follows_the_rfcs` |
| B01 | `_build` | False written as present | `test_build::test_false_flag_is_omitted` |
| B02 | `_build` | minus one accepted | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives3-cannot be negative]` |
| B03 | `_build` | build does not cap | `test_build::test_delta_seconds_go_out_as_tokens` |
| B04 | `_build` | obs-text written | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives11-cannot carry]` |
| B05 | `_build` | arguments never quoted | `test_build::test_other_arguments_are_quoted_when_not_tokens` |
| B06 | `_build` | backslash not escaped | `test_build::test_quotes_and_backslashes_are_escaped` |
| B07 | `_build` | field lists in token form | `test_build::test_field_lists_are_always_quoted` |
| B08 | `_build` | huge integer error escapes | `test_contract_hostile::test_a_huge_extension_integer_is_a_cache_control_error` |
| B09 | `_build` | bare max-age written | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives6-needs delta-seconds]` |
| B10 | `_build` | argument on no-store written | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives8-takes no argument]` |
| B11 | `_build` | name that is not a token written | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives0-is not a token]` |
| B12 | `_build` | line breaks written | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives10-cannot carry]` |
| B13 | `_build` | DEL written | `survived; equivalent (see below)` |
| B14 | `_build` | bad field list written | `test_build::test_build_refuses_what_the_grammar_cannot_carry[directives13-not a list of field names]` |
| B15 | `_build` | delta-seconds text written as given | `test_contract_api::test_every_public_name_has_a_passing_example` |
| B16 | `_build` | build takes any object | `test_contract_lens_c::test_spoofed_flags_names_times_and_structures_are_refused` |
| B17 | `_build` | parts joined without space | `test_build::test_builds_boolean_and_valued_directives` |
| A01 | `_access` | has false for an empty argument | `test_model::test_flags_are_true_for_any_present_value_but_false` |
| A02 | `_access` | negative seconds returned | `test_model::test_seconds_rejects_flags_text_and_negative_numbers` |
| A03 | `_access` | bare max-stale not unlimited | `test_model::test_bare_max_stale_accepts_any_staleness` |
| A04 | `_access` | seconds not capped | `test_model::test_seconds_rejects_flags_text_and_negative_numbers` |
| A05 | `_access` | s_maxage reads max-age | `test_model::test_each_number_reads_its_own_directive[s_maxage-s-maxage]` |
| A06 | `_access` | private_fields reads no-cache | `test_model::test_field_lists_are_split_and_lower_cased` |
| A07 | `_access` | a flag read as one second | `test_model::test_seconds_rejects_flags_text_and_negative_numbers` |
| A08 | `_access` | text read through its subclass | `test_contract_lens_c2::test_a_str_subclass_value_is_read_as_plain_text` |
| A09 | `_access` | extensions ignore the context | `test_model::test_extensions_depend_on_the_direction` |
| A10 | `_access` | bad field list listed | `test_model::test_field_lists_are_split_and_lower_cased` |
| A11 | `_access` | False counts as present | `test_model::test_flags_are_true_for_any_present_value_but_false` |
| A12 | `_access` | lookups are case-sensitive | `test_model::test_construction_folds_names_and_keeps_the_first_of_a_pair` |
| A13 | `_access` | must_understand reads must-revalidate | `test_model::test_each_flag_reads_its_own_directive[must_understand-must-understand]` |
| A14 | `_access` | proxy_revalidate reads public | `test_model::test_each_flag_reads_its_own_directive[proxy_revalidate-proxy-revalidate]` |
| A15 | `_access` | only_if_cached reads no-store | `test_model::test_each_flag_reads_its_own_directive[only_if_cached-only-if-cached]` |
| A16 | `_access` | min_fresh reads max-stale | `test_model::test_each_number_reads_its_own_directive[min_fresh-min-fresh]` |
| A17 | `_access` | stale_if_error reads the other window | `test_model::test_each_number_reads_its_own_directive[stale_if_error-stale-if-error]` |
| A18 | `_access` | immutable reads public | `test_model::test_flags_are_true_for_any_present_value_but_false` |
| A19 | `_access` | no_transform reads no-store | `test_model::test_each_flag_reads_its_own_directive[no_transform-no-transform]` |
| D01 | `_model` | constructor keeps the last | `test_model::test_construction_folds_names_and_keeps_the_first_of_a_pair` |
| D02 | `_model` | int subclass kept | `test_contract_equality::test_equality_reads_direct_edits_as_plain_values` |
| D03 | `_model` | in is case-sensitive | `test_contract_hostile::test_subclasses_are_read_as_their_plain_values` |
| D04 | `_model` | equality ignores value types | `test_contract_equality::test_equality_tells_numbers_from_flags` |
| D05 | `_model` | equality ignores duplicates | `test_contract_equality::test_equality_ignores_order_and_case_but_not_duplicates` |
| D06 | `_model` | subclass compares equal | `test_contract_equality::test_equality_with_other_types_is_false_both_ways` |
| D07 | `_model` | equality reads raw values | `test_contract_equality::test_equality_reads_direct_edits_as_plain_values` |
| D08 | `_model` | a string accepted as duplicates | `test_contract_types::test_public_functions_refuse_the_wrong_structure` |
| D09 | `_model` | assignment unchecked | `test_model::test_values_of_the_wrong_type_are_refused` |
| D10 | `_model` | missing name not cut | `test_contract_lens_c2::test_deleting_a_missing_name_reports_it_cut` |
| D11 | `_model` | names of direct edits not plain | `test_contract_lens_c2::test_a_name_set_directly_is_written_as_plain_text` |
| D12 | `_model` | str subclass kept | `test_contract_hostile::test_subclasses_are_read_as_their_plain_values` |
| D13 | `_model` | flags stored as numbers | `test_model::test_flags_are_true_for_any_present_value_but_false` |
| D14 | `_model` | values returns the names | `test_contract_api::test_every_public_method_has_a_passing_example` |
| K01 | `_checks` | names not cut | `test_contract_author::test_a_long_name_is_cut_to_forty_characters_in_messages[41]` |
| K02 | `_checks` | int accepted as a flag | `test_contract_api::test_flags_must_be_real_bools[0]` |
| K03 | `_checks` | infinity accepted as a time | `test_contract_hostile::test_times_must_be_finite[nan]` |
| K04 | `_checks` | minus one second accepted | `test_fresh::test_negative_age_is_refused` |
| K05 | `_checks` | type names not cut | `test_contract_hostile::test_a_metaclass_cannot_inflate_or_break_a_type_name` |
| K06 | `_checks` | type name read through the metaclass | `test_contract_hostile::test_a_metaclass_cannot_inflate_or_break_a_type_name` |
| K07 | `_checks` | a spoofed class passes the type check | `test_contract_lens_c::test_a_spoofed_class_is_not_a_directive_value[bool]` |
| K08 | `_checks` | bool accepted as a time | `test_contract_hostile::test_times_must_be_numbers[True]` |
| K09 | `_checks` | huge int time read as zero | `test_contract_lens_a::test_an_integer_time_beyond_a_float_is_out_of_range` |
| K10 | `_checks` | float accepted as seconds | `test_contract_hostile::test_times_must_be_numbers[True]` |
| K11 | `_checks` | cut not marked | `test_contract_author::test_a_long_name_is_cut_to_forty_characters_in_messages[41]` |
| L01 | `_lifetime` | max-age before s-maxage | `test_fresh::test_lifetime_follows_the_first_matching_rule` |
| L02 | `_lifetime` | invalid directive gives None | `test_fresh::test_invalid_freshness_information_counts_as_stale` |
| L03 | `_lifetime` | response delay ignored | `test_fresh::test_current_age_uses_the_more_conservative_estimate` |
| L04 | `_lifetime` | age rounded down | `test_fresh::test_current_age_uses_the_more_conservative_estimate` |
| L06 | `_lifetime` | apparent age not clamped | `test_contract_lens_c2::test_time_arithmetic_is_exact_and_clamped` |
| L07 | `_lifetime` | lifetime rounded up | `test_fresh::test_lifetime_follows_the_first_matching_rule` |
| L08 | `_lifetime` | cap one short | `test_contract_hostile::test_overflowing_time_arithmetic_gives_two_to_the_31` |
| L09 | `_lifetime` | negative results kept | `test_fresh::test_lifetime_follows_the_first_matching_rule` |
| L10 | `_lifetime` | Age not capped first | `test_contract_lens_a::test_an_age_value_past_two_to_the_31_is_read_as_two_to_the_31` |
| L11 | `_lifetime` | any policy object accepted | `test_contract_lens_c2::test_a_spoofed_policy_is_a_type_error_with_its_own_message` |
| L12 | `_lifetime` | expires without date ignored | `test_fresh::test_expires_needs_a_date` |
| L13 | `_lifetime` | float arithmetic | `test_contract_hostile::test_overflowing_time_arithmetic_gives_two_to_the_31` |
| F01 | `_fresh` | fresh at the boundary | `test_fresh::test_fresh_and_reusable` |
| F02 | `_fresh` | request max-age boundary | `test_fresh::test_request_limits_narrow_reuse` |
| F03 | `_fresh` | min-fresh boundary | `test_fresh::test_request_limits_narrow_reuse` |
| F04 | `_fresh` | s-maxage does not forbid stale | `test_fresh::test_directives_that_forbid_stale_use[max-age=60, s-maxage=60-True]` |
| F05 | `_fresh` | request stale-if-error ignored | `test_fresh::test_request_stale_if_error_takes_precedence` |
| F06 | `_fresh` | request no-cache allows background revalidation | `test_fresh::test_stale_windows_apply_only_once_stale` |
| F07 | `_fresh` | private cache stores no-store | `test_fresh::test_may_store_follows_the_directives` |
| F08 | `_fresh` | must-revalidate does not allow authorized | `test_fresh::test_may_store_follows_the_directives` |
| F09 | `_fresh` | age not capped | `test_properties::test_the_verdict_keeps_its_invariants` |
| F10 | `_fresh` | empty private list qualifies | `test_contract_lens_b::test_an_empty_private_list_keeps_a_shared_cache_out[private=]` |
| F11 | `_fresh` | must-understand ignored | `test_fresh::test_must_understand_overrides_no_store_only_when_understood` |
| F13 | `_fresh` | stale-if-error ignores what forbids stale | `test_fresh::test_directives_that_forbid_stale_use[max-age=60, must-revalidate-False]` |
| F14 | `_fresh` | no-cache response reusable | `test_fresh::test_response_no_cache_blocks_reuse_even_when_fresh` |
| F15 | `_fresh` | max-stale boundary | `test_fresh::test_max_stale_admits_a_stale_response` |
| F16 | `_fresh` | Authorization ignored | `test_fresh::test_may_store_follows_the_directives` |
| F17 | `_fresh` | negative staleness | `test_fresh::test_fresh_and_reusable` |
| F18 | `_fresh` | private cache refuses private | `test_fresh::test_may_store_follows_the_directives` |
| T01 | `_targeted` | only no-store kept on a bad value | `test_targeted::test_restrictive_directives_survive_a_bad_value` |
| T02 | `_targeted` | negative max-age kept | `test_targeted::test_values_that_break_a_directive_rule_are_left_out` |
| T03 | `_targeted` | empty field not ignored | `test_targeted::test_an_empty_or_invalid_field_is_ignored[]` |
| T04 | `_targeted` | invalid target wins | `test_targeted::test_select_prefers_the_first_valid_target` |
| T05 | `_targeted` | token field list accepted | `test_targeted::test_restrictive_directives_survive_a_bad_value` |
| T10 | `_targeted` | bad s-maxage dropped | `test_targeted::test_values_that_break_a_directive_rule_are_left_out` |
| T11 | `_targeted` | targeted delta-seconds not capped | `test_contract_hostile::test_folded_head_lines_join_in_linear_time` |
| T13 | `_targeted` | inner list read as a flag | `test_targeted::test_values_that_break_a_directive_rule_are_left_out` |
| T14 | `_targeted` | decimal extension dropped | `test_targeted::test_members_map_to_directive_values` |
| T15 | `_targeted` | delta-seconds text written as a String | `test_targeted::test_build_targeted_writes_a_dictionary` |
| T16 | `_targeted` | field list written as a Token | `test_targeted::test_build_targeted_writes_a_dictionary` |
| T17 | `_targeted` | 16-digit extension reaches the serializer | `test_contract_lens_a::test_build_targeted_names_the_directive_with_a_long_integer` |
| T18 | `_targeted` | triples accepted as pairs | `test_contract_lens_a::test_select_refuses_what_is_not_a_pair[pair0]` |
| T19 | `_targeted` | field names compared with case | `test_targeted::test_select_prefers_the_first_valid_target` |
| T20 | `_targeted` | only the first Cache-Control line | `survived; then test_contract_author::test_select_combines_every_cache_control_line` |
| T21 | `_targeted` | bytes read as lines | `test_review_fixes::test_arguments_of_the_wrong_type_are_refused` |
| T22 | `_targeted` | directive rules not applied | `test_targeted::test_build_targeted_refuses_what_the_dictionary_cannot_carry[directives2-needs delta-seconds]` |
| X01 | `_sf` | key may start with a digit | `test_sf_corpus::test_the_corpus_file_parses_as_expected[dictionary]` |
| X02 | `_sf` | four decimal places accepted | `test_sf_corpus::test_the_corpus_file_parses_as_expected[number]` |
| X03 | `_sf` | ?2 accepted | `survived; then test_contract_author::test_a_structured_boolean_is_only_0_or_1` |
| X04 | `_sf` | DEL inside a String | `test_sf_corpus::test_the_corpus_file_parses_as_expected[string-generated]` |
| X05 | `_sf` | token stops at colon and slash | `test_sf_corpus::test_the_corpus_file_parses_as_expected[token]` |
| X06 | `_sf` | upper-case escapes in a Display String | `test_sf_corpus::test_the_corpus_file_parses_as_expected[display-string]` |
| X07 | `_sf` | non-base64 octets ignored | `test_sf_corpus::test_the_corpus_file_parses_as_expected[binary]` |
| X08 | `_sf` | negative integers lose the sign | `test_sf_corpus::test_the_corpus_file_parses_as_expected[date]` |
| X09 | `_sf` | decimal Date accepted | `test_sf_corpus::test_the_corpus_file_parses_as_expected[date]` |
| T06 | `_sf` | 16-digit integer accepted | `test_sf_corpus::test_the_corpus_file_parses_as_expected[date]` |
| T07 | `_sf` | escaped n accepted | `test_sf_corpus::test_the_corpus_file_parses_as_expected[string-generated]` |
| T08 | `_sfdict` | trailing comma accepted | `test_sf_corpus::test_the_corpus_file_parses_as_expected[dictionary]` |
| Y01 | `_sfdict` | upper-case first letter written | `survived; equivalent (see below)` |
| Y02 | `_sfdict` | upper-case letters written | `test_contract_author::test_build_targeted_refuses_a_key_that_is_not_lower_case_ascii[x-A]` |
| Y03 | `_sfdict` | tab after a member refused | `test_sf_corpus::test_the_corpus_file_parses_as_expected[dictionary]` |
| Y04 | `_sfdict` | inner list parameters not read | `test_sf_corpus::test_the_corpus_file_parses_as_expected[examples]` |
| Y06 | `_sfdict` | String backslash not escaped | `test_roundtrip::test_build_targeted_then_parse_targeted_gives_back_the_structure` |
| Y08 | `_sfdict` | token may start with a digit | `test_targeted::test_build_targeted_writes_a_dictionary` |
| Y09 | `_sfdict` | first repeated key wins | `test_sf_corpus::test_the_corpus_file_parses_as_expected[dictionary]` |
| H01 | `_head` | first head used | `test_cli::test_a_response_head_prefers_the_cdn_field_for_a_shared_cache` |
| H02 | `_head` | Age field ignored | `test_review_fixes::test_the_command_line_reads_age_expires_and_folded_lines` |
| H03 | `_head` | space folding ignored | `test_review_fixes::test_the_command_line_reads_age_expires_and_folded_lines` |
| H04 | `_head` | huge dates escape | `test_contract_cli_edges::test_an_http_date_no_date_can_hold_does_not_parse[Mon, 01 Jan 99999999999 00:00:00 GMT]` |
| H05 | `_head` | dates without a zone accepted | `survived; then test_contract_author::test_an_expires_without_a_time_zone_means_already_expired` |
| H06 | `_head` | field names with spaces accepted | `survived; equivalent (see below)` |
| H07 | `_head` | body read as fields | `survived; then test_contract_author::test_the_head_reader_follows_the_field_rules` |
| H08 | `_head` | field lookup case-sensitive | `survived; then test_contract_author::test_the_head_reader_follows_the_field_rules` |
| H09 | `_head` | folded parts joined without space | `test_contract_hostile::test_folded_head_lines_join_in_linear_time` |
| I01 | `_cli` | shared does not prefer the CDN field | `test_cli::test_a_response_head_prefers_the_cdn_field_for_a_shared_cache` |
| I02 | `_cli` | bad Expires not treated as expired | `test_contract_cli_edges::test_a_head_with_such_a_date_is_judged_without_a_traceback[Mon, 01 Jan 99999999999 00:00:00 GMT-Expires]` |
| I03 | `_cli` | interrupt exits 1 | `test_contract_cli::test_an_interrupt_exits_130_without_a_traceback` |
| I04 | `_cli` | closed output exits 0 | `test_contract_cli::test_a_closed_output_exits_1_quietly[error0]` |
| I05 | `_cli` | field name prefix case-sensitive | `test_review_fixes::test_the_command_line_accepts_a_value_with_its_field_name` |
| I08 | `_cli` | strict head checked as a request | `test_review_fixes::test_the_command_line_checks_a_head_with_the_response_rules` |
| I09 | `_cli` | Age of the head ignored | `test_contract_cli::test_standard_input_is_read_as_octets_in_a_real_process` |
| I10 | `_cli` | Expires applied to a targeted field | `survived; then test_contract_author::test_expires_does_not_apply_to_a_targeted_field` |
| I11 | `_cli` | closed output not silenced | `test_contract_cli_edges::test_help_into_a_closed_pipe_exits_1_quietly` |
| I13 | `_cli` | POSIX value not read as octets | `test_contract_cli::test_posix_arguments_are_read_back_as_their_octets` |
| I14 | `_cli` | closed standard input exits 1 | `test_contract_cli::test_closed_standard_streams` |
| I06 | `_cliio` | octets on the wrong platform | `test_contract_cli::test_posix_arguments_are_read_back_as_their_octets` |
| I07 | `_cliio` | EINVAL not a closed pipe | `test_contract_cli::test_a_closed_output_exits_1_quietly[error1]` |
| J01 | `_cliio` | usage errors not cut | `test_contract_cli_edges::test_a_huge_unrecognized_argument_is_not_echoed_whole` |
| J02 | `_cliio` | help bypasses the output rules | `test_contract_cli_edges::test_help_into_a_closed_pipe_exits_1_quietly` |
| J03 | `_cliio` | usage error exits 1 | `test_contract_cli::test_exit_statuses_in_a_real_process[args3-2]` |
| J04 | `_cliio` | closed stderr object raises | `test_contract_lens_c2::test_a_closed_stderr_never_raises` |
| J05 | `_cliio` | closed stream object reported as a failure | `test_contract_lens_c2::test_a_closed_stdout_object_exits_1_quietly` |
| J06 | `_cliio` | standard input read as UTF-8 | `test_contract_cli::test_standard_input_is_read_as_octets_in_a_real_process` |
| J07 | `_cliio` | messages without the program name | `test_contract_cli::test_exit_statuses_in_a_real_process[args1-1]` |
| J08 | `_cliio` | usage line missing | `test_contract_cli_edges::test_a_huge_unrecognized_argument_is_not_echoed_whole` |
| E01 | `_errors` | pickle loses the offset | `test_contract_api::test_errors_and_values_survive_pickling` |
| E03 | `_errors` | offset missing from the message | `test_contract_api::test_public_names_report_the_package_as_their_module` |
| E02 | `__init__` | public names keep private modules | `test_contract_api::test_public_names_report_the_package_as_their_module` |
| E04 | `__init__` | select missing from __all__ | `test_contract::test_all_lists_exactly_the_public_api` |

</details>

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

## Gates (item 15), final run at a6c10d4

Fresh clones of the pushed head a6c10d4 on Elena's PC (CPython 3.14.2, auto:cpu turns,
2026-10-19), the fetched sources checked against the manifest first (25 files, all ok):

- `ruff format --check .` exit 0, `ruff check .` exit 0, `mypy --strict src` exit 0,
  `mypy --strict src tests` and `mypy --strict src tests scripts` exit 0; `pytest`: 374
  passed, 2 skipped (the two opt-in end-to-end modules), exit 0.
- With `CCDIRECTIVES_E2E=1` and `CCDIRECTIVES_E2E_PYPI=1`: the wheel, upgrade and install
  modules, 4 passed (wheel in a throwaway venv, console script and `python -m` by
  subprocess, upgrade in place from PyPI 0.2.0, which is still the only release).
- `python -m build` exit 0 and `twine check --strict` PASSED for the wheel and the sdist.
  The sdist holds src, tests (with `tests/upstream/MANIFEST.json`, no fetched file), the
  two scripts, README, GUIDE, CHANGELOG, CONTRIBUTING, LICENSE, requirements-dev.txt,
  pyproject and `.gitignore`; the wheel holds the package, `py.typed`, the entry point and
  `licenses/LICENSE`. METADATA: 1.0.0, Production/Stable, Python 3.10 to 3.14, MIT, the
  four project URLs, no runtime dependency.
- Interpreter matrix, the 1.0.0 wheel in a fresh venv per interpreter and the sdist suite
  against it (its `src` removed): CPython 3.10.19, 3.11.5, 3.12.12, 3.13.2, 3.14.2 and
  3.14.2 free-threaded, 374 passed and 2 opt-in skipped on each, exit 0; 3.8.20 and 3.9.25
  refused by pip as below `requires-python`.

## QA lenses (item 19), round 1 at 7361bc2

Four lenses reported findings (a: API and docs, b: correctness and ground truth, c:
adversarial, e: contract strength). Every behaviour finding first got a contract that
failed on 7361bc2 (`tests/test_contract_qa1.py`, `tests/test_contract_qa1_head.py`, a new
line in `tests/test_typing.py`), then the fix; every behaviour change is in CHANGELOG
1.0.0.

| Finding | Fix |
| --- | --- |
| a-F1 `False` absent only for some operations | `False` is dropped on construction and assignment and skipped by `build`, `build_targeted` and equality when set directly; `in`, `len`, iteration, `dict(cc)`, `extensions()` and `==` now agree with `has()` |
| a-F2 `select` leaked the interpreter's unbounded `TypeError` | headers and targets are checked for iterability, message built with the cut type name |
| a-F3 `select` type refused lists of two | `Headers` accepts `tuple[str, str]` and `list[str]` pairs; mypy check added |
| a-F4 undocumented errors and rounding | GUIDE and docstrings of `parse`, `freshness_lifetime` and `assess` list the `TypeError` and `ValueError` cases and the floor of `expires - date`; contract for both |
| a-F5 properties without docstrings | every `CacheControl` property (moved to `_props.py` for the 200-line limit) has a docstring with a doctest; a contract runs all 18 |
| b-F1, c-F3 asctime refused | new `_dates.http_date` reads the three RFC 9110 section 5.6.7 formats, all as UTC |
| b-F2 list-based `Age` read as 0 | first member used (RFC 9111 section 5.1) |
| b-F3 non-GMT `Expires` used | a zone other than `GMT` is invalid, so `Expires` means already expired |
| b-F4 rfc850 years 69 to 76 put in 19xx | 50-year rule relative to the current year |
| b-F5 "one exception" in strict mode | GUIDE and README now name both exceptions (argument on `immutable`, repeated directives) |
| c-F1 `private=5` loosened by the round trip | `build` and `build_targeted` raise `CacheControlError` for a number on `no-cache` or `private`; contract that `parse(build(x), strict=True)` and the targeted round trip keep the `may_store` verdict and field lists |
| c-F2 years below 100 moved to 20xx | four-digit years are read as written; a two-digit year in IMF-fixdate is invalid |
| c-F4 `Age` stripped with `str.strip()` | only SP and HTAB stripped |
| e-F1 to e-F4 surviving mutants | contracts added; each mutant (no cap in `parse_targeted`, reversed targets, case-sensitive `cache-control:` prefix, `Name :` field kept) now fails `test_contract_qa1*.py`, checked one at a time |
| e-F5 upgrade test red on Windows 3.14.2 | the 0.2.0 closed-output probe accepts exit 1 or 120 with or without output |

Disputed findings: none.

Run after the fixes, fresh clone of the commit on Elena's PC (CPython 3.14.2, auto:cpu
turn elena/2, fetched sources present): `ruff format --check .`, `ruff check .`,
`mypy --strict src tests scripts` exit 0; `pytest` 428 passed, 2 skipped (the opt-in
end-to-end modules), exit 0; with `CCDIRECTIVES_E2E=1` and `CCDIRECTIVES_E2E_PYPI=1` the
wheel and upgrade modules passed, exit 0. Fix commit: 9cc83ff.

## QA lenses (item 19), round 2 at 6d12c6b

Three lenses reported findings (a: API and docs, b: correctness and ground truth, e:
contract strength). Each behaviour finding first got a contract in
`tests/test_contract_qa2.py` that failed on 6d12c6b, then the fix; the surviving mutants
got contracts that pass on the code and fail on the mutant. Behaviour changes are in
CHANGELOG 1.0.0 (Fixed).

| Finding | Fix |
| --- | --- |
| a-F6 GUIDE said `has()` is true for any stored value | GUIDE restored to "any value but `False`" and now lists which operations treat a `False` placed directly in `directives` as absent (`build`, `build_targeted`, equality, `has()`, properties) and which still see it (`in`, `len`, iteration, `keys`, `values`, `items`, `get`, `dict(cc)`, `extensions()`); CHANGELOG says the same; contract `test_a_false_set_directly_is_stored_but_not_present` |
| b-N1 empty `Age` member read as 0 | all `Age` lines form one list, empty and whitespace-only members are skipped, the first other member is used; `Age: , 100` and an empty `Age` line before `Age: 100` give 100 (stale) |
| b-N2 `GMT` matched case-sensitively | `GMT` matches in any ASCII case in IMF-fixdate and rfc850-date |
| b-N3 50-year rule compared years | candidate instants are compared with now plus 50 calendar years; `31-Dec-76` and `19-Oct-76 12:00:01` read at 2026-10-19T12:00Z are 1976; docstring and GUIDE updated |
| e-D02, D05, D06, D11, D14, D16, D17, D18, e-M02 surviving mutants | contracts for a non-GMT rfc850 zone, unknown day names, short day names in rfc850, day 00, second 60, upper-case names in all three formats, trailing or leading text, a two-digit asctime year, and a `False` repeat of a present name |

Each reported mutant (and the N1, N2, N3 fixes reverted) was applied one at a time to a
copy of `src` and the suite run against it: every one fails, first failing test as
listed.

| Mutant | First failing test |
| --- | --- |
| D02 rfc850 zone `[A-Za-z]+` | `test_malformed_dates_do_not_parse[Sunday, 06-Nov-94 08:49:37 EST]` |
| D05 `_day` always True | `test_malformed_dates_do_not_parse[Xyz, 06 Nov 1994 08:49:37 GMT]` |
| D06 rfc850 takes short day names | `test_malformed_dates_do_not_parse[Sun, 06-Nov-94 08:49:37 GMT]` |
| D11 day range from 0 | `test_malformed_dates_do_not_parse[Sun, 00 Nov 1994 08:49:37 GMT]` |
| D14 second > 59 refused | `test_second_sixty_is_the_next_second` |
| D16 IMF names `[A-Z][a-z]+` | `test_names_and_gmt_ignore_case[SUN, 06 NOV 1994 08:49:37 GMT]` |
| D17 `_IMF.match` | `test_malformed_dates_do_not_parse[Sun, 06 Nov 1994 08:49:37 GMTX]` |
| D18 asctime year `[0-9]{2,4}` | `test_malformed_dates_do_not_parse[Sun Nov  6 08:49:37 94]` |
| M02 `False` skip after the duplicate check | `test_a_false_repeat_of_a_present_name_is_not_a_duplicate` |
| N1 empty Age members kept | `test_a_list_age_uses_its_first_member` |
| N1 only the first Age line read | `test_age_lines_form_one_list` |
| N2 `GMT` case-sensitive | `test_names_and_gmt_ignore_case[Sun, 06 Nov 1994 08:49:37 gmt]` |
| N3 years compared, not instants | `test_the_fifty_year_rule_compares_instants[Thursday, 31-Dec-76 00:00:00 GMT-1976]` |

Disputed findings: none.

Run after the fixes, clone of 0dd886e on Elena's PC (CPython 3.14.2, auto:cpu turn
elena/1, fetched sources present): `ruff format --check .`, `ruff check .`,
`mypy --strict src tests scripts` exit 0; `pytest` 476 passed, 2 skipped (the opt-in
end-to-end modules), exit 0; with `CCDIRECTIVES_E2E=1` and `CCDIRECTIVES_E2E_PYPI=1` the
wheel and upgrade modules passed, exit 0. Fix commit: 0dd886e.

## QA lenses (item 19), round 3 at 85988ff

Two lenses reported findings (a: API and docs, e: contract strength). The behaviour
finding first got a contract in `tests/test_contract_qa3.py` that failed on 85988ff, then
the fix; the surviving mutants got contracts that pass on the code and fail on the
mutant. The behaviour change is in CHANGELOG 1.0.0 (Fixed).

| Finding | Fix |
| --- | --- |
| a-N1 `29-Feb-00` read in 2060 was invalid, against the documented rule | the rfc850 year is now chosen only among candidate years that have the day (six centuries are tried, so a leap year is always reached); `29-Feb-00` read in 2060, 2160 and 2250 is 2000-02-29 and the CLI gives lifetime 3600; GUIDE and docstring state the leap day case |
| e-N14 the 50-year filter could reach four-digit years | `_stamp` takes an explicit `limit` that only the rfc850 branch passes, and a missing candidate returns None instead of raising; contracts that `06 Nov 3000` in IMF-fixdate and asctime is read as written, through `http_date` and through the CLI (lifetime capped at 2147483648, fresh) |
| e-N10, e-N11 `_limit` minutes and seconds unchecked | contracts with now 12:30:30: `19-Oct-76` at 12:30:15, 12:30:30 and 12:15:00 is 2076, at 12:30:31 and 12:45:00 is 1976, and the CLI lifetimes 1577925015 and 1577924100 |
| e-N03 `GMT` could be truncated to `GM` | contract that IMF-fixdate and rfc850-date ending in `GM`, or with no zone, do not parse, and such an `Expires` is already expired |
| e-N05 asctime could take long day names | contract that `Sunday Nov  6 08:49:37 1994` (any case) does not parse, and such an `Expires` is already expired |

Each mutant was applied one at a time to `src` and the whole suite run against it: every
one fails, first failing test as listed.

| Mutant | First failing test |
| --- | --- |
| N03 `_GMT` `[Gg][Mm][Tt]?` | `test_truncated_zones_and_long_asctime_days_do_not_parse[Sun, 06 Nov 1994 08:49:37 GM]` |
| N05 asctime takes `_DAYS + _LONG_DAYS` | `test_truncated_zones_and_long_asctime_days_do_not_parse[Sunday Nov  6 08:49:37 1994]` |
| N10 `_limit` seconds as 0 | `test_the_fifty_year_rule_compares_minutes_and_seconds[Monday, 19-Oct-76 12:30:15 GMT-2076]` |
| N11 `_limit` minutes as 0 | `test_the_fifty_year_rule_compares_minutes_and_seconds[Monday, 19-Oct-76 12:30:15 GMT-2076]` |
| N14 IMF-fixdate also given the 50-year limit | `test_four_digit_years_far_ahead_are_read_as_written[Sun, 06 Nov 3000 08:49:37 GMT]` |
| N1 only three centuries tried | `test_february_29_takes_the_latest_year_that_has_it[now2-2000]` |
| N1 candidate years not filtered by the day | `test_other_dates_do_not_parse[Mon, 31 Feb 1994 00:00:00 GMT]` |

Disputed findings: none.

Run after the fixes, clone of aaafc96 on the laptop (CPython 3.14.6, auto:cpu turn
portatil/1, fetched sources present): `ruff format --check .`, `ruff check .`,
`mypy --strict src tests scripts` exit 0; with `CCDIRECTIVES_E2E=1` and
`CCDIRECTIVES_E2E_PYPI=1`, `pytest` 501 passed, exit 0. Fix commit: aaafc96.

## QA lenses (item 19), round 4 at 8a923ec

One lens reported findings (e: contract strength), both surviving mutants with no
behaviour bug: the code already keeps the documented promise, so each got a contract in
`tests/test_contract_qa4.py` that passes on the code and fails on the mutant. No
behaviour changed, so the CHANGELOG is unchanged.

| Finding | Fix |
| --- | --- |
| e-F1 `_centuries` could try four centuries instead of six | contract that `Tuesday, 29-Feb-00 00:00:00 GMT` read with the clock at 2310-01-01 is 2000-02-29 (five centuries back), and the CLI with that `Date`, `Expires` one hour later and `Cache-Control: public` gives lifetime 3600 |
| e-F2 `_stamp` could reject year 0001 (`y > 1`) | contract that `Mon, 01 Jan 0001 00:00:00 GMT` and `Mon Jan  1 00:00:00 0001` give -62135596800.0, and the CLI with `Date` and `Expires` one hour apart in year 0001 gives lifetime 3600; year 0000 stays rejected |

Each mutant was applied one at a time to a copy of the tree and the date contract files
run against it: both fail.

| Mutant | Failing tests |
| --- | --- |
| F1 `range(6)` as `range(4)` in `_centuries` | `test_february_29_read_in_2310_is_five_centuries_back`, `test_february_29_read_in_2310_keeps_its_lifetime` |
| F2 `y >= 1` as `y > 1` in `_stamp` | `test_year_0001_is_read_as_written` (both forms), `test_an_expires_in_year_0001_keeps_its_lifetime` |

Disputed findings: none.

Run after the fixes, clone of bbb378b on Elena's PC (CPython 3.14.2, auto:cpu turn
elena/1, fetched sources present): `ruff format --check .`, `ruff check .`,
`mypy --strict src tests scripts` exit 0; with `CCDIRECTIVES_E2E=1` and
`CCDIRECTIVES_E2E_PYPI=1`, `pytest` 506 passed, exit 0. Fix commit: bbb378b.
