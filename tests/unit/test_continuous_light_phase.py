"""Pure analytic phase and sine-wave reference checks."""

from __future__ import annotations

import math

import pytest

from symbiotic_sim_v2.devices.virtual_light.phase import (
    normalize_phase_cycles,
    phase_cycles_at,
)
from symbiotic_sim_v2.devices.virtual_light.waveform import sine_value


@pytest.mark.parametrize(
    ("time_us", "expected_phase"),
    (
        (0, 0.0),
        (250_000, 0.25),
        (500_000, 0.5),
        (750_000, 0.75),
        (1_000_000, 0.0),
        (123_250_000, 0.25),
    ),
)
def test_phase_is_evaluated_directly_from_integer_virtual_time(
    time_us: int,
    expected_phase: float,
) -> None:
    assert phase_cycles_at(
        time_us,
        start_time_us=0,
        phase_cycles_at_start=0.0,
        blink_bpm=60.0,
    ) == pytest.approx(expected_phase, abs=1e-12)


@pytest.mark.parametrize(
    ("phase", "expected_value"),
    (
        (0.0, 0.425),
        (0.25, 0.50),
        (0.5, 0.425),
        (0.75, 0.35),
        (1.0, 0.425),
    ),
)
def test_sine_value_matches_reference_cardinal_phases(
    phase: float,
    expected_value: float,
) -> None:
    assert sine_value(
        phase,
        value_center=0.425,
        value_amplitude=0.075,
    ) == pytest.approx(expected_value, abs=1e-12)


def test_nonzero_origin_and_phase_are_not_reset_by_query() -> None:
    assert phase_cycles_at(
        12_000_000,
        start_time_us=10_000_000,
        phase_cycles_at_start=0.2,
        blink_bpm=90.0,
    ) == pytest.approx(0.2)
    assert normalize_phase_cycles(-0.25) == pytest.approx(0.75)


@pytest.mark.parametrize(
    ("kwargs", "error"),
    (
        (
            {
                "time_us": True,
                "start_time_us": 0,
                "phase_cycles_at_start": 0.0,
                "blink_bpm": 60.0,
            },
            TypeError,
        ),
        (
            {
                "time_us": 0,
                "start_time_us": 1,
                "phase_cycles_at_start": 0.0,
                "blink_bpm": 60.0,
            },
            ValueError,
        ),
        (
            {
                "time_us": 0,
                "start_time_us": 0,
                "phase_cycles_at_start": 1.0,
                "blink_bpm": 60.0,
            },
            ValueError,
        ),
        (
            {
                "time_us": 0,
                "start_time_us": 0,
                "phase_cycles_at_start": 0.0,
                "blink_bpm": 0.0,
            },
            ValueError,
        ),
        (
            {
                "time_us": 0,
                "start_time_us": 0,
                "phase_cycles_at_start": 0.0,
                "blink_bpm": math.nan,
            },
            ValueError,
        ),
    ),
)
def test_phase_rejects_bool_reverse_invalid_phase_bpm_and_nan(
    kwargs: dict[str, object],
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        phase_cycles_at(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("phase", "center", "amplitude"),
    (
        (True, 0.425, 0.075),
        (math.nan, 0.425, 0.075),
        (0.0, -0.1, 0.075),
        (0.0, 0.425, -0.1),
        (0.0, 0.95, 0.1),
    ),
)
def test_waveform_rejects_nonfinite_bool_and_invalid_value_range(
    phase: object,
    center: object,
    amplitude: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        sine_value(
            phase,  # type: ignore[arg-type]
            value_center=center,  # type: ignore[arg-type]
            value_amplitude=amplitude,  # type: ignore[arg-type]
        )
