"""The argument rule of every registered directive, derived from the fetched RFC text.

RFC 9111 sections 5.2.1 and 5.2.2 give each directive its argument syntax (or none),
RFC 5861 gives the two stale extensions, RFC 8246 says immutable takes none and that one
in a request has no effect. The derived table must equal the registry this library uses.
"""

from __future__ import annotations

import re

import pytest

from ccdirectives import REQUEST_DIRECTIVES, RESPONSE_DIRECTIVES, CacheControlError, parse
from ccdirectives._registry import argument_rule


def _sections(text: str, prefix: str) -> dict[str, str]:
    pattern = rf"^{re.escape(prefix)}\.\d+\.  (\S+)\n(.*?)(?=^\d+\.[\d.]*  )"
    return dict(re.findall(pattern, text, flags=re.MULTILINE | re.DOTALL))


def _rule(body: str) -> str:
    syntax = re.search(r"Argument syntax:\s+(\S+)", body)
    if syntax is None:
        return "none"
    if syntax.group(1) == "#field-name":
        return "fields"
    assert syntax.group(1) == "delta-seconds"
    return "optional-delta" if "If no value is assigned" in body else "delta"


def _derived(rfc9111: str, rfc5861: str, rfc8246: str) -> dict[tuple[str, str], str]:
    table: dict[tuple[str, str], str] = {}
    for prefix, context in (("5.2.1", "request"), ("5.2.2", "response")):
        for name, body in _sections(rfc9111, prefix).items():
            table[(name, context)] = _rule(body)
    for name in ("stale-while-revalidate", "stale-if-error"):
        assert re.search(rf'{name} = "{name}" "=" delta-seconds', rfc5861), name
        table[(name, "response")] = "delta"
    # Section 4 scopes stale-if-error in a request too; section 3 has no such sentence.
    assert "When used as a request Cache-Control extension" in rfc5861.split("4.  The", 1)[1]
    table[("stale-if-error", "request")] = "delta"
    assert "takes no arguments" in rfc8246 and "they have no meaning and MUST be ignored" in (
        " ".join(rfc8246.split())
    )
    assert "in a request has no effect" in " ".join(rfc8246.split())
    table[("immutable", "response")] = "ignored"
    return table


def test_every_argument_rule_follows_the_rfcs(rfc9111: str, rfc5861: str, rfc8246: str) -> None:
    derived = _derived(rfc9111, rfc5861, rfc8246)
    assert len(derived) == 7 + 10 + 3 + 1
    ours = {
        (name, context): argument_rule(name, context)
        for name in REQUEST_DIRECTIVES | RESPONSE_DIRECTIVES
        for context in ("request", "response")
        if argument_rule(name, context) is not None
    }
    assert ours == derived
    assert {name for name, context in derived if context == "request"} == REQUEST_DIRECTIVES
    assert {name for name, context in derived if context == "response"} == RESPONSE_DIRECTIVES


@pytest.mark.parametrize("context", ["request", "response"])
def test_strict_mode_enforces_the_derived_rules(
    rfc9111: str, rfc5861: str, rfc8246: str, context: str
) -> None:
    for (name, side), rule in _derived(rfc9111, rfc5861, rfc8246).items():
        if side != context:
            continue
        bare, delta, fields = name, f"{name}=60", f'{name}="etag, vary"'
        accepted = {
            "none": {bare},
            "ignored": {bare},
            "delta": {delta},
            "optional-delta": {bare, delta},
            # "60" is a token, so a one-element list of field names.
            "fields": {bare, fields, delta},
        }[rule]
        for header in (bare, delta, fields):
            if header in accepted:
                parse(header, strict=True, context=context)  # type: ignore[arg-type]
            else:
                with pytest.raises(CacheControlError):
                    parse(header, strict=True, context=context)  # type: ignore[arg-type]
