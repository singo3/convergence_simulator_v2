"""Immutable diagnostics for the Stage 5B connected second round."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION = (
    "digital_life_second_round_record_v1"
)
K_UPDATE_STATUS_DEFERRED = "deferred_to_stage_5c"


@dataclass(frozen=True, slots=True)
class DigitalLifeSecondRoundRecord:
    signal_index: int
    signal_time_us: int
    digital_life_id: str
    role: str
    s: int
    qualification_holder_id: str | None
    g: int
    first_round_b: tuple[float, float, float, float]
    returned_b: tuple[float, float, float, float] | None
    b_match: bool
    attribution_source: str
    is_new_valid_evaluation: bool
    evaluation_id: str | None
    evaluation_kind: str | None
    evaluation_quality: str | None
    w: float
    e_before: float
    e_after: float
    e_updated: bool
    q_before: float
    q_after: float
    q_update_applied: bool
    q_skip_reason: str
    k_before: tuple[float, float, float, float]
    k_after: tuple[float, float, float, float]
    k_update_status: str
    closing_evaluation_attribution: bool
    holder_release_pending: bool
    first_round_completed: bool
    schema_version: str = DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ConnectedDigitalLifeSnapshot:
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
    qualification_holder_id: str | None
    current_g: int
    holder_matches: bool
    latest_touch_time_us: int | None
    latest_returned_b: tuple[float, float, float, float] | None
    latest_attribution_source: str | None
    first_round_count: int
    second_round_count: int
    evaluation_update_count: int
    new_valid_evaluation_count: int
    q_update_count: int
    k_update_count: int
    touch_dispatched_count: int
    first_round_completed: bool
    second_round_completed: bool
    pending_signal_index: int | None
