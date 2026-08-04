"""Detached Stage 8A.1 session outcome with experiment-only diagnostics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Any

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.math import intrinsic_b_mapping
from symbiotic_sim_v2.digital_life.relation_memory.adaptive_component import (
    AdaptiveConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.relation_memory.config import (
    ADOPTION_RESULTS,
    EXPLORATION_DECISIONS,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    relation_memory_state_map_from_dict,
    relation_memory_state_map_to_dict,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION,
    SCALED_REFERENCE_SIGMA_POLICY_VERSION,
)
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.mapping import map_active_b_to_light
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
    adaptive_digital_life_components,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.experimental_component import (
    ExperimentalAdaptiveConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.runtime.multi_session.session_outcome import (
    BundleLightPresentation,
    _physical_bundle_presentations,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    SESSION_DURATION_US,
    UINT32_MAX,
    global_time_us,
)
from symbiotic_sim_v2.simulation.clock import ClockState


def _counter(name: str, value: object) -> int:
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


def _optional_number(name: str, value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric or null")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _state_map(
    value: Mapping[str, RelationMemoryPersistentState] | Mapping[str, Any],
) -> Mapping[str, RelationMemoryPersistentState]:
    if not isinstance(value, Mapping):
        raise TypeError("persistent state map must be a mapping")
    ids = tuple(value)
    expected_ids = tuple(
        digital_life_config_for_role(role).digital_life_id
        for role in ("red", "green", "blue")
    )
    if len(ids) != 3 or set(ids) != set(expected_ids):
        raise ValueError(
            "experimental outcome requires the fixed red/green/blue life roster"
        )
    raw = {
        life_id: state.to_dict()
        if isinstance(state, RelationMemoryPersistentState)
        else state
        for life_id, state in value.items()
    }
    return relation_memory_state_map_from_dict(raw, expected_digital_life_ids=ids)


def _mapping_records(name: str, value: object) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, Mapping[str, Any]] = {}
    for life_id, record in value.items():
        if not isinstance(life_id, str) or not life_id.strip():
            raise ValueError(f"{name} keys must be non-empty life IDs")
        if not isinstance(record, Mapping):
            raise TypeError(f"{name} records must be mappings")
        result[life_id] = MappingProxyType(dict(record))
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class ExperimentalSessionOutcome:
    session_index: int
    local_time_us: int
    global_time_us: int
    valid_for_convergence: bool
    invalid_reason: str | None
    engine_completed: bool
    physiology_root_seed: int
    user_type_id: str
    reference_arm: bool
    holder_id: str | None
    holder_role: str | None
    initial_persistent_state_by_life: Mapping[str, RelationMemoryPersistentState]
    final_persistent_state_by_life: Mapping[str, RelationMemoryPersistentState]
    holder_final_k_anchor: tuple[float, float, float, float] | None
    holder_final_hue_degree: float | None
    holder_final_blink_bpm: float | None
    exploration_decision: str | None
    adoption_result: str | None
    candidate_generated: bool
    candidate_accepted: bool
    holder_W_anchor_session: float | None
    holder_W_trial_1: float | None
    holder_W_trial_2: float | None
    fatigue_trajectory_by_life: Mapping[str, Mapping[str, Any]]
    sigma_trajectory_by_life: Mapping[str, Mapping[str, Any]]
    bundle_presentations: tuple[BundleLightPresentation, ...]
    session_digest: str | None
    schema_version: str = FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION

    def __post_init__(self) -> None:
        index = _counter("session_index", self.session_index)
        local = _counter("local_time_us", self.local_time_us)
        aggregate = _counter("global_time_us", self.global_time_us)
        if local > SESSION_DURATION_US:
            raise ValueError("local_time_us exceeds the 240-second session")
        if aggregate != global_time_us(index, local):
            raise ValueError("global_time_us differs from indexed local time")
        for name in (
            "valid_for_convergence",
            "engine_completed",
            "reference_arm",
            "candidate_generated",
            "candidate_accepted",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        reason = _optional_text("invalid_reason", self.invalid_reason)
        if self.valid_for_convergence != (reason is None and self.engine_completed):
            raise ValueError("validity must exactly reflect completion and invalid_reason")
        if self.engine_completed and local != SESSION_DURATION_US:
            raise ValueError("completed outcome must end at the 240-second boundary")
        if isinstance(self.physiology_root_seed, bool) or not isinstance(
            self.physiology_root_seed, int
        ):
            raise TypeError("physiology_root_seed must be an integer")
        if not 0 <= self.physiology_root_seed <= UINT32_MAX:
            raise ValueError("physiology_root_seed must be unsigned 32-bit")
        if not isinstance(self.user_type_id, str) or not self.user_type_id.strip():
            raise ValueError("user_type_id must be a non-empty string")
        holder_id = _optional_text("holder_id", self.holder_id)
        holder_role = _optional_text("holder_role", self.holder_role)
        if (holder_id is None) != (holder_role is None):
            raise ValueError("holder ID and role must both be present or null")
        if holder_role is not None and holder_role not in {"red", "green", "blue"}:
            raise ValueError("holder_role is not recognized")
        if holder_role is not None and (
            digital_life_config_for_role(holder_role).digital_life_id != holder_id
        ):
            raise ValueError("holder ID and role differ from the fixed roster")
        initial = _state_map(self.initial_persistent_state_by_life)
        final = (
            _state_map(self.final_persistent_state_by_life)
            if self.final_persistent_state_by_life
            else MappingProxyType({})
        )
        if self.engine_completed and set(final) != set(initial):
            raise ValueError("completed outcome requires three final persistent states")
        if not self.engine_completed and final:
            raise ValueError("incomplete outcome cannot publish final persistent state")
        if self.candidate_accepted and not self.candidate_generated:
            raise ValueError("accepted candidate must have been generated")
        if (
            self.exploration_decision is not None
            and self.exploration_decision not in EXPLORATION_DECISIONS
        ):
            raise ValueError("exploration_decision is not recognized")
        if (
            self.adoption_result is not None
            and self.adoption_result not in ADOPTION_RESULTS
        ):
            raise ValueError("adoption_result is not recognized")
        if self.candidate_generated != (self.exploration_decision == "explore"):
            raise ValueError("candidate generation differs from exploration decision")
        if self.candidate_accepted != (self.adoption_result == "accepted"):
            raise ValueError("candidate acceptance differs from adoption result")
        k = self.holder_final_k_anchor
        if k is not None:
            if len(k) != 4:
                raise ValueError("holder_final_k_anchor must contain four values")
            k = tuple(float(value) for value in k)  # type: ignore[assignment]
            if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in k):
                raise ValueError("holder_final_k_anchor values must be within [0,1]")
        hue = _optional_number("holder_final_hue_degree", self.holder_final_hue_degree)
        bpm = _optional_number("holder_final_blink_bpm", self.holder_final_blink_bpm)
        if self.valid_for_convergence and (holder_id is None or hue is None or bpm is None):
            raise ValueError("valid outcome lacks its committed holder pattern")
        presentations = tuple(
            item
            if isinstance(item, BundleLightPresentation)
            else BundleLightPresentation.from_dict(item)
            for item in self.bundle_presentations
        )
        fatigue = _mapping_records(
            "fatigue_trajectory_by_life", self.fatigue_trajectory_by_life
        )
        sigma = _mapping_records(
            "sigma_trajectory_by_life", self.sigma_trajectory_by_life
        )
        if self.engine_completed and set(fatigue) != set(initial):
            raise ValueError("completed outcome requires one fatigue record per life")
        if not set(sigma).issubset(initial):
            raise ValueError("sigma trajectory contains an unknown Digital Life")
        if sigma and set(sigma) != {holder_id}:
            raise ValueError("sigma trajectory must belong only to the session holder")
        if self.valid_for_convergence and set(sigma) != {holder_id}:
            raise ValueError("valid outcome requires one holder sigma audit")
        for presentation in presentations:
            if presentation.session_index != index:
                raise ValueError("bundle presentation belongs to another session")
            if presentation.holder_id != holder_id:
                raise ValueError("bundle presentation holder differs from the outcome")
        if self.engine_completed:
            trial_deltas: dict[str, int] = {}
            for life_id, before in initial.items():
                after = final[life_id]
                if after.session_count != before.session_count + 1:
                    raise ValueError("completed outcome must increment session_count once")
                trial_delta = after.trial_count - before.trial_count
                if trial_delta not in (0, 1):
                    raise ValueError(
                        "completed outcome may increment each trial_count at most once"
                    )
                trial_deltas[life_id] = trial_delta
                if (
                    after.profile_version,
                    after.algorithm_version,
                    after.state_schema_version,
                ) != (
                    before.profile_version,
                    before.algorithm_version,
                    before.state_schema_version,
                ):
                    raise ValueError("persistent-state versions changed in outcome")
                audit = fatigue[life_id]
                if audit.get("digital_life_id") != life_id:
                    raise ValueError(
                        "fatigue record Digital Life ID differs from its mapping key"
                    )
                if audit.get("e_at_session_start") != before.e:
                    raise ValueError(
                        "fatigue record session-start E differs from persistent-state "
                        "handoff chain"
                    )
                selected = audit.get("selected_active_signal_count")
                recovered = audit.get("full_recovery_applied")
                after_policy = audit.get("e_after_session_end_policy")
                audit_reference = audit.get("reference_arm")
                if isinstance(selected, bool) or not isinstance(selected, int):
                    raise TypeError("selected_active_signal_count must be an integer")
                if not 0 <= selected <= 180:
                    raise ValueError("selected_active_signal_count is outside [0,180]")
                if not isinstance(recovered, bool):
                    raise TypeError("full_recovery_applied must be boolean")
                if not isinstance(audit_reference, bool):
                    raise TypeError("fatigue audit reference_arm must be boolean")
                if audit_reference != self.reference_arm:
                    raise ValueError("fatigue audit differs from outcome arm")
                if isinstance(after_policy, bool) or not isinstance(
                    after_policy, (int, float)
                ):
                    raise TypeError("e_after_session_end_policy must be numeric")
                if after.e != float(after_policy):
                    raise ValueError("final E differs from the fatigue policy audit")
                if self.reference_arm:
                    if recovered:
                        raise ValueError("reference arm cannot apply full recovery")
                else:
                    if recovered != (selected == 0):
                        raise ValueError(
                            "experimental recovery differs from selected signal count"
                        )
                    if selected == 0 and after.e != 0.0:
                        raise ValueError("unselected experimental life must finish at E=0")
                expected_anchor = (
                    after.k_anchor
                    if life_id == holder_id and self.candidate_accepted
                    else before.k_anchor
                )
                if after.k_anchor != expected_anchor:
                    raise ValueError(
                        "final k_anchor differs from the candidate adoption result"
                    )
                if (
                    life_id == holder_id
                    and self.candidate_accepted
                    and (
                        after.k_anchor[1] != before.k_anchor[1]
                        or after.k_anchor[3] != before.k_anchor[3]
                    )
                ):
                    raise ValueError("candidate adoption may change only F/T")
            if sum(trial_deltas.values()) != int(self.candidate_generated):
                raise ValueError(
                    "trial_count increments must exactly match candidate generation"
                )
            if self.candidate_generated and (
                holder_id is None or trial_deltas[holder_id] != 1
            ):
                raise ValueError("only the holder may increment trial_count")
            if holder_id is not None:
                holder_final = final[holder_id]
                if k != holder_final.k_anchor:
                    raise ValueError(
                        "holder_final_k_anchor differs from final persistent state"
                    )
                if k is not None:
                    config = digital_life_config_for_role(holder_role)
                    mapped_b = intrinsic_b_mapping(
                        k,
                        f_min=config.f_min,
                        f_max=config.f_max,
                        a_fixed=config.a_fixed,
                        t_min=config.t_min,
                        t_max=config.t_max,
                        d_fixed=config.d_fixed,
                    )
                    mapped_light = map_active_b_to_light(
                        mapped_b,
                        GardenLightMapperConfig(),
                    )
                    if hue is not None and not math.isclose(
                        hue,
                        mapped_light.hue_degree,
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    ):
                        raise ValueError("holder final Hue differs from final k mapping")
                    if bpm is not None and not math.isclose(
                        bpm,
                        mapped_light.blink_bpm,
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    ):
                        raise ValueError("holder final BPM differs from final k mapping")
            for life_id, audit in sigma.items():
                if audit.get("digital_life_id") != life_id:
                    raise ValueError(
                        "sigma record Digital Life ID differs from its mapping key"
                    )
                if audit.get("candidate_generated") != self.candidate_generated:
                    raise ValueError(
                        "sigma record candidate flag differs from the outcome"
                    )
                if audit.get("candidate_accepted") != self.candidate_accepted:
                    raise ValueError(
                        "sigma record adoption flag differs from the outcome"
                    )
                audit_reference = audit.get("reference_arm")
                if audit_reference is not None and audit_reference != self.reference_arm:
                    raise ValueError("sigma audit differs from outcome arm")
                if audit.get("policy_version") != SCALED_REFERENCE_SIGMA_POLICY_VERSION:
                    raise ValueError("sigma audit policy_version is not recognized")
                numeric: dict[str, float] = {}
                for name in (
                    "w_anchor_session",
                    "reference_sigma_min",
                    "reference_sigma_max",
                    "reference_sigma_at_w",
                    "sigma_multiplier",
                    "effective_sigma",
                ):
                    value = audit.get(name)
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise TypeError(f"sigma audit {name} must be numeric")
                    numeric[name] = float(value)
                    if not math.isfinite(numeric[name]):
                        raise ValueError(f"sigma audit {name} must be finite")
                for name in (
                    "w_anchor_session",
                    "reference_sigma_min",
                    "reference_sigma_max",
                    "reference_sigma_at_w",
                    "effective_sigma",
                ):
                    if not 0.0 <= numeric[name] <= 1.0:
                        raise ValueError(f"sigma audit {name} must be within [0,1]")
                if not 0.25 <= numeric["sigma_multiplier"] <= 1.50:
                    raise ValueError("sigma audit multiplier is outside [0.25,1.50]")
                if not (
                    numeric["reference_sigma_min"]
                    <= numeric["reference_sigma_at_w"]
                    <= numeric["reference_sigma_max"]
                ):
                    raise ValueError("sigma audit reference width ordering is invalid")
                if not math.isclose(
                    numeric["effective_sigma"],
                    numeric["reference_sigma_at_w"]
                    * numeric["sigma_multiplier"],
                    rel_tol=0.0,
                    abs_tol=1.0e-15,
                ):
                    raise ValueError("effective sigma differs from scaled reference sigma")
                movement_names = (
                    "candidate_delta_f",
                    "candidate_delta_t",
                    "resulting_delta_hue_degree",
                    "resulting_delta_bpm",
                )
                movement = tuple(audit.get(name) for name in movement_names)
                if self.candidate_generated != all(
                    value is not None for value in movement
                ):
                    raise ValueError(
                        "sigma candidate movement must exist exactly when generated"
                    )
                if self.candidate_generated:
                    converted: list[float] = []
                    for name, value in zip(movement_names, movement, strict=True):
                        if isinstance(value, bool) or not isinstance(
                            value, (int, float)
                        ):
                            raise TypeError(f"sigma audit {name} must be numeric")
                        number = float(value)
                        if not math.isfinite(number):
                            raise ValueError(f"sigma audit {name} must be finite")
                        converted.append(number)
                    delta_f, delta_t, delta_hue, delta_bpm = converted
                    before = initial[life_id]
                    candidate_k = (
                        before.k_anchor[0] + delta_f,
                        before.k_anchor[1],
                        before.k_anchor[2] + delta_t,
                        before.k_anchor[3],
                    )
                    if any(not 0.0 <= axis <= 1.0 for axis in candidate_k):
                        raise ValueError("sigma audit candidate lies outside [0,1]")
                    config = digital_life_config_for_role(holder_role)
                    anchor_b = intrinsic_b_mapping(
                        before.k_anchor,
                        f_min=config.f_min,
                        f_max=config.f_max,
                        a_fixed=config.a_fixed,
                        t_min=config.t_min,
                        t_max=config.t_max,
                        d_fixed=config.d_fixed,
                    )
                    candidate_b = intrinsic_b_mapping(
                        candidate_k,
                        f_min=config.f_min,
                        f_max=config.f_max,
                        a_fixed=config.a_fixed,
                        t_min=config.t_min,
                        t_max=config.t_max,
                        d_fixed=config.d_fixed,
                    )
                    mapper = GardenLightMapperConfig()
                    anchor_light = map_active_b_to_light(anchor_b, mapper)
                    candidate_light = map_active_b_to_light(candidate_b, mapper)
                    if not math.isclose(
                        delta_hue,
                        candidate_light.hue_degree - anchor_light.hue_degree,
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    ):
                        raise ValueError("sigma audit Hue delta differs from candidate")
                    if not math.isclose(
                        delta_bpm,
                        candidate_light.blink_bpm - anchor_light.blink_bpm,
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    ):
                        raise ValueError("sigma audit BPM delta differs from candidate")
                    if self.candidate_accepted and any(
                        not math.isclose(
                            actual,
                            expected,
                            rel_tol=0.0,
                            abs_tol=1.0e-15,
                        )
                        for actual, expected in zip(
                            final[life_id].k_anchor,
                            candidate_k,
                            strict=True,
                        )
                    ):
                        raise ValueError(
                            "accepted final k_anchor differs from the sigma candidate"
                        )
        if self.schema_version != FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION:
            raise ValueError(
                "schema_version must be "
                f"{FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION}"
            )
        for name, value in {
            "session_index": index,
            "local_time_us": local,
            "global_time_us": aggregate,
            "invalid_reason": reason,
            "holder_id": holder_id,
            "holder_role": holder_role,
            "initial_persistent_state_by_life": initial,
            "final_persistent_state_by_life": final,
            "holder_final_k_anchor": k,
            "holder_final_hue_degree": hue,
            "holder_final_blink_bpm": bpm,
            "holder_W_anchor_session": _optional_number(
                "holder_W_anchor_session", self.holder_W_anchor_session
            ),
            "holder_W_trial_1": _optional_number(
                "holder_W_trial_1", self.holder_W_trial_1
            ),
            "holder_W_trial_2": _optional_number(
                "holder_W_trial_2", self.holder_W_trial_2
            ),
            "fatigue_trajectory_by_life": fatigue,
            "sigma_trajectory_by_life": sigma,
            "bundle_presentations": presentations,
        }.items():
            object.__setattr__(self, name, value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_index": self.session_index,
            "local_time_us": self.local_time_us,
            "global_time_us": self.global_time_us,
            "valid_for_convergence": self.valid_for_convergence,
            "invalid_reason": self.invalid_reason,
            "engine_completed": self.engine_completed,
            "physiology_root_seed": self.physiology_root_seed,
            "user_type_id": self.user_type_id,
            "reference_arm": self.reference_arm,
            "holder_id": self.holder_id,
            "holder_role": self.holder_role,
            "initial_persistent_state_by_life": relation_memory_state_map_to_dict(
                self.initial_persistent_state_by_life,
                expected_digital_life_ids=tuple(self.initial_persistent_state_by_life),
            ),
            "final_persistent_state_by_life": (
                {}
                if not self.final_persistent_state_by_life
                else relation_memory_state_map_to_dict(
                    self.final_persistent_state_by_life,
                    expected_digital_life_ids=tuple(self.final_persistent_state_by_life),
                )
            ),
            "holder_final_k_anchor": self.holder_final_k_anchor,
            "holder_final_hue_degree": self.holder_final_hue_degree,
            "holder_final_blink_bpm": self.holder_final_blink_bpm,
            "exploration_decision": self.exploration_decision,
            "adoption_result": self.adoption_result,
            "candidate_generated": self.candidate_generated,
            "candidate_accepted": self.candidate_accepted,
            "holder_W_anchor_session": self.holder_W_anchor_session,
            "holder_W_trial_1": self.holder_W_trial_1,
            "holder_W_trial_2": self.holder_W_trial_2,
            "fatigue_trajectory_by_life": {
                life_id: dict(record)
                for life_id, record in self.fatigue_trajectory_by_life.items()
            },
            "sigma_trajectory_by_life": {
                life_id: dict(record)
                for life_id, record in self.sigma_trajectory_by_life.items()
            },
            "bundle_presentations": [
                record.to_dict() for record in self.bundle_presentations
            ],
            "session_digest": self.session_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> ExperimentalSessionOutcome:
        if not isinstance(values, Mapping):
            raise TypeError("experimental session outcome must be a mapping")
        expected = {field.name for field in fields(cls)}
        actual = set(values)
        if actual != expected:
            raise ValueError(
                f"outcome fields differ; missing={sorted(expected - actual)}, "
                f"unknown={sorted(actual - expected)}"
            )
        return cls(**dict(values))


def _reference_fatigue_record(
    component: AdaptiveConnectedDigitalLifeComponent,
) -> dict[str, Any]:
    signals = component.adaptive_signal_records()
    rounds = component.adaptive_second_round_records()
    by_index = {record.signal_index: record for record in rounds}
    if not signals or set(by_index) != {record.signal_index for record in signals}:
        raise RuntimeError("reference fatigue audit is incomplete")
    baseline = [record for record in signals if record.s == 0 and record.signal_index < 60]
    active = [record for record in signals if record.s == 1]
    closing = [
        record
        for record in rounds
        if record.closing_evaluation_attribution
    ]
    if not baseline or not active or len(closing) != 1:
        raise RuntimeError("reference fatigue phases are incomplete")
    start_round = by_index[signals[0].signal_index]
    baseline_round = by_index[baseline[-1].signal_index]
    active_round = by_index[active[-1].signal_index]
    closing_round = closing[0]
    selected = sum(record.s == 1 and record.g == 1 for record in signals)
    return {
        "digital_life_id": component.config.digital_life_id,
        "e_at_session_start": component.initial_persistent_state().e,
        "e_before_baseline": start_round.e_before,
        "e_after_baseline": baseline_round.e_after,
        "e_after_active": active_round.e_after,
        "e_before_session_end_policy": closing_round.e_after,
        "e_after_session_end_policy": closing_round.e_after,
        "selected_active_signal_count": selected,
        "full_recovery_applied": False,
        "selected_session_fatigue_target": 0.15,
        "eta_selected": None,
        "rho_reference": None,
        "selected_policy_version": "v2_reference_eta_E",
        "session_end_policy_version": "reference_no_session_end_recovery",
        "reference_arm": True,
    }


def experimental_session_outcome_from_simulation(
    simulation: AdaptiveRelationMemoryClosedLoopSimulation,
    *,
    session_index: int,
    physiology_root_seed: int,
    user_type_id: str,
    reference_arm: bool,
    execution_error: Exception | None = None,
) -> ExperimentalSessionOutcome:
    """Project a complete engine without re-evaluating its candidate in the runner."""

    components = adaptive_digital_life_components(simulation)
    life_ids = tuple(config.digital_life_id for config in simulation.digital_life_configs)
    configs = {config.digital_life_id: config for config in simulation.digital_life_configs}
    initial = {life_id: components[life_id].initial_persistent_state() for life_id in life_ids}
    finalized = {life_id: components[life_id].final_persistent_state() for life_id in life_ids}
    all_finalized = all(
        isinstance(state, RelationMemoryPersistentState)
        for state in finalized.values()
    )
    final = (
        {
            life_id: state
            for life_id, state in finalized.items()
            if isinstance(state, RelationMemoryPersistentState)
        }
        if all_finalized
        else {}
    )
    holder_id = simulation.garden_output_component.snapshot().last_assigned_holder_id
    holder_role = None if holder_id is None else configs[holder_id].role
    holder_component = None if holder_id is None else components[holder_id]
    holder_session = (
        None if holder_component is None else holder_component.relation_memory_session_state()
    )
    presentations: tuple[BundleLightPresentation, ...] = ()
    projection_errors: list[str] = []
    try:
        presentations = _physical_bundle_presentations(
            simulation, session_index, holder_id, holder_component
        )
    except Exception as exc:
        projection_errors.append(
            f"bundle_presentation_error:{type(exc).__name__}:{exc}"
        )
    holder_k = None if holder_id is None or holder_id not in final else final[holder_id].k_anchor
    holder_hue = holder_bpm = None
    if holder_id is not None and holder_k is not None:
        try:
            config = configs[holder_id]
            b = intrinsic_b_mapping(
                holder_k,
                f_min=config.f_min,
                f_max=config.f_max,
                a_fixed=config.a_fixed,
                t_min=config.t_min,
                t_max=config.t_max,
                d_fixed=config.d_fixed,
            )
            light = map_active_b_to_light(b, simulation.garden_light_mapper_config)
            holder_hue = light.hue_degree
            holder_bpm = light.blink_bpm
        except Exception as exc:
            projection_errors.append(f"physical_mapping_error:{type(exc).__name__}:{exc}")
    fatigue: dict[str, Mapping[str, Any]] = {}
    sigma: dict[str, Mapping[str, Any]] = {}
    try:
        for life_id, component in components.items():
            if isinstance(component, ExperimentalAdaptiveConnectedDigitalLifeComponent):
                fatigue_record = component.fatigue_session_record()
                if fatigue_record is None:
                    raise RuntimeError(f"missing experimental fatigue record for {life_id}")
                fatigue[life_id] = fatigue_record.to_dict() | {"reference_arm": False}
                sigma_record = component.sigma_session_record()
                if sigma_record is not None:
                    sigma[life_id] = sigma_record.to_dict()
            else:
                fatigue[life_id] = _reference_fatigue_record(component)
                decision_record = next(
                    (
                        record
                        for record in component.relation_memory_transition_records()
                        if record.bundle_index == 0
                        and record.g == 1
                        and record.w is not None
                        and record.sigma is not None
                    ),
                    None,
                )
                if decision_record is not None:
                    trial = decision_record.k_trial
                    anchor = decision_record.k_anchor_before
                    delta_f = None if trial is None else trial[0] - anchor[0]
                    delta_t = None if trial is None else trial[2] - anchor[2]
                    if trial is None:
                        delta_hue = delta_bpm = None
                    else:
                        config = component.config
                        anchor_b = intrinsic_b_mapping(
                            anchor,
                            f_min=config.f_min,
                            f_max=config.f_max,
                            a_fixed=config.a_fixed,
                            t_min=config.t_min,
                            t_max=config.t_max,
                            d_fixed=config.d_fixed,
                        )
                        trial_b = intrinsic_b_mapping(
                            trial,
                            f_min=config.f_min,
                            f_max=config.f_max,
                            a_fixed=config.a_fixed,
                            t_min=config.t_min,
                            t_max=config.t_max,
                            d_fixed=config.d_fixed,
                        )
                        anchor_light = map_active_b_to_light(
                            anchor_b, simulation.garden_light_mapper_config
                        )
                        trial_light = map_active_b_to_light(
                            trial_b, simulation.garden_light_mapper_config
                        )
                        delta_hue = trial_light.hue_degree - anchor_light.hue_degree
                        delta_bpm = trial_light.blink_bpm - anchor_light.blink_bpm
                    sigma[life_id] = {
                        "digital_life_id": life_id,
                        "w_anchor_session": decision_record.w,
                        "reference_sigma_min": decision_record.sigma_min,
                        "reference_sigma_max": decision_record.sigma_max,
                        "reference_sigma_at_w": decision_record.sigma,
                        "sigma_multiplier": 1.0,
                        "effective_sigma": decision_record.sigma,
                        "candidate_generated": trial is not None,
                        "candidate_accepted": (
                            component.relation_memory_session_state().adoption_result
                            == "accepted"
                        ),
                        "candidate_delta_f": delta_f,
                        "candidate_delta_t": delta_t,
                        "resulting_delta_hue_degree": delta_hue,
                        "resulting_delta_bpm": delta_bpm,
                        "policy_version": SCALED_REFERENCE_SIGMA_POLICY_VERSION,
                        "reference_arm": True,
                    }
    except Exception as exc:
        projection_errors.append(f"policy_audit_error:{type(exc).__name__}:{exc}")
    clock_completed = simulation.engine.clock.state is ClockState.COMPLETED
    engine_completed = clock_completed and execution_error is None
    reasons: list[str] = []
    if execution_error is not None:
        reasons.append(f"engine_error:{type(execution_error).__name__}:{execution_error}")
    if not clock_completed:
        reasons.append("engine_incomplete")
    if holder_id is None:
        reasons.append("active_holder_missing")
    if not all_finalized:
        reasons.append("final_persistent_states_incomplete")
    reasons.extend(projection_errors)
    valid = engine_completed and not reasons
    local_time = simulation.engine.clock.current_time_us
    return ExperimentalSessionOutcome(
        session_index=session_index,
        local_time_us=local_time,
        global_time_us=global_time_us(session_index, local_time),
        valid_for_convergence=valid,
        invalid_reason=None if valid else ";".join(reasons),
        engine_completed=engine_completed,
        physiology_root_seed=physiology_root_seed,
        user_type_id=user_type_id,
        reference_arm=reference_arm,
        holder_id=holder_id,
        holder_role=holder_role,
        initial_persistent_state_by_life=initial,
        final_persistent_state_by_life=final if engine_completed else {},
        holder_final_k_anchor=holder_k,
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
        holder_W_trial_1=None if holder_session is None else holder_session.w_trial_1,
        holder_W_trial_2=None if holder_session is None else holder_session.w_trial_2,
        fatigue_trajectory_by_life=fatigue if engine_completed else {},
        sigma_trajectory_by_life=sigma if engine_completed else {},
        bundle_presentations=presentations,
        session_digest=(
            simulation.engine.deterministic_digest() if engine_completed else None
        ),
    )


__all__ = [
    "ExperimentalSessionOutcome",
    "experimental_session_outcome_from_simulation",
]
