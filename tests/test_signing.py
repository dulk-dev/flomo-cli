"""Unit tests for the MD5 signing algorithm."""

import pytest

from flomo_cli.client import _generate_sign


def test_sign_known_example():
    """Verified example from flomo-api-analysis.md."""
    params = {
        "timestamp": "1773669997",
        "api_key": "flomo_web",
        "app_version": "4.0",
        "platform": "web",
        "webp": "1",
    }
    assert _generate_sign(params) == "e8749f38dfc1fcdd1582d34a0c7759f0"


def test_sign_skips_none():
    params = {"api_key": "flomo_web", "extra": None}
    result = _generate_sign(params)
    # 'extra' must not appear in the hash input
    params_without = {"api_key": "flomo_web"}
    assert result == _generate_sign(params_without)


def test_sign_skips_empty_string():
    params = {"api_key": "flomo_web", "empty": ""}
    result = _generate_sign(params)
    params_without = {"api_key": "flomo_web"}
    assert result == _generate_sign(params_without)


def test_sign_keeps_zero_int():
    """Integer zero should be included (JS: `0 === 0` is truthy)."""
    params = {"pin": 0, "api_key": "flomo_web"}
    result = _generate_sign(params)
    # Must differ from a sign where pin is absent
    params_without_pin = {"api_key": "flomo_web"}
    assert result != _generate_sign(params_without_pin)


def test_sign_sorted_keys():
    """Order of params should not matter — sign is always sorted."""
    p1 = {"b": "2", "a": "1"}
    p2 = {"a": "1", "b": "2"}
    assert _generate_sign(p1) == _generate_sign(p2)


def test_sign_list_param_order_independent_and_skips_none():
    """List params should sort items and skip None entries."""
    p1 = {"api_key": "flomo_web", "tags": ["beta", None, "alpha"]}
    p2 = {"api_key": "flomo_web", "tags": ["alpha", "beta"]}
    assert _generate_sign(p1) == _generate_sign(p2)


def test_sign_list_param_affects_hash():
    """Presence of list param should change sign value."""
    with_tags = {"api_key": "flomo_web", "tags": ["alpha"]}
    without_tags = {"api_key": "flomo_web"}
    assert _generate_sign(with_tags) != _generate_sign(without_tags)
