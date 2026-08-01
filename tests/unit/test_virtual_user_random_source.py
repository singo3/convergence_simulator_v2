"""Reference and invariance tests for stateless named SHA-256 random values."""

from __future__ import annotations

import inspect

import pytest

from symbiotic_sim_v2.virtual_user import random_source
from symbiotic_sim_v2.virtual_user.random_source import standard_normal, uniform01


def test_canonical_uniform_reference_values() -> None:
    assert uniform01(20260802, "correlated_innovation", 0) == pytest.approx(
        0.09548367462478982,
        abs=1e-16,
    )
    assert uniform01(20260802, "beat_jitter", 17) == pytest.approx(
        0.2950067783269705,
        abs=1e-16,
    )


def test_canonical_normal_reference_values() -> None:
    assert standard_normal(20260802, "correlated_innovation", 0) == pytest.approx(
        -2.112529329815411,
        abs=1e-15,
    )
    assert standard_normal(20260802, "beat_jitter", 17) == pytest.approx(
        1.5333084554840202,
        abs=1e-15,
    )


def test_uniform_is_strictly_open_interval() -> None:
    values = [uniform01(4, "stream", index) for index in range(100)]
    assert all(0.0 < value < 1.0 for value in values)


def test_extreme_digest_chunks_are_still_strictly_open() -> None:
    assert 0.0 < random_source._open_uniform(bytes(8)) < 1.0
    assert 0.0 < random_source._open_uniform(b"\xff" * 8) < 1.0


def test_same_key_is_repeatable() -> None:
    first = standard_normal(77, "stream", 19)
    assert standard_normal(77, "stream", 19) == first


def test_stream_and_index_names_separate_values() -> None:
    base = standard_normal(77, "stream-a", 1)
    assert standard_normal(77, "stream-b", 1) != base
    assert standard_normal(77, "stream-a", 2) != base


def test_call_order_does_not_change_results() -> None:
    keys = [(9, "a", 0), (9, "b", 3), (9, "a", 8)]
    forward = {key: standard_normal(*key) for key in keys}
    reverse = {key: standard_normal(*key) for key in reversed(keys)}
    assert forward == reverse


def test_no_python_hash_or_global_rng_is_used() -> None:
    source = inspect.getsource(random_source)
    assert "hash(" not in source
    assert "random." not in source
    assert "numpy" not in source.lower()


@pytest.mark.parametrize(
    "args",
    [(-1, "x", 0), (True, "x", 0), (1, "", 0), (1, "x", -1), (1, "x", True)],
)
def test_invalid_random_keys_are_rejected(args) -> None:
    with pytest.raises(ValueError):
        uniform01(*args)
