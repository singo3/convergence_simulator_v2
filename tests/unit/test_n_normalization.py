"""Fixed RMSSD-to-N equation tests without production-derived expectations."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.garden.input_layer.normalization import normalize_rmssd_to_n


@pytest.mark.parametrize(
    ("rmssd_ms", "expected_n"),
    ((15.0, 0.0), (47.5, 0.5), (80.0, 1.0), (10.0, 0.0), (100.0, 1.0)),
)
def test_fixed_clipped_linear_n_mapping(rmssd_ms: float, expected_n: float) -> None:
    assert normalize_rmssd_to_n(rmssd_ms) == expected_n


def test_n_uses_only_rmssd_and_fixed_endpoints() -> None:
    assert normalize_rmssd_to_n(31.25, 15.0, 80.0) == 0.25
    assert normalize_rmssd_to_n(31.25, 0.0, 100.0) == 0.3125


@pytest.mark.parametrize(
    "values",
    ((True,), ("47.5",), (float("nan"),), (float("inf"),), (47.5, 80.0, 15.0)),
)
def test_normalization_rejects_invalid_numeric_inputs(values: tuple[object, ...]) -> None:
    with pytest.raises((TypeError, ValueError)):
        normalize_rmssd_to_n(*values)  # type: ignore[arg-type]
