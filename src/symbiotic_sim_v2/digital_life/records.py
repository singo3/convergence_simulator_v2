"""Immutable Stage 5A diagnostics and snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

DIGITAL_LIFE_FIRST_ROUND_RECORD_SCHEMA_VERSION = (
    "digital_life_first_round_record_v1"
)
DIGITAL_LIFE_EVALUATION_UPDATE_RECORD_SCHEMA_VERSION = (
    "digital_life_evaluation_update_record_v1"
)


@dataclass(frozen=True, slots=True)
class DigitalLifeFirstRoundRecord:
    signal_index: int
    signal_time_us: int
    digital_life_id: str
    role: str
    phase: str
    bundle_index: int | None
    window_role: str
    session_status: str
    s: int
    n_current: float | None
    n_available: bool
    n_baseline_session: float | None
    baseline_available: bool
    valid_evaluation_revision: int
    is_new_valid_evaluation: bool
    source_evaluation_id: str | None
    source_evaluation_kind: str | None
    source_evaluation_quality: str | None
    nd: float
    w: float
    p: float
    p_intrinsic: float
    e: float
    q: float
    v: float | None
    k_anchor: tuple[float, float, float, float]
    k_current: tuple[float, float, float, float]
    b_f: float
    b_a: float
    b_t: float
    b_d: float
    tau: float | None
    birth_phase: float
    touch_enabled: bool
    touch_dispatched: bool
    second_round_connected: bool
    g_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DigitalLifeEvaluationUpdateRecord:
    evaluation_id: str
    evaluation_kind: str
    bundle_index: int | None
    event_time_us: int
    quality: str
    is_valid: bool
    n_revision: int
    n: float | None
    n_baseline_session: float | None
    previous_nd: float
    new_nd: float
    previous_w: float
    new_w: float
    applied: bool
    skip_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DigitalLifeSnapshot:
    digital_life_id: str
    role: str
    model_version: str
    n_current: float | None
    n_baseline_session: float | None
    baseline_initialized: bool
    nd: float
    w: float
    p: float
    p_intrinsic: float
    e: float
    q: float
    v: float | None
    k_anchor: tuple[float, float, float, float]
    k_current: tuple[float, float, float, float]
    b: tuple[float, float, float, float]
    tau: float | None
    birth_phase: float
    last_signal_index: int | None
    last_revision: int
    latest_s: int | None
    latest_evaluation_id: str | None
    first_round_count: int
    evaluation_update_count: int
    new_valid_evaluation_count: int
    g_status: str
    second_round_connected: bool
    touch_dispatched_count: int
