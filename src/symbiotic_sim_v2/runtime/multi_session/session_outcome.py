"""Immutable representative outcome for one completed or failed Stage 8A session."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from types import MappingProxyType
from typing import Any

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.hash01 import hash01
from symbiotic_sim_v2.digital_life.math import (
    calculate_nd,
    evaluate_w,
    intrinsic_b_mapping,
)
from symbiotic_sim_v2.digital_life.relation_memory.adaptive_component import (
    AdaptiveConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.relation_memory.candidate import generate_candidate
from symbiotic_sim_v2.digital_life.relation_memory.config import (
    ADOPTION_RESULTS,
    EXPLORATION_DECISIONS,
)
from symbiotic_sim_v2.digital_life.relation_memory.direction import (
    derive_search_direction,
)
from symbiotic_sim_v2.digital_life.relation_memory.intrinsic import (
    derive_relation_memory_intrinsic_profile,
    exploration_decision,
    exploration_probability,
    exploration_sigma,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.garden.input_layer.records import GardenEvaluationRecord
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.mapping import map_active_b_to_light
from symbiotic_sim_v2.runtime.adaptive_closed_loop.relation_memory_scenario import (
    AdaptiveRelationMemoryClosedLoopSimulation,
    adaptive_digital_life_components,
)
from symbiotic_sim_v2.runtime.multi_life.touch_delivery import (
    MAX_TOUCH_OFFSET_US,
    MIN_TOUCH_OFFSET_US,
)
from symbiotic_sim_v2.simulation.clock import ClockState

from .session_seed import SESSION_DURATION_US, UINT32_MAX, global_time_us

MULTI_SESSION_OUTCOME_SCHEMA_VERSION = "multi_session_outcome_v1"
BUNDLE_PRESENTATION_SCHEMA_VERSION = "bundle_light_presentation_v1"
KVector = tuple[float, float, float, float]
_ROLES = {"red", "green", "blue"}


def _strict_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate session outcome field: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _optional_text(name: str, value: object | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string or null")
    return value


def _finite(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _unit(name: str, value: object) -> float:
    number = _finite(name, value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return number


def _optional_unit(name: str, value: object | None) -> float | None:
    return None if value is None else _unit(name, value)


def _vector(name: str, value: object) -> KVector:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{name} must be a four-element sequence")
    if len(value) != 4:
        raise ValueError(f"{name} must contain four values")
    return tuple(_unit(f"{name}[{index}]", item) for index, item in enumerate(value))  # type: ignore[return-value]


def _optional_finite(name: str, value: object | None) -> float | None:
    return None if value is None else _finite(name, value)


def _vector_map(name: str, value: object) -> Mapping[str, KVector]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, KVector] = {}
    for life_id, vector in value.items():
        if not isinstance(life_id, str) or not life_id.strip():
            raise ValueError(f"{name} keys must be non-empty Digital Life IDs")
        result[life_id] = _vector(f"{name}[{life_id}]", vector)
    return MappingProxyType(result)


def _counter_map(name: str, value: object) -> Mapping[str, int]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, int] = {}
    for life_id, count in value.items():
        if not isinstance(life_id, str) or not life_id.strip():
            raise ValueError(f"{name} keys must be non-empty Digital Life IDs")
        result[life_id] = _non_negative_int(f"{name}[{life_id}]", count)
    return MappingProxyType(result)


def _persistent_state_map(
    name: str,
    value: object,
) -> Mapping[str, RelationMemoryPersistentState]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, RelationMemoryPersistentState] = {}
    for life_id, raw_state in value.items():
        if not isinstance(life_id, str) or not life_id.strip():
            raise ValueError(f"{name} keys must be non-empty Digital Life IDs")
        state = (
            raw_state
            if isinstance(raw_state, RelationMemoryPersistentState)
            else RelationMemoryPersistentState.from_dict(
                raw_state,
                expected_digital_life_id=life_id,
            )
        )
        if state.digital_life_id != life_id:
            raise ValueError(f"{name} state ID differs from its mapping key")
        result[life_id] = state
    return MappingProxyType(result)


def _evaluation(
    name: str,
    value: object | None,
    *,
    kind: str,
    bundle_index: int | None,
) -> GardenEvaluationRecord | None:
    if value is None:
        return None
    if isinstance(value, GardenEvaluationRecord):
        record = value
    else:
        if not isinstance(value, Mapping):
            raise TypeError(f"{name} must be a GardenEvaluationRecord or mapping")
        expected = set(GardenEvaluationRecord.__dataclass_fields__)
        actual = set(value)
        if actual != expected:
            raise ValueError(
                f"{name} fields differ; missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        normalized = dict(value)
        reject_reasons = normalized.get("reject_reasons")
        if isinstance(reject_reasons, list):
            normalized["reject_reasons"] = tuple(reject_reasons)
        record = GardenEvaluationRecord(**normalized)
    if record.evaluation_kind != kind or record.bundle_index != bundle_index:
        raise ValueError(f"{name} has the wrong evaluation kind or bundle index")
    return record


@dataclass(frozen=True, slots=True)
class BundleLightPresentation:
    """One contiguous, actually emitted physical pattern inside a Bundle."""

    session_index: int
    bundle_index: int
    first_signal_index: int
    last_signal_index: int
    first_effective_time_us: int
    last_effective_time_us: int
    first_global_time_us: int
    last_global_time_us: int
    holder_id: str
    k_presented: KVector
    b_presented: KVector
    hue_degree: float
    blink_bpm: float
    mapping_version: str
    schema_version: str = BUNDLE_PRESENTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        session_index = _non_negative_int("session_index", self.session_index)
        bundle = _non_negative_int("bundle_index", self.bundle_index)
        if bundle > 2:
            raise ValueError("bundle_index must be between 0 and 2")
        first_signal = _non_negative_int(
            "first_signal_index", self.first_signal_index
        )
        last_signal = _non_negative_int("last_signal_index", self.last_signal_index)
        expected_first = 60 + 60 * bundle
        expected_last = expected_first + 59
        if not expected_first <= first_signal <= last_signal <= expected_last:
            raise ValueError("presentation signal range lies outside its Bundle")
        first_time = _non_negative_int(
            "first_effective_time_us", self.first_effective_time_us
        )
        last_time = _non_negative_int(
            "last_effective_time_us", self.last_effective_time_us
        )
        if first_time > last_time or last_time > SESSION_DURATION_US:
            raise ValueError("presentation effective-time range is invalid")
        first_signal_time = first_signal * 1_000_000
        last_signal_time = last_signal * 1_000_000
        if not (
            first_signal_time + MIN_TOUCH_OFFSET_US
            <= first_time
            <= first_signal_time + MAX_TOUCH_OFFSET_US
        ):
            raise ValueError(
                "presentation first effective time lies outside its signal interval"
            )
        if not (
            last_signal_time + MIN_TOUCH_OFFSET_US
            <= last_time
            <= last_signal_time + MAX_TOUCH_OFFSET_US
        ):
            raise ValueError(
                "presentation last effective time lies outside its signal interval"
            )
        first_global_time = _non_negative_int(
            "first_global_time_us",
            self.first_global_time_us,
        )
        last_global_time = _non_negative_int(
            "last_global_time_us",
            self.last_global_time_us,
        )
        if first_global_time != global_time_us(session_index, first_time):
            raise ValueError("presentation first global time differs from local time")
        if last_global_time != global_time_us(session_index, last_time):
            raise ValueError("presentation last global time differs from local time")
        holder = _optional_text("holder_id", self.holder_id)
        assert holder is not None
        k = _vector("k_presented", self.k_presented)
        b = _vector("b_presented", self.b_presented)
        hue = _finite("hue_degree", self.hue_degree)
        bpm = _finite("blink_bpm", self.blink_bpm)
        if not 0.0 <= hue <= 360.0:
            raise ValueError("presentation Hue must be between 0 and 360")
        if not 10.0 <= bpm <= 165.0:
            raise ValueError("presentation BPM must be between 10 and 165")
        mapping_version = _optional_text("mapping_version", self.mapping_version)
        assert mapping_version is not None
        if self.schema_version != BUNDLE_PRESENTATION_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {BUNDLE_PRESENTATION_SCHEMA_VERSION}"
            )
        for name, value in {
            "session_index": session_index,
            "bundle_index": bundle,
            "first_signal_index": first_signal,
            "last_signal_index": last_signal,
            "first_effective_time_us": first_time,
            "last_effective_time_us": last_time,
            "first_global_time_us": first_global_time,
            "last_global_time_us": last_global_time,
            "holder_id": holder,
            "k_presented": k,
            "b_presented": b,
            "hue_degree": hue,
            "blink_bpm": bpm,
            "mapping_version": mapping_version,
        }.items():
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_index": self.session_index,
            "bundle_index": self.bundle_index,
            "first_signal_index": self.first_signal_index,
            "last_signal_index": self.last_signal_index,
            "first_effective_time_us": self.first_effective_time_us,
            "last_effective_time_us": self.last_effective_time_us,
            "first_global_time_us": self.first_global_time_us,
            "last_global_time_us": self.last_global_time_us,
            "holder_id": self.holder_id,
            "k_presented": list(self.k_presented),
            "b_presented": list(self.b_presented),
            "hue_degree": self.hue_degree,
            "blink_bpm": self.blink_bpm,
            "mapping_version": self.mapping_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> BundleLightPresentation:
        if not isinstance(values, Mapping):
            raise TypeError("bundle presentation values must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                "bundle presentation fields differ; "
                f"missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        return cls(**dict(values))


def _bundle_presentations(
    value: object,
) -> tuple[BundleLightPresentation, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("bundle_presentations must be a sequence")
    return tuple(
        item
        if isinstance(item, BundleLightPresentation)
        else BundleLightPresentation.from_dict(item)
        for item in value
    )


@dataclass(frozen=True, slots=True)
class SessionOutcome:
    """One session vote; its final committed anchor is the representative pattern."""

    session_index: int
    local_time_us: int
    global_time_us: int
    valid_for_convergence: bool
    invalid_reason: str | None
    engine_completed: bool
    physiology_root_seed: int
    user_type_id: str
    holder_id: str | None
    holder_role: str | None
    initial_k_anchor_by_life: Mapping[str, KVector]
    initial_persistent_state_by_life: Mapping[str, RelationMemoryPersistentState]
    final_k_anchor_by_life: Mapping[str, KVector]
    holder_final_k_anchor: KVector | None
    holder_final_b_f: float | None
    holder_final_b_a: float | None
    holder_final_b_t: float | None
    holder_final_b_d: float | None
    holder_final_hue_degree: float | None
    holder_final_blink_bpm: float | None
    exploration_decision: str | None
    adoption_result: str | None
    candidate_generated: bool
    candidate_accepted: bool
    holder_W_anchor_session: float | None
    holder_W_trial_1: float | None
    holder_W_trial_2: float | None
    baseline_evaluation: GardenEvaluationRecord | None
    bundle_0_evaluation: GardenEvaluationRecord | None
    bundle_1_evaluation: GardenEvaluationRecord | None
    bundle_2_evaluation: GardenEvaluationRecord | None
    session_count_before_by_life: Mapping[str, int]
    session_count_after_by_life: Mapping[str, int]
    trial_count_before_by_life: Mapping[str, int]
    trial_count_after_by_life: Mapping[str, int]
    final_persistent_state_by_life: Mapping[str, RelationMemoryPersistentState]
    bundle_presentations: tuple[BundleLightPresentation, ...]
    session_digest: str | None
    schema_version: str = MULTI_SESSION_OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        index = _non_negative_int("session_index", self.session_index)
        local = _non_negative_int("local_time_us", self.local_time_us)
        aggregate = _non_negative_int("global_time_us", self.global_time_us)
        if local > SESSION_DURATION_US:
            raise ValueError(f"local_time_us must not exceed {SESSION_DURATION_US}")
        if aggregate != global_time_us(index, local):
            raise ValueError("global_time_us does not match session index and local time")
        if not isinstance(self.valid_for_convergence, bool):
            raise TypeError("valid_for_convergence must be boolean")
        if not isinstance(self.engine_completed, bool):
            raise TypeError("engine_completed must be boolean")
        reason = _optional_text("invalid_reason", self.invalid_reason)
        if self.valid_for_convergence and reason is not None:
            raise ValueError("a valid outcome cannot carry invalid_reason")
        if not self.valid_for_convergence and reason is None:
            raise ValueError("an invalid outcome requires invalid_reason")
        if self.valid_for_convergence and not self.engine_completed:
            raise ValueError("a valid outcome requires a completed engine")
        if (
            isinstance(self.physiology_root_seed, bool)
            or not isinstance(self.physiology_root_seed, int)
        ):
            raise TypeError("physiology_root_seed must be an integer")
        if not 0 <= self.physiology_root_seed <= UINT32_MAX:
            raise ValueError("physiology_root_seed must be an unsigned 32-bit integer")
        if not isinstance(self.user_type_id, str) or not self.user_type_id.strip():
            raise ValueError("user_type_id must be a non-empty string")
        holder_id = _optional_text("holder_id", self.holder_id)
        holder_role = _optional_text("holder_role", self.holder_role)
        if (holder_id is None) != (holder_role is None):
            raise ValueError("holder ID and role must both be present or both be null")
        if holder_role is not None and holder_role not in _ROLES:
            raise ValueError("holder_role must be red, green, blue, or null")
        if (
            holder_id is not None
            and holder_role is not None
            and digital_life_config_for_role(holder_role).digital_life_id != holder_id
        ):
            raise ValueError("holder ID and role do not match the fixed roster")

        initial_k = _vector_map("initial_k_anchor_by_life", self.initial_k_anchor_by_life)
        initial_states = _persistent_state_map(
            "initial_persistent_state_by_life",
            self.initial_persistent_state_by_life,
        )
        final_k = _vector_map("final_k_anchor_by_life", self.final_k_anchor_by_life)
        session_before = _counter_map(
            "session_count_before_by_life", self.session_count_before_by_life
        )
        session_after = _counter_map(
            "session_count_after_by_life", self.session_count_after_by_life
        )
        trial_before = _counter_map(
            "trial_count_before_by_life", self.trial_count_before_by_life
        )
        trial_after = _counter_map(
            "trial_count_after_by_life", self.trial_count_after_by_life
        )
        final_states = _persistent_state_map(
            "final_persistent_state_by_life", self.final_persistent_state_by_life
        )
        roster = set(initial_k)
        if len(roster) != 3:
            raise ValueError("SessionOutcome requires exactly three initial life states")
        for name, values in (
            ("initial_persistent_state_by_life", initial_states),
            ("session_count_before_by_life", session_before),
            ("trial_count_before_by_life", trial_before),
        ):
            if set(values) != roster:
                raise ValueError(f"{name} must match the initial roster")
        for life_id, state in initial_states.items():
            if state.k_anchor != initial_k[life_id]:
                raise ValueError("initial state and initial k anchor mapping differ")
            if state.session_count != session_before[life_id]:
                raise ValueError("initial state and session count mapping differ")
            if state.trial_count != trial_before[life_id]:
                raise ValueError("initial state and trial count mapping differ")
        for name, values in (
            ("final_k_anchor_by_life", final_k),
            ("session_count_after_by_life", session_after),
            ("trial_count_after_by_life", trial_after),
            ("final_persistent_state_by_life", final_states),
        ):
            if values and set(values) != roster:
                raise ValueError(f"{name} must be empty or match the initial roster")
        if self.engine_completed and (
            local != SESSION_DURATION_US
            or set(final_k) != roster
            or set(session_after) != roster
            or set(trial_after) != roster
            or set(final_states) != roster
        ):
            raise ValueError(
                "a completed engine requires the 240-second closing and three final states"
            )
        for life_id, state in final_states.items():
            if state.k_anchor != final_k[life_id]:
                raise ValueError("final state and final k anchor mapping differ")
            if state.session_count != session_after[life_id]:
                raise ValueError("final state and session count mapping differ")
            if state.trial_count != trial_after[life_id]:
                raise ValueError("final state and trial count mapping differ")

        holder_anchor = (
            None
            if self.holder_final_k_anchor is None
            else _vector("holder_final_k_anchor", self.holder_final_k_anchor)
        )
        b_values = tuple(
            _optional_unit(name, getattr(self, name))
            for name in (
                "holder_final_b_f",
                "holder_final_b_a",
                "holder_final_b_t",
                "holder_final_b_d",
            )
        )
        hue = _optional_finite("holder_final_hue_degree", self.holder_final_hue_degree)
        bpm = _optional_finite("holder_final_blink_bpm", self.holder_final_blink_bpm)
        physical_values = (*b_values, hue, bpm)
        if holder_id is None:
            if holder_anchor is not None or any(value is not None for value in physical_values):
                raise ValueError("an outcome without a holder cannot carry a pattern")
        else:
            pattern_values = (holder_anchor, *physical_values)
            if any(value is not None for value in pattern_values):
                if any(value is None for value in pattern_values):
                    raise ValueError("a partial holder final pattern is not allowed")
                if holder_id not in final_k or holder_anchor != final_k[holder_id]:
                    raise ValueError("holder final anchor differs from final state mapping")
                assert hue is not None and bpm is not None
                if not 0.0 <= hue <= 360.0:
                    raise ValueError("holder final Hue must be between 0 and 360")
                if not 10.0 <= bpm <= 165.0:
                    raise ValueError("holder final BPM must be between 10 and 165")
                assert holder_role is not None
                holder_config = digital_life_config_for_role(holder_role)
                expected_b = intrinsic_b_mapping(
                    holder_anchor,
                    f_min=holder_config.f_min,
                    f_max=holder_config.f_max,
                    a_fixed=holder_config.a_fixed,
                    t_min=holder_config.t_min,
                    t_max=holder_config.t_max,
                    d_fixed=holder_config.d_fixed,
                )
                if b_values != expected_b:
                    raise ValueError("holder final B differs from its committed k anchor")
                expected_light = map_active_b_to_light(
                    expected_b,
                    GardenLightMapperConfig(),
                )
                if (
                    hue != expected_light.hue_degree
                    or bpm != expected_light.blink_bpm
                ):
                    raise ValueError(
                        "holder final Hue/BPM differ from the fixed physical mapping"
                    )

        exploration = _optional_text("exploration_decision", self.exploration_decision)
        adoption = _optional_text("adoption_result", self.adoption_result)
        if exploration is not None and exploration not in EXPLORATION_DECISIONS:
            raise ValueError("exploration_decision is not a Stage 5C decision")
        if adoption is not None and adoption not in ADOPTION_RESULTS:
            raise ValueError("adoption_result is not a Stage 5C result")
        if not isinstance(self.candidate_generated, bool):
            raise TypeError("candidate_generated must be boolean")
        if not isinstance(self.candidate_accepted, bool):
            raise TypeError("candidate_accepted must be boolean")
        if self.candidate_accepted != (adoption == "accepted"):
            raise ValueError("candidate_accepted must exactly match accepted adoption")
        if self.candidate_accepted and not self.candidate_generated:
            raise ValueError("an accepted candidate must have been generated")
        if self.candidate_generated and exploration != "explore":
            raise ValueError("a generated candidate requires explore")
        if holder_id is None and any(
            value is not None for value in (exploration, adoption)
        ):
            raise ValueError("an outcome without a holder has no holder adaptation result")

        baseline = _evaluation(
            "baseline_evaluation",
            self.baseline_evaluation,
            kind="baseline",
            bundle_index=None,
        )
        bundle_0 = _evaluation(
            "bundle_0_evaluation",
            self.bundle_0_evaluation,
            kind="bundle",
            bundle_index=0,
        )
        bundle_1 = _evaluation(
            "bundle_1_evaluation",
            self.bundle_1_evaluation,
            kind="bundle",
            bundle_index=1,
        )
        bundle_2 = _evaluation(
            "bundle_2_evaluation",
            self.bundle_2_evaluation,
            kind="bundle",
            bundle_index=2,
        )
        presentations = _bundle_presentations(self.bundle_presentations)
        if tuple(
            (record.bundle_index, record.first_signal_index)
            for record in presentations
        ) != tuple(
            sorted(
                (record.bundle_index, record.first_signal_index)
                for record in presentations
            )
        ):
            raise ValueError("bundle presentations must be ordered by Bundle and signal")
        if holder_id is None and presentations:
            raise ValueError("an outcome without a holder has no Bundle presentations")
        if holder_id is not None and any(
            record.holder_id != holder_id for record in presentations
        ):
            raise ValueError("Bundle presentation holder differs from session holder")
        if any(record.session_index != index for record in presentations):
            raise ValueError("Bundle presentation session index differs from outcome")
        if holder_role is not None:
            holder_config = digital_life_config_for_role(holder_role)
            mapper_config = GardenLightMapperConfig()
            for record in presentations:
                expected_b = intrinsic_b_mapping(
                    record.k_presented,
                    f_min=holder_config.f_min,
                    f_max=holder_config.f_max,
                    a_fixed=holder_config.a_fixed,
                    t_min=holder_config.t_min,
                    t_max=holder_config.t_max,
                    d_fixed=holder_config.d_fixed,
                )
                expected_light = map_active_b_to_light(expected_b, mapper_config)
                if record.b_presented != expected_b:
                    raise ValueError("Bundle presentation B differs from presented k")
                if (
                    record.hue_degree != expected_light.hue_degree
                    or record.blink_bpm != expected_light.blink_bpm
                    or record.mapping_version != mapper_config.mapping_version
                ):
                    raise ValueError(
                        "Bundle presentation differs from the fixed physical mapping"
                    )
        trial_patterns = tuple(
            dict.fromkeys(
                record.k_presented
                for record in presentations
                if holder_id is not None
                and record.k_presented != initial_k[holder_id]
            )
        )
        if len(trial_patterns) > 1:
            raise ValueError("one session may present at most one candidate k_trial")
        holder_trial = None if not trial_patterns else trial_patterns[0]
        if self.engine_completed:
            if self.candidate_generated != (holder_trial is not None):
                raise ValueError(
                    "candidate generation differs from the physical k_trial audit"
                )
            decision_w: float | None = None
            if (
                holder_id is not None
                and baseline is not None
                and baseline.is_valid
                and baseline.n is not None
                and bundle_0 is not None
                and bundle_0.is_valid
                and bundle_0.n is not None
            ):
                decision_w = evaluate_w(
                    calculate_nd(
                        bundle_0.n,
                        baseline.n,
                        digital_life_config_for_role(holder_role).delta_n,
                    )
                )
            if self.candidate_generated and decision_w is None:
                raise ValueError(
                    "candidate audit requires valid baseline and Bundle 0 values"
                )
            if holder_id is not None and decision_w is not None:
                profile = derive_relation_memory_intrinsic_profile(holder_id)
                probability = exploration_probability(
                    decision_w,
                    profile.p_explore_min,
                )
                expected_decision = exploration_decision(
                    hash01(
                        holder_id,
                        "C",
                        "explore",
                        session_before[holder_id],
                    ),
                    probability,
                )
                if exploration != expected_decision:
                    raise ValueError(
                        "exploration decision differs from the fixed Hash01 policy"
                    )
                if holder_trial is not None:
                    sigma = exploration_sigma(
                        decision_w,
                        profile.sigma_min,
                        profile.sigma_max,
                    )
                    expected_trial = generate_candidate(
                        initial_k[holder_id],
                        sigma,
                        derive_search_direction(
                            holder_id,
                            trial_before[holder_id],
                        ),
                    )
                    if holder_trial != expected_trial:
                        raise ValueError(
                            "physical k_trial differs from the fixed Hash/reflect policy"
                        )
            for life_id, initial_anchor in initial_k.items():
                expected_anchor = (
                    holder_trial
                    if life_id == holder_id and self.candidate_accepted
                    else initial_anchor
                )
                if final_k[life_id] != expected_anchor:
                    raise ValueError(
                        "final k anchor differs from the audited adoption result"
                    )
        complete_presentation_audit = True
        for bundle_index in range(3):
            bundle_presentations = tuple(
                record
                for record in presentations
                if record.bundle_index == bundle_index
            )
            if not bundle_presentations:
                complete_presentation_audit = False
                continue
            expected_start = 60 + 60 * bundle_index
            expected_signal = bundle_presentations[0].first_signal_index
            for record in bundle_presentations:
                if record.first_signal_index != expected_signal:
                    raise ValueError("Bundle presentation audit has a signal gap")
                expected_signal = record.last_signal_index + 1
            complete_presentation_audit = complete_presentation_audit and (
                bundle_presentations[0].first_signal_index == expected_start
                and expected_signal == 120 + 60 * bundle_index
            )
        if self.valid_for_convergence and (
            baseline is None
            or not baseline.is_valid
            or any(record is None for record in (bundle_0, bundle_1, bundle_2))
            or holder_id is None
            or holder_anchor is None
            or hue is None
            or bpm is None
            or set(final_states) != roster
            or not complete_presentation_audit
        ):
            raise ValueError("valid outcome lacks a required finalized session value")

        digest = _optional_text("session_digest", self.session_digest)
        if digest is not None and (
            len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError("session_digest must be a lowercase SHA-256 hex digest")
        if self.engine_completed and digest is None:
            raise ValueError("a completed engine requires session_digest")
        if self.schema_version != MULTI_SESSION_OUTCOME_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {MULTI_SESSION_OUTCOME_SCHEMA_VERSION}"
            )

        normalized = {
            "session_index": index,
            "local_time_us": local,
            "global_time_us": aggregate,
            "invalid_reason": reason,
            "holder_id": holder_id,
            "holder_role": holder_role,
            "initial_k_anchor_by_life": initial_k,
            "initial_persistent_state_by_life": initial_states,
            "final_k_anchor_by_life": final_k,
            "holder_final_k_anchor": holder_anchor,
            "holder_final_b_f": b_values[0],
            "holder_final_b_a": b_values[1],
            "holder_final_b_t": b_values[2],
            "holder_final_b_d": b_values[3],
            "holder_final_hue_degree": hue,
            "holder_final_blink_bpm": bpm,
            "exploration_decision": exploration,
            "adoption_result": adoption,
            "holder_W_anchor_session": _optional_unit(
                "holder_W_anchor_session", self.holder_W_anchor_session
            ),
            "holder_W_trial_1": _optional_unit(
                "holder_W_trial_1", self.holder_W_trial_1
            ),
            "holder_W_trial_2": _optional_unit(
                "holder_W_trial_2", self.holder_W_trial_2
            ),
            "baseline_evaluation": baseline,
            "bundle_0_evaluation": bundle_0,
            "bundle_1_evaluation": bundle_1,
            "bundle_2_evaluation": bundle_2,
            "session_count_before_by_life": session_before,
            "session_count_after_by_life": session_after,
            "trial_count_before_by_life": trial_before,
            "trial_count_after_by_life": trial_after,
            "final_persistent_state_by_life": final_states,
            "bundle_presentations": presentations,
            "session_digest": digest,
        }
        for name, value in normalized.items():
            object.__setattr__(self, name, value)

    @property
    def holder_initial_hue_degree(self) -> float | None:
        """Return the first actual holder light, for the GUI session-history row."""

        return (
            None
            if not self.bundle_presentations
            else self.bundle_presentations[0].hue_degree
        )

    @property
    def holder_initial_blink_bpm(self) -> float | None:
        """Return the first actual holder blink rate in the session."""

        return (
            None
            if not self.bundle_presentations
            else self.bundle_presentations[0].blink_bpm
        )

    @property
    def holder_k_trial(self) -> KVector | None:
        """Return the actually presented candidate, never a rollback fallback."""

        if not self.candidate_generated or self.holder_id is None:
            return None
        initial = self.initial_k_anchor_by_life[self.holder_id]
        return next(
            (
                record.k_presented
                for record in self.bundle_presentations
                if record.k_presented != initial
            ),
            None,
        )

    def to_dict(self) -> dict[str, Any]:
        def vectors(values: Mapping[str, KVector]) -> dict[str, list[float]]:
            return {life_id: list(vector) for life_id, vector in values.items()}

        def counters(values: Mapping[str, int]) -> dict[str, int]:
            return dict(values)

        def evaluation(record: GardenEvaluationRecord | None) -> dict[str, Any] | None:
            return None if record is None else record.to_dict()

        return {
            "session_index": self.session_index,
            "local_time_us": self.local_time_us,
            "global_time_us": self.global_time_us,
            "valid_for_convergence": self.valid_for_convergence,
            "invalid_reason": self.invalid_reason,
            "engine_completed": self.engine_completed,
            "physiology_root_seed": self.physiology_root_seed,
            "user_type_id": self.user_type_id,
            "holder_id": self.holder_id,
            "holder_role": self.holder_role,
            "initial_k_anchor_by_life": vectors(self.initial_k_anchor_by_life),
            "initial_persistent_state_by_life": {
                life_id: state.to_dict()
                for life_id, state in self.initial_persistent_state_by_life.items()
            },
            "final_k_anchor_by_life": vectors(self.final_k_anchor_by_life),
            "holder_final_k_anchor": (
                None if self.holder_final_k_anchor is None else list(self.holder_final_k_anchor)
            ),
            "holder_final_b_f": self.holder_final_b_f,
            "holder_final_b_a": self.holder_final_b_a,
            "holder_final_b_t": self.holder_final_b_t,
            "holder_final_b_d": self.holder_final_b_d,
            "holder_final_hue_degree": self.holder_final_hue_degree,
            "holder_final_blink_bpm": self.holder_final_blink_bpm,
            "exploration_decision": self.exploration_decision,
            "adoption_result": self.adoption_result,
            "candidate_generated": self.candidate_generated,
            "candidate_accepted": self.candidate_accepted,
            "holder_W_anchor_session": self.holder_W_anchor_session,
            "holder_W_trial_1": self.holder_W_trial_1,
            "holder_W_trial_2": self.holder_W_trial_2,
            "baseline_evaluation": evaluation(self.baseline_evaluation),
            "bundle_0_evaluation": evaluation(self.bundle_0_evaluation),
            "bundle_1_evaluation": evaluation(self.bundle_1_evaluation),
            "bundle_2_evaluation": evaluation(self.bundle_2_evaluation),
            "session_count_before_by_life": counters(
                self.session_count_before_by_life
            ),
            "session_count_after_by_life": counters(
                self.session_count_after_by_life
            ),
            "trial_count_before_by_life": counters(self.trial_count_before_by_life),
            "trial_count_after_by_life": counters(self.trial_count_after_by_life),
            "final_persistent_state_by_life": {
                life_id: state.to_dict()
                for life_id, state in self.final_persistent_state_by_life.items()
            },
            "bundle_presentations": [
                record.to_dict() for record in self.bundle_presentations
            ],
            "session_digest": self.session_digest,
            "schema_version": self.schema_version,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> SessionOutcome:
        if not isinstance(values, Mapping):
            raise TypeError("session outcome values must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                f"session outcome fields differ; missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        return cls(**dict(values))

    @classmethod
    def from_json(cls, encoded: str) -> SessionOutcome:
        if not isinstance(encoded, str):
            raise TypeError("encoded session outcome must be a string")
        values = json.loads(
            encoded,
            object_pairs_hook=_strict_object_pairs,
            parse_constant=_reject_json_constant,
        )
        if not isinstance(values, dict):
            raise ValueError("session outcome JSON must contain an object")
        return cls.from_dict(values)


def _physical_bundle_presentations(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
    session_index: int,
    holder_id: str | None,
    holder_component: AdaptiveConnectedDigitalLifeComponent | None,
) -> tuple[BundleLightPresentation, ...]:
    """Detach exact contiguous physical-command segments from the session engine."""

    if holder_id is None or holder_component is None:
        return ()
    signal_records = {
        record.signal_index: record
        for record in holder_component.adaptive_signal_records()
        if record.s == 1 and record.bundle_index is not None
    }
    result: list[BundleLightPresentation] = []
    for command in simulation.garden_light_mapper_component.command_records():
        signal_index = command.source_signal_index
        if (
            not command.active
            or command.qualification_holder_id != holder_id
            or not 60 <= signal_index <= 239
        ):
            continue
        signal = signal_records.get(signal_index)
        if signal is None:
            raise RuntimeError("active physical command lacks holder signal audit")
        if command.source_b is None or command.hue_degree is None or command.blink_bpm is None:
            raise RuntimeError("active physical command lacks B/Hue/BPM")
        if tuple(command.source_b) != tuple(signal.b_presented):
            raise RuntimeError("physical command B differs from holder-presented B")
        assert signal.bundle_index is not None
        candidate = BundleLightPresentation(
            session_index=session_index,
            bundle_index=signal.bundle_index,
            first_signal_index=signal_index,
            last_signal_index=signal_index,
            first_effective_time_us=command.command_effective_time_us,
            last_effective_time_us=command.command_effective_time_us,
            first_global_time_us=global_time_us(
                session_index,
                command.command_effective_time_us,
            ),
            last_global_time_us=global_time_us(
                session_index,
                command.command_effective_time_us,
            ),
            holder_id=holder_id,
            k_presented=signal.k_presented,
            b_presented=signal.b_presented,
            hue_degree=command.hue_degree,
            blink_bpm=command.blink_bpm,
            mapping_version=command.mapping_version,
        )
        if result:
            previous = result[-1]
            same_pattern = (
                previous.bundle_index == candidate.bundle_index
                and previous.holder_id == candidate.holder_id
                and previous.k_presented == candidate.k_presented
                and previous.b_presented == candidate.b_presented
                and previous.hue_degree == candidate.hue_degree
                and previous.blink_bpm == candidate.blink_bpm
                and previous.mapping_version == candidate.mapping_version
                and previous.last_signal_index + 1 == candidate.first_signal_index
            )
            if same_pattern:
                result[-1] = replace(
                    previous,
                    last_signal_index=candidate.last_signal_index,
                    last_effective_time_us=candidate.last_effective_time_us,
                    last_global_time_us=candidate.last_global_time_us,
                )
                continue
        result.append(candidate)
    return tuple(result)


def session_outcome_from_simulation(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
    *,
    session_index: int,
    physiology_root_seed: int,
    user_type_id: str,
    execution_error: BaseException | None = None,
) -> SessionOutcome:
    """Project one Stage 5C engine into a detached multi-session audit record."""

    if not hasattr(simulation, "engine"):
        raise TypeError("simulation must be an adaptive closed-loop simulation")
    components = adaptive_digital_life_components(simulation)
    life_ids = tuple(config.digital_life_id for config in simulation.digital_life_configs)
    configs_by_id = {
        config.digital_life_id: config for config in simulation.digital_life_configs
    }
    initial_states = {
        life_id: components[life_id].initial_persistent_state() for life_id in life_ids
    }
    finalized = {
        life_id: components[life_id].final_persistent_state() for life_id in life_ids
    }
    all_finalized = all(state is not None for state in finalized.values())
    final_states: dict[str, RelationMemoryPersistentState] = (
        {
            life_id: state
            for life_id, state in finalized.items()
            if isinstance(state, RelationMemoryPersistentState)
        }
        if all_finalized
        else {}
    )

    evaluations = simulation.garden_input_component.evaluation_records()
    baseline = next(
        (record for record in evaluations if record.evaluation_kind == "baseline"),
        None,
    )
    bundles = {
        record.bundle_index: record
        for record in evaluations
        if record.evaluation_kind == "bundle"
    }
    garden_snapshot = simulation.garden_output_component.snapshot()
    holder_id = garden_snapshot.last_assigned_holder_id
    holder_role = (
        None if holder_id is None else configs_by_id[holder_id].role
    )
    holder_component: AdaptiveConnectedDigitalLifeComponent | None = (
        None if holder_id is None else components[holder_id]
    )
    holder_session = (
        None
        if holder_component is None
        else holder_component.relation_memory_session_state()
    )
    presentations: tuple[BundleLightPresentation, ...] = ()
    presentation_error: str | None = None
    try:
        presentations = _physical_bundle_presentations(
            simulation,
            session_index,
            holder_id,
            holder_component,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        presentation_error = (
            f"bundle_presentation_error:{type(exc).__name__}:{exc}"
        )

    final_k = {life_id: state.k_anchor for life_id, state in final_states.items()}
    holder_anchor: KVector | None = None
    holder_b: KVector | None = None
    holder_hue: float | None = None
    holder_bpm: float | None = None
    physical_error: str | None = None
    if holder_id is not None and holder_id in final_states:
        try:
            holder_anchor = final_states[holder_id].k_anchor
            config = configs_by_id[holder_id]
            holder_b = intrinsic_b_mapping(
                holder_anchor,
                f_min=config.f_min,
                f_max=config.f_max,
                a_fixed=config.a_fixed,
                t_min=config.t_min,
                t_max=config.t_max,
                d_fixed=config.d_fixed,
            )
            mapping = map_active_b_to_light(
                holder_b,
                simulation.garden_light_mapper_config,
            )
            holder_hue = mapping.hue_degree
            holder_bpm = mapping.blink_bpm
        except (TypeError, ValueError, RuntimeError) as exc:
            holder_anchor = None
            holder_b = None
            physical_error = f"physical_mapping_error:{type(exc).__name__}:{exc}"

    clock_completed = simulation.engine.clock.state is ClockState.COMPLETED
    # An exception is never a normally completed session, even if it was
    # detected after a factory returned an already-completed/reused engine.
    # This flag drives commit eligibility, completed counts, and resume-stop
    # semantics, so it must include execution success rather than clock state
    # alone.
    engine_completed = clock_completed and execution_error is None
    invalid_reasons: list[str] = []
    if execution_error is not None:
        invalid_reasons.append(
            f"engine_error:{type(execution_error).__name__}:{execution_error}"
        )
    if not clock_completed:
        invalid_reasons.append("engine_incomplete")
    if baseline is None:
        invalid_reasons.append("baseline_missing")
    elif not baseline.is_valid:
        invalid_reasons.append("baseline_invalid")
    if holder_id is None:
        invalid_reasons.append("active_holder_missing")
    if not all_finalized:
        invalid_reasons.append("final_persistent_states_incomplete")
    if set(bundles) != {0, 1, 2}:
        invalid_reasons.append("bundle_evaluations_incomplete")
    if presentation_error is not None:
        invalid_reasons.append(presentation_error)
    elif holder_id is not None and not presentations:
        invalid_reasons.append("bundle_presentations_missing")
    if physical_error is not None:
        invalid_reasons.append(physical_error)
    elif holder_id is not None and holder_anchor is None:
        invalid_reasons.append("holder_final_pattern_missing")
    valid = not invalid_reasons
    local_time_us = simulation.engine.clock.current_time_us
    digest = simulation.engine.deterministic_digest()

    return SessionOutcome(
        session_index=session_index,
        local_time_us=local_time_us,
        global_time_us=global_time_us(session_index, local_time_us),
        valid_for_convergence=valid,
        invalid_reason=None if valid else ";".join(invalid_reasons),
        engine_completed=engine_completed,
        physiology_root_seed=physiology_root_seed,
        user_type_id=user_type_id,
        holder_id=holder_id,
        holder_role=holder_role,
        initial_k_anchor_by_life={
            life_id: state.k_anchor for life_id, state in initial_states.items()
        },
        initial_persistent_state_by_life=initial_states,
        final_k_anchor_by_life=final_k,
        holder_final_k_anchor=holder_anchor,
        holder_final_b_f=None if holder_b is None else holder_b[0],
        holder_final_b_a=None if holder_b is None else holder_b[1],
        holder_final_b_t=None if holder_b is None else holder_b[2],
        holder_final_b_d=None if holder_b is None else holder_b[3],
        holder_final_hue_degree=holder_hue,
        holder_final_blink_bpm=holder_bpm,
        exploration_decision=(
            None if holder_session is None else holder_session.exploration_decision
        ),
        adoption_result=(
            None if holder_session is None else holder_session.adoption_result
        ),
        candidate_generated=(
            False if holder_session is None else holder_session.candidate_generated
        ),
        candidate_accepted=(
            False if holder_session is None else holder_session.adoption_result == "accepted"
        ),
        holder_W_anchor_session=(
            None if holder_session is None else holder_session.w_anchor_session
        ),
        holder_W_trial_1=(
            None if holder_session is None else holder_session.w_trial_1
        ),
        holder_W_trial_2=(
            None if holder_session is None else holder_session.w_trial_2
        ),
        baseline_evaluation=baseline,
        bundle_0_evaluation=bundles.get(0),
        bundle_1_evaluation=bundles.get(1),
        bundle_2_evaluation=bundles.get(2),
        session_count_before_by_life={
            life_id: state.session_count for life_id, state in initial_states.items()
        },
        session_count_after_by_life={
            life_id: state.session_count for life_id, state in final_states.items()
        },
        trial_count_before_by_life={
            life_id: state.trial_count for life_id, state in initial_states.items()
        },
        trial_count_after_by_life={
            life_id: state.trial_count for life_id, state in final_states.items()
        },
        final_persistent_state_by_life=final_states,
        bundle_presentations=presentations,
        session_digest=digest,
    )


__all__ = [
    "BUNDLE_PRESENTATION_SCHEMA_VERSION",
    "BundleLightPresentation",
    "KVector",
    "MULTI_SESSION_OUTCOME_SCHEMA_VERSION",
    "SessionOutcome",
    "session_outcome_from_simulation",
]
