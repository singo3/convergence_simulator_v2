"""Wilson interval and continuous descriptive-statistic tests."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.uncertainty import (
    continuous_summary,
    wilson_interval,
)


@pytest.mark.parametrize(
    ("successes", "total", "expected_rate", "lower", "upper"),
    (
        (0, 0, None, None, None),
        (0, 10, 0.0, 0.0, 0.277533),
        (10, 10, 1.0, 0.722467, 1.0),
        (5, 10, 0.5, 0.236593, 0.763407),
        (1, 1, 1.0, 0.206549, 1.0),
    ),
)
def test_wilson_fixtures(successes, total, expected_rate, lower, upper) -> None:
    result = wilson_interval(successes, total)
    assert result["rate"] == expected_rate
    if lower is None:
        assert result["lower95"] is result["upper95"] is None
    else:
        assert result["lower95"] == pytest.approx(lower, abs=1e-6)
        assert result["upper95"] == pytest.approx(upper, abs=1e-6)


@pytest.mark.parametrize(
    ("successes", "total"),
    ((-1, 2), (3, 2), (0, -1), (True, 1), (1, False)),
)
def test_wilson_rejects_invalid_counts(successes, total) -> None:
    with pytest.raises((TypeError, ValueError)):
        wilson_interval(successes, total)


def test_continuous_summary_empty() -> None:
    assert continuous_summary((None,)) == {
        "count": 0,
        "mean": None,
        "median": None,
        "min": None,
        "max": None,
        "q1": None,
        "q3": None,
    }


@pytest.mark.parametrize(
    ("values", "median", "q1", "q3"),
    (
        ((2,), 2.0, 2.0, 2.0),
        ((1, 2), 1.5, 1.25, 1.75),
        ((1, 2, 3, 4), 2.5, 1.75, 3.25),
        ((4, None, 1, 3, 2), 2.5, 1.75, 3.25),
    ),
)
def test_continuous_summary_quantiles(values, median, q1, q3) -> None:
    result = continuous_summary(values)
    assert result["median"] == median
    assert result["q1"] == q1
    assert result["q3"] == q3
    assert result["min"] == 1.0 or len(values) == 1


def test_continuous_summary_has_all_requested_fields() -> None:
    result = continuous_summary((1, 2, 7))
    assert result == {
        "count": 3,
        "mean": pytest.approx(10 / 3),
        "median": 2.0,
        "min": 1.0,
        "max": 7.0,
        "q1": 1.5,
        "q3": 4.5,
    }
