"""Check the library against RFC 9111, 9110, 5861, 8246, 9213 and the IANA registry.

The files are read from tests/upstream (URL, size and sha256 in MANIFEST.json); the tests
that read them skip until `python scripts/fetch_upstream.py` has fetched them.
"""

from __future__ import annotations

import csv
import io
import re

from ccdirectives import (
    DELTA_MAX,
    REGISTERED_DIRECTIVES,
    REQUEST_DIRECTIVES,
    RESPONSE_DIRECTIVES,
    assess,
    may_store,
    parse,
    select,
)
from ccdirectives._chars import TCHAR, is_qdtext, is_quotable
from ccdirectives._registry import DELTA_DIRECTIVES, FIELD_DIRECTIVES


def _sections(text: str, prefix: str) -> dict[str, str]:
    """Map each directive name to its section body, for headings like ``5.2.1.1.  max-age``."""
    pattern = rf"^{re.escape(prefix)}\.\d+\.  (\S+)\n(.*?)(?=^\d+\.[\d.]*  )"
    return dict(re.findall(pattern, text, flags=re.MULTILINE | re.DOTALL))


def test_the_registry_holds_exactly_the_iana_names(iana_csv: str) -> None:
    rows = list(csv.DictReader(io.StringIO(iana_csv)))
    assert {row["Cache Directive"] for row in rows} == REGISTERED_DIRECTIVES
    for row in rows:
        name, reference = row["Cache Directive"], row["Reference"]
        assert ("5.2.1" in reference) == (name in REQUEST_DIRECTIVES - {"stale-if-error"})
        if "5.2.2" in reference:
            assert name in RESPONSE_DIRECTIVES


def test_request_and_response_sets_follow_rfc_9111_sections(rfc9111: str) -> None:
    request = _sections(rfc9111, "5.2.1")
    response = _sections(rfc9111, "5.2.2")
    assert len(request) == 7 and len(response) == 10
    defined_here = set(request) | set(response)
    assert {n for n in REQUEST_DIRECTIVES if n in defined_here} == set(request)
    assert {n for n in RESPONSE_DIRECTIVES if n in defined_here} == set(response)
    for name, body in {**request, **response}.items():
        if "delta-seconds (see Section 1.2.2)" in body:
            assert name in DELTA_DIRECTIVES, name
        if "#field-name" in body:
            assert name in FIELD_DIRECTIVES, name
    assert {n for n in DELTA_DIRECTIVES if n in defined_here} == {
        n for n, body in {**request, **response}.items() if "delta-seconds" in body
    }


def test_delta_max_is_the_value_section_1_2_2_names(rfc9111: str) -> None:
    section = rfc9111.rsplit("1.2.2.  Delta Seconds", 1)[1].split("2.  Overview", 1)[0]
    match = re.search(r"MUST consider the value\s+to be (\d+)", section)
    assert match is not None and int(match.group(1)) == DELTA_MAX
    assert parse(f"max-age={DELTA_MAX * 10}").max_age == DELTA_MAX


def test_tchar_matches_rfc_9110(rfc9110: str) -> None:
    rule = rfc9110.split("tchar          =", 1)[1].split("; any VCHAR", 1)[0]
    listed = set(re.findall(r'"(.)"', rule))
    expected = listed | set("0123456789") | {chr(c) for c in range(65, 91)}
    expected |= {chr(c) for c in range(97, 123)}
    assert expected == TCHAR


def _abnf_set(rule: str) -> set[int]:
    names = {"HTAB": {9}, "SP": {32}, "VCHAR": set(range(0x21, 0x7F))}
    names["obs-text"] = set(range(0x80, 0x100))
    codes: set[int] = set()
    for part in (p.strip() for p in rule.split("/")):
        if part in names:
            codes |= names[part]
        elif "-" in part:
            low, high = part[2:].split("-")
            codes |= set(range(int(low, 16), int(high, 16) + 1))
        else:
            codes.add(int(part[2:], 16))
    return codes


def test_quoted_string_characters_match_rfc_9110(rfc9110: str) -> None:
    qdtext = re.search(r"qdtext         = (.+)", rfc9110)
    pair = re.search(r'quoted-pair    = "\\" \( (.+) \)', rfc9110)
    assert qdtext is not None and pair is not None
    assert {c for c in range(0x110) if is_qdtext(chr(c))} == _abnf_set(qdtext.group(1))
    assert {c for c in range(0x110) if is_quotable(chr(c))} == _abnf_set(pair.group(1))


def test_the_list_examples_of_rfc_9110_parse_strictly(rfc9110: str) -> None:
    section = rfc9110.rsplit("5.6.1.2.  Recipient Requirements", 1)[1].split("5.6.2.", 1)[0]
    valid = section.split("valid values for example-list", 1)[1].split("In contrast", 1)[0]
    examples = re.findall(r'^ +"(.+)"$', valid, flags=re.MULTILINE)
    assert examples == ["foo,bar", "foo ,bar,", "foo , ,bar,charlie"]
    for example in examples:
        names = [part.strip() for part in example.split(",") if part.strip()]
        assert list(parse(example, strict=True)) == names


def test_the_extension_example_of_section_5_2_3(rfc9111: str) -> None:
    header = re.search(r"^   Cache-Control: (private, community=.+)$", rfc9111, re.MULTILINE)
    assert header is not None
    cc = parse(header.group(1), strict=True, context="response")
    # Expected values from https://www.rfc-editor.org/rfc/rfc9111.txt section 5.2.3.
    assert cc.private and cc["community"] == "UCI"
    assert cc.extensions("response") == ("community",)


def _example(text: str, start: str) -> str:
    match = re.search(rf"Cache-Control: ({re.escape(start)}.*)$", text, flags=re.MULTILINE)
    assert match is not None, start
    return match.group(1).strip()


def test_the_rfc_5861_examples(rfc5861: str) -> None:
    # Expected windows from https://www.rfc-editor.org/rfc/rfc5861.txt sections 3.1 and 4.1.
    revalidate = parse(_example(rfc5861, "max-age=600, stale-while"), strict=True)
    assert assess(revalidate, age=630).stale_while_revalidate
    assert not assess(revalidate, age=631).stale_while_revalidate
    on_error = parse(_example(rfc5861, "max-age=600, stale-if"), strict=True)
    assert assess(on_error, age=900).stale_if_error
    assert assess(on_error, age=1800).stale_if_error
    assert not assess(on_error, age=1801).stale_if_error


def test_the_rfc_8246_example(rfc8246: str) -> None:
    cc = parse(_example(rfc8246, "max-age=31536000"), strict=True, context="response")
    assert cc.immutable and cc.max_age == 31536000


def _field_pairs(block: str) -> list[list[tuple[str, str]]]:
    groups: list[list[tuple[str, str]]] = []
    previous = -2
    lines = block.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^   ((?:CDN-)?Cache-Control): (.+)$", line)
        if match:
            if index != previous + 1:
                groups.append([])
            groups[-1].append((match.group(1), match.group(2).strip()))
            previous = index
    return groups


def test_the_rfc_9213_examples(rfc9213: str) -> None:
    block = rfc9213.rsplit("3.1.  Examples", 1)[1].split("4.  IANA", 1)[0]
    split, cdn_only, nobody, all_but_cdn = _field_pairs(block)
    cdn = ("CDN-Cache-Control",)
    # Expected policies from https://www.rfc-editor.org/rfc/rfc9213.txt section 3.1.
    assert assess(select(split, cdn)[1], age=0, shared=True).lifetime == 600
    assert assess(select(split, ())[1], age=0, shared=True).lifetime == 120
    assert assess(select(split, ())[1], age=0).lifetime == 60
    assert may_store(select(cdn_only, cdn)[1], shared=True)
    assert not may_store(select(cdn_only, ())[1], shared=True)
    assert not may_store(select(nobody, cdn)[1], shared=True)
    field, policy = select(all_but_cdn, cdn)
    assert field == "CDN-Cache-Control" and may_store(policy, shared=True)
    assert policy.extensions() == ("none",)
    assert not may_store(select(all_but_cdn, ())[1])
