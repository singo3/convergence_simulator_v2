"""Half-open Garden phase, S, window, and schedule-boundary tests."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.garden.input_layer.config import GardenInputConfig
from symbiotic_sim_v2.garden.input_layer.phases import (
    GardenEvaluationKind,
    GardenPhase,
    GardenWindowRole,
)
from symbiotic_sim_v2.garden.input_layer.timing import (
    evaluation_windows,
    phase_at,
    phase_change_times_us,
)


@pytest.mark.parametrize(
    (
        "time_us",
        "phase",
        "bundle_index",
        "role",
        "nominal_s",
        "evaluation_id",
    ),
    (
        (0, GardenPhase.BASELINE_DISCARD, None, GardenWindowRole.DISCARD, 0, None),
        (
            29_999_999,
            GardenPhase.BASELINE_DISCARD,
            None,
            GardenWindowRole.DISCARD,
            0,
            None,
        ),
        (
            30_000_000,
            GardenPhase.BASELINE_EVALUATION,
            None,
            GardenWindowRole.EVALUATION,
            0,
            "session-001-baseline",
        ),
        (
            59_999_999,
            GardenPhase.BASELINE_EVALUATION,
            None,
            GardenWindowRole.EVALUATION,
            0,
            "session-001-baseline",
        ),
        (60_000_000, GardenPhase.BUNDLE_0_DISCARD, 0, GardenWindowRole.DISCARD, 1, None),
        (
            90_000_000,
            GardenPhase.BUNDLE_0_EVALUATION,
            0,
            GardenWindowRole.EVALUATION,
            1,
            "session-001-bundle-0",
        ),
        (120_000_000, GardenPhase.BUNDLE_1_DISCARD, 1, GardenWindowRole.DISCARD, 1, None),
        (
            150_000_000,
            GardenPhase.BUNDLE_1_EVALUATION,
            1,
            GardenWindowRole.EVALUATION,
            1,
            "session-001-bundle-1",
        ),
        (180_000_000, GardenPhase.BUNDLE_2_DISCARD, 2, GardenWindowRole.DISCARD, 1, None),
        (
            210_000_000,
            GardenPhase.BUNDLE_2_EVALUATION,
            2,
            GardenWindowRole.EVALUATION,
            1,
            "session-001-bundle-2",
        ),
        (
            239_999_999,
            GardenPhase.BUNDLE_2_EVALUATION,
            2,
            GardenWindowRole.EVALUATION,
            1,
            "session-001-bundle-2",
        ),
        (240_000_000, GardenPhase.OUTSIDE, None, GardenWindowRole.OUTSIDE, 0, None),
    ),
)
def test_phase_at_uses_one_shared_half_open_boundary_classification(
    time_us: int,
    phase: GardenPhase,
    bundle_index: int | None,
    role: GardenWindowRole,
    nominal_s: int,
    evaluation_id: str | None,
) -> None:
    descriptor = phase_at(time_us, GardenInputConfig())

    assert descriptor.phase is phase
    assert descriptor.bundle_index == bundle_index
    assert descriptor.window_role is role
    assert descriptor.nominal_s == nominal_s
    assert descriptor.evaluation_id == evaluation_id


def test_evaluation_descriptors_have_exact_half_open_windows() -> None:
    config = GardenInputConfig()
    expected = {
        "session-001-baseline": (30_000_000, 60_000_000),
        "session-001-bundle-0": (90_000_000, 120_000_000),
        "session-001-bundle-1": (150_000_000, 180_000_000),
        "session-001-bundle-2": (210_000_000, 240_000_000),
    }

    for time_us in (30_000_000, 59_999_999, 90_000_000, 119_999_999):
        descriptor = phase_at(time_us, config)
        assert (descriptor.window_start_us, descriptor.window_end_us) == expected[
            descriptor.evaluation_id
        ]


def test_phase_schedule_has_exactly_nine_unique_boundaries() -> None:
    assert phase_change_times_us(GardenInputConfig()) == (
        0,
        30_000_000,
        60_000_000,
        90_000_000,
        120_000_000,
        150_000_000,
        180_000_000,
        210_000_000,
        240_000_000,
    )


def test_signal_grid_has_241_points_including_both_session_ends() -> None:
    config = GardenInputConfig()
    signal_times = tuple(
        range(0, config.total_duration_seconds * 1_000_000 + 1, config.signal_interval_us)
    )

    assert len(signal_times) == 241
    assert signal_times[0] == 0
    assert signal_times[-1] == 240_000_000
    assert all(phase_at(time_us, config).nominal_s == 0 for time_us in signal_times[:60])
    assert all(phase_at(time_us, config).nominal_s == 1 for time_us in signal_times[60:240])
    assert phase_at(signal_times[240], config).nominal_s == 0


def test_evaluation_windows_are_exactly_baseline_then_three_bundles() -> None:
    windows = evaluation_windows(GardenInputConfig())

    assert [window.evaluation_kind for window in windows] == [
        GardenEvaluationKind.BASELINE,
        GardenEvaluationKind.BUNDLE,
        GardenEvaluationKind.BUNDLE,
        GardenEvaluationKind.BUNDLE,
    ]
    assert [window.bundle_index for window in windows] == [None, 0, 1, 2]
    assert [
        (window.window_start_us, window.window_end_us) for window in windows
    ] == [
        (30_000_000, 60_000_000),
        (90_000_000, 120_000_000),
        (150_000_000, 180_000_000),
        (210_000_000, 240_000_000),
    ]


@pytest.mark.parametrize("time_us", (True, 1.0, "1"))
def test_phase_time_requires_integer_microseconds(time_us: object) -> None:
    with pytest.raises(TypeError, match="integer"):
        phase_at(time_us, GardenInputConfig())  # type: ignore[arg-type]


def test_negative_phase_time_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        phase_at(-1, GardenInputConfig())
