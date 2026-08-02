"""Raw-RRI absolute and trailing-median artifact policy tests."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.garden.input_layer.artifact_filter import classify_rri
from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig


@pytest.mark.parametrize(
    ("rri_us", "artifact", "reason"),
    (
        (299_999, True, "too_short"),
        (300_000, False, None),
        (2_000_000, False, None),
        (2_000_001, True, "too_long"),
    ),
)
def test_absolute_range_is_inclusive_and_raw(
    rri_us: int,
    artifact: bool,
    reason: str | None,
) -> None:
    decision = classify_rri(rri_us, (), GardenInputConfig())

    assert decision.artifact is artifact
    assert decision.artifact_reason == reason


def test_absolute_artifact_value_is_neither_clipped_nor_interpolated() -> None:
    raw_rri_us = 299_999
    history = (800_000, 900_000, 1_000_000, 1_100_000, 1_200_000)
    before = tuple(history)

    decision = classify_rri(raw_rri_us, history, GardenInputConfig())

    assert raw_rri_us == 299_999
    assert decision.artifact_reason == "too_short"
    assert history == before
    assert decision.median_rri_us_before is None
    assert decision.relative_deviation is None


def test_four_valid_history_values_do_not_enable_median_classification() -> None:
    decision = classify_rri(2_000_000, (1_000_000,) * 4, GardenInputConfig())

    assert decision.median_history_count_before == 4
    assert decision.median_rri_us_before is None
    assert decision.relative_deviation is None
    assert not decision.artifact


def test_five_valid_history_values_enable_median_classification() -> None:
    decision = classify_rri(1_100_000, (1_000_000,) * 5, GardenInputConfig())

    assert decision.median_history_count_before == 5
    assert decision.median_rri_us_before == 1_000_000.0
    assert decision.relative_deviation == pytest.approx(0.1)
    assert not decision.artifact


@pytest.mark.parametrize(
    ("rri_us", "artifact"),
    ((1_200_000, False), (1_200_001, True), (800_000, False), (799_999, True)),
)
def test_twenty_percent_median_boundary_is_inclusive(rri_us: int, artifact: bool) -> None:
    decision = classify_rri(rri_us, (1_000_000,) * 5, GardenInputConfig())

    assert decision.artifact is artifact
    assert decision.artifact_reason == ("median_deviation" if artifact else None)


def test_only_the_trailing_fifteen_valid_values_are_used() -> None:
    history = (1_100_000,) + (1_000_000,) * 8 + (1_200_000,) * 7
    decision = classify_rri(1_200_001, history, GardenInputConfig())

    assert len(history) == 16
    assert decision.median_history_count_before == 15
    assert decision.median_rri_us_before == 1_000_000.0
    assert decision.artifact


def test_current_rri_is_not_inserted_before_median_is_calculated() -> None:
    history = (800_000, 800_000, 800_000, 1_000_000, 1_000_000)
    decision = classify_rri(1_000_000, history, GardenInputConfig())

    assert decision.median_rri_us_before == 800_000.0
    assert decision.relative_deviation == pytest.approx(0.25)
    assert decision.artifact


@pytest.mark.parametrize("rri_us", (True, 800.0, "800000"))
def test_rri_requires_positive_integer_microseconds(rri_us: object) -> None:
    with pytest.raises(TypeError, match="integer"):
        classify_rri(rri_us, (), GardenInputConfig())  # type: ignore[arg-type]


@pytest.mark.parametrize("rri_us", (0, -1))
def test_nonpositive_rri_is_rejected(rri_us: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        classify_rri(rri_us, (), GardenInputConfig())


@pytest.mark.parametrize("history", ((1_000_000, True), (0,), (-1,), (800_000.0,)))
def test_history_requires_positive_integer_microseconds(history: tuple[object, ...]) -> None:
    with pytest.raises(ValueError, match="history"):
        classify_rri(800_000, history, GardenInputConfig())  # type: ignore[arg-type]
