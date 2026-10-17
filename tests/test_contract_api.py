"""The frozen 1.0 surface: signatures, module names, examples, option types and pickling."""

from __future__ import annotations

import doctest
import inspect
import pickle
from collections.abc import Callable
from typing import Any

import pytest

import ccdirectives as cc
from ccdirectives import CacheControl, CacheControlError, Freshness, parse

SIGNATURES = {
    "CacheControl": (
        "(directives: 'dict[str, DirectiveValue]' = <factory>, "
        "duplicates: 'frozenset[str]' = frozenset()) -> None"
    ),
    "CacheControlError": "(message: 'str', offset: 'int | None' = None) -> 'None'",
    "Freshness": (
        "(lifetime: 'int | None', age: 'int', fresh: 'bool', reusable: 'bool', "
        "stale_while_revalidate: 'bool', stale_if_error: 'bool') -> None"
    ),
    "assess": (
        "(response: 'CacheControl', *, age: 'int', shared: 'bool' = False, "
        "request: 'CacheControl | None' = None, expires: 'float | None' = None, "
        "date: 'float | None' = None) -> 'Freshness'"
    ),
    "build": "(cache_control: 'CacheControl') -> 'str'",
    "build_targeted": "(cache_control: 'CacheControl') -> 'str'",
    "current_age": (
        "(*, date_value: 'float', request_time: 'float', response_time: 'float', "
        "now: 'float', age_value: 'int' = 0) -> 'int'"
    ),
    "freshness_lifetime": (
        "(response: 'CacheControl', *, shared: 'bool' = False, expires: 'float | None' = None, "
        "date: 'float | None' = None) -> 'int | None'"
    ),
    "may_store": (
        "(response: 'CacheControl', *, shared: 'bool' = False, authorized: 'bool' = False, "
        "understood_status: 'bool' = False) -> 'bool'"
    ),
    "parse": (
        "(header: 'str | Iterable[str]', *, strict: 'bool' = False, "
        "context: 'Context | None' = None) -> 'CacheControl'"
    ),
    "parse_targeted": "(value: 'str | Iterable[str]') -> 'CacheControl | None'",
    "select": (
        "(headers: 'Headers', targets: 'Iterable[str]' = ('CDN-Cache-Control',)) "
        "-> 'tuple[str, CacheControl]'"
    ),
}
CONSTANTS = {"DELTA_MAX", "REGISTERED_DIRECTIVES", "REQUEST_DIRECTIVES", "RESPONSE_DIRECTIVES"}
PROPERTIES = [
    "max_age",
    "s_maxage",
    "min_fresh",
    "max_stale",
    "stale_while_revalidate",
    "stale_if_error",
    "no_cache",
    "no_cache_fields",
    "private",
    "private_fields",
    "no_store",
    "no_transform",
    "only_if_cached",
    "must_revalidate",
    "proxy_revalidate",
    "must_understand",
    "public",
    "immutable",
]


def test_every_public_signature_is_frozen() -> None:
    assert set(SIGNATURES) | CONSTANTS | {"DirectiveValue"} == set(cc.__all__)
    for name, expected in SIGNATURES.items():
        assert str(inspect.signature(getattr(cc, name))) == expected, name


def test_the_module_exposes_nothing_public_beyond_all() -> None:
    public = {name for name in dir(cc) if not name.startswith("_")}
    assert public == set(cc.__all__)


def test_public_names_report_the_package_as_their_module() -> None:
    for name in SIGNATURES:
        assert getattr(cc, name).__module__ == "ccdirectives", name
    assert repr(CacheControlError("bad", 1)) == "CacheControlError('bad at offset 1')"


def test_cache_control_keeps_its_methods_and_typed_reads() -> None:
    for name in ("get", "items", "has", "seconds", "extensions", *PROPERTIES):
        assert hasattr(CacheControl, name), name
    assert all(isinstance(getattr(CacheControl, name), property) for name in PROPERTIES)


def test_every_public_name_has_a_passing_example() -> None:
    finder = doctest.DocTestFinder(recurse=False)
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    for name in SIGNATURES:
        tests = finder.find(getattr(cc, name), name, globs=dict(vars(cc)))
        assert tests and tests[0].examples, name
        for test in tests:
            runner.run(test)
    (module,) = finder.find(cc, "ccdirectives")
    assert module.docstring is not None
    assert all(name in module.docstring for name in [*CONSTANTS, "DirectiveValue"])
    runner.run(module)
    assert runner.failures == 0
    assert runner.tries > 40


def test_errors_and_values_survive_pickling() -> None:
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        error = pickle.loads(pickle.dumps(CacheControlError("bad", 7), protocol))
        assert type(error) is CacheControlError
        assert (error.reason, error.offset, str(error)) == ("bad", 7, "bad at offset 7")
        bare = pickle.loads(pickle.dumps(CacheControlError("bad"), protocol))
        assert (bare.reason, bare.offset, str(bare)) == ("bad", None, "bad")
        policy = parse("max-age=5, x=1, MAX-AGE=6")
        assert pickle.loads(pickle.dumps(policy, protocol)) == policy
        verdict = Freshness(1, 2, False, False, False, True)
        assert pickle.loads(pickle.dumps(verdict, protocol)) == verdict


def _flag_calls() -> list[tuple[str, Callable[[Any], object]]]:
    policy = parse("max-age=5")
    return [
        ("strict", lambda v: parse("a", strict=v)),
        ("shared", lambda v: cc.assess(policy, age=1, shared=v)),
        ("shared", lambda v: cc.freshness_lifetime(policy, shared=v)),
        ("shared", lambda v: cc.may_store(policy, shared=v)),
        ("authorized", lambda v: cc.may_store(policy, authorized=v)),
        ("understood_status", lambda v: cc.may_store(policy, understood_status=v)),
    ]


@pytest.mark.parametrize("value", [None, 0, 1, "yes", "", 1.0, [], b"x"])
def test_flags_must_be_real_bools(value: object) -> None:
    for flag, call in _flag_calls():
        with pytest.raises(TypeError) as caught:
            call(value)
        assert str(caught.value) == f"{flag} must be a bool, got {type(value).__name__}"
        call(False)
        call(True)


@pytest.mark.parametrize("bad", [1, None, b"max-age", 1.5])
def test_directive_names_must_be_str_everywhere(bad: Any) -> None:
    policy = CacheControl({"max-age": 5})
    calls: list[Callable[[], object]] = [
        lambda: policy[bad],
        lambda: policy.get(bad),
        lambda: policy.has(bad),
        lambda: policy.seconds(bad),
        lambda: policy.__delitem__(bad),
        lambda: policy.__setitem__(bad, True),
        lambda: CacheControl({bad: True}),
        lambda: CacheControl({}, frozenset({bad})),
    ]
    for call in calls:
        with pytest.raises(TypeError, match="directive names must be str"):
            call()
    assert bad not in policy
