"""Independent hand-calculated RMSSD tests."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.garden.input_layer.rmssd import calculate_rmssd_ms


def test_rmssd_matches_an_independently_hand_calculated_fixture() -> None:
    # Differences are 30 ms and 40 ms: sqrt((30^2 + 40^2) / 2).
    expected_ms = math.sqrt(1_250.0)

    assert calculate_rmssd_ms((800_000, 830_000, 870_000)) == pytest.approx(expected_ms)


@pytest.mark.parametrize("values", ((), (800_000,)))
def test_fewer_than_two_rri_values_produces_none(values: tuple[int, ...]) -> None:
    assert calculate_rmssd_ms(values) is None


def test_microseconds_are_converted_to_milliseconds_after_root_mean_square() -> None:
    # A single adjacent difference of 65,000 us is exactly 65 ms.
    assert calculate_rmssd_ms((800_000, 865_000)) == 65.0


def test_rmssd_uses_the_supplied_sequence_order() -> None:
    chronological = calculate_rmssd_ms((800_000, 830_000, 870_000))
    reordered = calculate_rmssd_ms((800_000, 870_000, 830_000))

    assert chronological == pytest.approx(math.sqrt(1_250.0))
    assert reordered == pytest.approx(math.sqrt(3_250.0))
    assert reordered != chronological


@pytest.mark.parametrize("values", ((True, 800_000), (800.0, 900_000), ("800000", 900_000)))
def test_rmssd_inputs_must_be_integer_microseconds(values: tuple[object, ...]) -> None:
    with pytest.raises(TypeError, match="integers"):
        calculate_rmssd_ms(values)  # type: ignore[arg-type]


@pytest.mark.parametrize("values", ((0, 800_000), (-1, 800_000)))
def test_rmssd_inputs_must_be_positive(values: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="positive"):
        calculate_rmssd_ms(values)
