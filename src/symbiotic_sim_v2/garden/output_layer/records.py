"""Immutable Stage 5B Garden qualification diagnostics and snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

type BVector = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class GardenTouchRecord:
    signal_index: int
    signal_time_us: int
    arrival_order: int
    arrival_time_us: int
    digital_life_id: str
    b: BVector
    holder_before: str | None
    holder_after: str | None
    assigned_holder_on_this_touch: bool
    exact_time_tie: bool
    tie_break_policy: str
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GardenQualifiedBRecord:
    garden_id: str
    signal_index: int
    signal_time_us: int
    effective_time_us: int
    s: int
    active: bool
    qualification_holder_id: str | None
    b: BVector | None
    emission_policy_version: str
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GardenFeedbackRecord:
    garden_id: str
    recipient_digital_life_id: str
    signal_index: int
    signal_time_us: int
    s: int
    qualification_holder_id: str | None
    returned_b: BVector | None
    attribution_source: str
    closing_evaluation_attribution: bool
    schema_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GardenQualificationRecord:
    signal_index: int
    signal_time_us: int
    s: int
    holder_before: str | None
    holder_after: str | None
    assigned_this_signal: bool
    assignment_touch_time_us: int | None
    assignment_touch_id: str | None
    held_from_previous_signal: bool
    released_after_second_round: bool
    touch_order: tuple[str, ...]
    qualified_b: BVector | None
    active_output: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GardenOutputSnapshot:
    garden_id: str
    model_version: str
    qualification_state_schema_version: str
    current_signal_index: int | None
    current_s: int | None
    qualification_holder_id: str | None
    last_assigned_holder_id: str | None
    qualification_assigned_signal_index: int | None
    qualification_assignment_time_us: int | None
    holder_active: bool
    round_open: bool
    closing_release_pending: bool
    touch_count_current_round: int
    total_touch_count: int
    active_output_count: int
    inactive_output_count: int
    feedback_count: int
    assignment_count: int
    release_count: int
    incomplete_round_count: int
    qualification_record_count: int
    latest_qualified_b: BVector | None
    latest_qualified_b_effective_time_us: int | None
    latest_active_qualified_b_effective_time_us: int | None
    latest_active_holder_touch_time_us: int | None
    latest_active_qualified_b_delay_us: int | None
    qualified_b_emission_policy_version: str
    latest_touch_order: tuple[str, ...]
