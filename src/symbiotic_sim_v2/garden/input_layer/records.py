"""Immutable Garden classification, evaluation, signal, and snapshot values."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GardenRriRecord:
    input_measurement_index: int
    input_event_id: str
    event_time_us: int
    device_id: str
    user_id: str
    raw_rri_us: int
    raw_rri_ms: float
    phase: str
    bundle_index: int | None
    window_role: str
    evaluation_id: str | None
    artifact: bool
    artifact_reason: str | None
    median_history_count_before: int
    median_rri_us_before: float | None
    relative_deviation: float | None
    accepted_into_valid_history: bool
    included_in_evaluation_window: bool
    membership_policy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GardenEvaluationRecord:
    evaluation_id: str
    evaluation_kind: str
    bundle_index: int | None
    window_start_us: int
    window_end_us: int
    total_rri_count: int
    artifact_rri_count: int
    valid_rri_count: int
    artifact_rate: float
    rmssd_ms: float | None
    n: float | None
    quality: str
    is_valid: bool
    reject_reasons: tuple[str, ...]
    n_revision: int
    baseline_id: str | None
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GardenInputSignalRecord:
    garden_id: str
    session_id: str
    signal_index: int
    signal_time_us: int
    s: int
    phase: str
    bundle_index: int | None
    window_role: str
    n_current: float | None
    n_available: bool
    n_baseline_session: float | None
    baseline_available: bool
    latest_valid_evaluation_id: str | None
    valid_evaluation_revision: int
    session_status: str
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GardenInputSnapshot:
    garden_id: str
    model_version: str
    session_id: str
    session_status: str
    current_phase: str
    current_s: int
    current_bundle_index: int | None
    current_window_role: str
    received_rri_count: int
    valid_rri_count: int
    artifact_rri_count: int
    recent_valid_history_count: int
    n_baseline_session: float | None
    n_current: float | None
    baseline_available: bool
    latest_rmssd_ms: float | None
    latest_evaluation_quality: str | None
    latest_evaluation_id: str | None
    valid_evaluation_revision: int
    signal_count: int
    evaluation_count: int
