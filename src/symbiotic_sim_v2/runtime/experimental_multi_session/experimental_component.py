"""Adaptive Digital Life that owns Stage 8A.1 fatigue and sigma policies."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any

from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.digital_life.math import intrinsic_b_mapping
from symbiotic_sim_v2.digital_life.relation_memory.adaptive_component import (
    AdaptiveConnectedDigitalLifeComponent,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.session_state import (
    RelationMemorySessionState,
)
from symbiotic_sim_v2.digital_life.relation_memory.transitions import (
    RelationMemoryTransitionInput,
    RelationMemoryTransitionResult,
    apply_relation_memory_transition_with_sigma_multiplier,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    SelectedSessionFatiguePolicy,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.sigma_policy import (
    ScaledReferenceSigmaPolicy,
)
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.mapping import map_active_b_to_light
from symbiotic_sim_v2.simulation.engine import SimulationEngine

FATIGUE_SESSION_RECORD_SCHEMA_VERSION = "stage_08a1_fatigue_session_record_v1"
SIGMA_SESSION_RECORD_SCHEMA_VERSION = "stage_08a1_sigma_session_record_v1"


def _required_id(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("digital_life_id must be a non-empty string")
    return value


def _unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


@dataclass(frozen=True, slots=True)
class ExperimentalFatigueSessionRecord:
    """One life's E trajectory with the post-closing policy kept explicit."""

    digital_life_id: str
    e_at_session_start: float
    e_before_baseline: float
    e_after_baseline: float
    e_after_active: float
    e_before_session_end_policy: float
    e_after_session_end_policy: float
    selected_active_signal_count: int
    full_recovery_applied: bool
    selected_session_fatigue_target: float
    eta_selected: float
    rho_reference: float
    selected_policy_version: str
    session_end_policy_version: str
    schema_version: str = FATIGUE_SESSION_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "digital_life_id", _required_id(self.digital_life_id))
        for name in (
            "e_at_session_start",
            "e_before_baseline",
            "e_after_baseline",
            "e_after_active",
            "e_before_session_end_policy",
            "e_after_session_end_policy",
            "selected_session_fatigue_target",
            "eta_selected",
            "rho_reference",
        ):
            object.__setattr__(self, name, _unit(name, getattr(self, name)))
        if (
            isinstance(self.selected_active_signal_count, bool)
            or not isinstance(self.selected_active_signal_count, int)
        ):
            raise TypeError("selected_active_signal_count must be an integer")
        if not 0 <= self.selected_active_signal_count <= 180:
            raise ValueError("selected_active_signal_count must be between 0 and 180")
        if not isinstance(self.full_recovery_applied, bool):
            raise TypeError("full_recovery_applied must be boolean")
        if self.full_recovery_applied != (self.selected_active_signal_count == 0):
            raise ValueError("full recovery flag differs from the selected signal count")
        if self.full_recovery_applied and self.e_after_session_end_policy != 0.0:
            raise ValueError("full recovery must set E to zero")
        if (
            not self.full_recovery_applied
            and self.e_after_session_end_policy
            != self.e_before_session_end_policy
        ):
            raise ValueError("selected life E must remain at the post-closing value")
        for name in ("selected_policy_version", "session_end_policy_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.schema_version != FATIGUE_SESSION_RECORD_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {FATIGUE_SESSION_RECORD_SCHEMA_VERSION}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExperimentalSigmaSessionRecord:
    """One holder's reference/effective sigma and actual reflected movement."""

    digital_life_id: str
    w_anchor_session: float
    reference_sigma_min: float
    reference_sigma_max: float
    reference_sigma_at_w: float
    sigma_multiplier: float
    effective_sigma: float
    candidate_generated: bool
    candidate_accepted: bool
    candidate_delta_f: float | None
    candidate_delta_t: float | None
    resulting_delta_hue_degree: float | None
    resulting_delta_bpm: float | None
    policy_version: str
    schema_version: str = SIGMA_SESSION_RECORD_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "digital_life_id", _required_id(self.digital_life_id))
        for name in (
            "w_anchor_session",
            "reference_sigma_min",
            "reference_sigma_max",
            "reference_sigma_at_w",
            "effective_sigma",
        ):
            object.__setattr__(self, name, _unit(name, getattr(self, name)))
        if isinstance(self.sigma_multiplier, bool) or not isinstance(
            self.sigma_multiplier, (int, float)
        ):
            raise TypeError("sigma_multiplier must be a number")
        multiplier = float(self.sigma_multiplier)
        if not math.isfinite(multiplier) or not 0.25 <= multiplier <= 1.50:
            raise ValueError("sigma_multiplier must be finite and between 0.25 and 1.50")
        object.__setattr__(self, "sigma_multiplier", multiplier)
        for name in ("candidate_generated", "candidate_accepted"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be boolean")
        if self.candidate_accepted and not self.candidate_generated:
            raise ValueError("accepted candidate must have been generated")
        movement = (
            self.candidate_delta_f,
            self.candidate_delta_t,
            self.resulting_delta_hue_degree,
            self.resulting_delta_bpm,
        )
        if self.candidate_generated != all(value is not None for value in movement):
            raise ValueError("candidate movement must be complete exactly when generated")
        for name in (
            "candidate_delta_f",
            "candidate_delta_t",
            "resulting_delta_hue_degree",
            "resulting_delta_bpm",
        ):
            value = getattr(self, name)
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"{name} must be a number or null")
                converted = float(value)
                if not math.isfinite(converted):
                    raise ValueError(f"{name} must be finite")
                object.__setattr__(self, name, converted)
        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise ValueError("policy_version must be a non-empty string")
        if self.schema_version != SIGMA_SESSION_RECORD_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {SIGMA_SESSION_RECORD_SCHEMA_VERSION}"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentalAdaptiveConnectedDigitalLifeComponent(
    AdaptiveConnectedDigitalLifeComponent
):
    """Apply Stage 8A.1 policy inside each life, never in its runner."""

    def __init__(
        self,
        config: DigitalLifeConfig,
        initial_persistent_state: RelationMemoryPersistentState,
        *,
        fatigue_policy: SelectedSessionFatiguePolicy,
        sigma_policy: ScaledReferenceSigmaPolicy,
    ) -> None:
        if not isinstance(fatigue_policy, SelectedSessionFatiguePolicy):
            raise TypeError("fatigue_policy must be a SelectedSessionFatiguePolicy")
        if not isinstance(sigma_policy, ScaledReferenceSigmaPolicy):
            raise TypeError("sigma_policy must be a ScaledReferenceSigmaPolicy")
        # Base construction calls the virtual reset(), so policies must exist first.
        self._fatigue_policy = fatigue_policy
        self._sigma_policy = sigma_policy
        super().__init__(config, initial_persistent_state)

    @property
    def fatigue_policy(self) -> SelectedSessionFatiguePolicy:
        return self._fatigue_policy

    @property
    def sigma_policy(self) -> ScaledReferenceSigmaPolicy:
        return self._sigma_policy

    def reset(self) -> None:
        super().reset()
        self._e_at_session_start = self._state.e
        self._e_before_baseline: float | None = None
        self._e_after_baseline: float | None = None
        self._e_after_active: float | None = None
        self._e_before_session_end_policy: float | None = None
        self._selected_active_signal_count = 0
        self._pending_experimental_final_state: RelationMemoryPersistentState | None = None
        self._fatigue_session_record: ExperimentalFatigueSessionRecord | None = None

    def _calculate_e_after_feedback(self, e: object, s: object, g: object) -> float:
        return self._fatigue_policy.calculate_e_next(e, s, g)

    def _transition_relation_memory(
        self,
        persistent_state: RelationMemoryPersistentState,
        session_state: RelationMemorySessionState,
        transition_input: RelationMemoryTransitionInput,
    ) -> RelationMemoryTransitionResult:
        return apply_relation_memory_transition_with_sigma_multiplier(
            persistent_state,
            session_state,
            transition_input,
            sigma_multiplier=self._sigma_policy.sigma_multiplier,
        )

    def _handle_finalized_relation_state(
        self,
        state: RelationMemoryPersistentState,
    ) -> None:
        if self._pending_experimental_final_state is not None:
            raise RuntimeError("experimental final state is already pending")
        self._pending_experimental_final_state = state

    def handle_interoceptive_feedback(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        super().handle_interoceptive_feedback(event, engine)
        record = self._second_round_records[-1]
        if self._e_before_baseline is None:
            self._e_before_baseline = record.e_before
        if record.s == 1:
            self._e_after_active = record.e_after
            if record.g == 1:
                self._selected_active_signal_count += 1
        elif record.closing_evaluation_attribution:
            self._e_before_session_end_policy = record.e_after
        else:
            self._e_after_baseline = record.e_after

    def finalize_session_end_state_policy(self) -> None:
        """Publish final state only at the all-life pre-release closing barrier."""

        pending = self._pending_experimental_final_state
        if pending is None:
            raise RuntimeError("experimental closing policy has no pending final state")
        if self.has_pending_second_round():
            raise RuntimeError("experimental closing policy preceded second-round completion")
        if not self._second_round_records[-1].closing_evaluation_attribution:
            raise RuntimeError("experimental closing policy requires closing attribution")
        required = {
            "e_before_baseline": self._e_before_baseline,
            "e_after_baseline": self._e_after_baseline,
            "e_after_active": self._e_after_active,
            "e_before_session_end_policy": self._e_before_session_end_policy,
        }
        if missing := [name for name, value in required.items() if value is None]:
            raise RuntimeError(
                "experimental fatigue trajectory is incomplete: " + ", ".join(missing)
            )
        assert self._e_before_baseline is not None
        assert self._e_after_baseline is not None
        assert self._e_after_active is not None
        assert self._e_before_session_end_policy is not None
        decision = self._fatigue_policy.decide_session_end(
            self._e_before_session_end_policy,
            self._selected_active_signal_count,
        )
        state_after_policy = replace(pending, e=decision.e_after_policy)
        fatigue_record = ExperimentalFatigueSessionRecord(
            digital_life_id=self.config.digital_life_id,
            e_at_session_start=self._e_at_session_start,
            e_before_baseline=self._e_before_baseline,
            e_after_baseline=self._e_after_baseline,
            e_after_active=self._e_after_active,
            e_before_session_end_policy=self._e_before_session_end_policy,
            e_after_session_end_policy=state_after_policy.e,
            selected_active_signal_count=self._selected_active_signal_count,
            full_recovery_applied=decision.full_recovery_applied,
            selected_session_fatigue_target=(
                self._fatigue_policy.selected_session_fatigue_target
            ),
            eta_selected=self._fatigue_policy.eta_selected,
            rho_reference=self._fatigue_policy.rho_reference,
            selected_policy_version=self._fatigue_policy.selected_policy_version,
            session_end_policy_version=self._fatigue_policy.session_end_policy_version,
        )
        # All fallible policy and record validation is complete before the state is
        # published. A later engine error still leaves the multi-session runner's
        # handoff untouched because it commits only a successful whole session.
        self._state.e = state_after_policy.e
        self._working_persistent_state = state_after_policy
        self._commit_final_persistent_state(state_after_policy)
        self._fatigue_session_record = fatigue_record
        self._pending_experimental_final_state = None

    def fatigue_session_record(self) -> ExperimentalFatigueSessionRecord | None:
        return self._fatigue_session_record

    def sigma_session_record(self) -> ExperimentalSigmaSessionRecord | None:
        decision_record = next(
            (
                record
                for record in self._relation_transition_records
                if record.bundle_index == 0
                and record.g == 1
                and record.w is not None
                and record.sigma is not None
            ),
            None,
        )
        if decision_record is None:
            return None
        assert decision_record.w is not None
        assert decision_record.sigma is not None
        scaled = self._sigma_policy.at_w(
            decision_record.w,
            decision_record.sigma_min,
            decision_record.sigma_max,
        )
        if decision_record.sigma != scaled.effective_sigma:
            raise RuntimeError("transition sigma differs from the injected sigma policy")
        trial = decision_record.k_trial
        if trial is None:
            delta_f = delta_t = delta_hue = delta_bpm = None
        else:
            anchor = decision_record.k_anchor_before
            delta_f = trial[0] - anchor[0]
            delta_t = trial[2] - anchor[2]
            anchor_b = self._map_k_to_b(anchor)
            trial_b = self._map_k_to_b(trial)
            mapper = GardenLightMapperConfig()
            anchor_light = map_active_b_to_light(anchor_b, mapper)
            trial_light = map_active_b_to_light(trial_b, mapper)
            delta_hue = trial_light.hue_degree - anchor_light.hue_degree
            delta_bpm = trial_light.blink_bpm - anchor_light.blink_bpm
        return ExperimentalSigmaSessionRecord(
            digital_life_id=self.config.digital_life_id,
            w_anchor_session=decision_record.w,
            reference_sigma_min=decision_record.sigma_min,
            reference_sigma_max=decision_record.sigma_max,
            reference_sigma_at_w=scaled.reference_sigma,
            sigma_multiplier=scaled.multiplier,
            effective_sigma=scaled.effective_sigma,
            candidate_generated=trial is not None,
            candidate_accepted=(
                self._relation_session_state.adoption_result == "accepted"
            ),
            candidate_delta_f=delta_f,
            candidate_delta_t=delta_t,
            resulting_delta_hue_degree=delta_hue,
            resulting_delta_bpm=delta_bpm,
            policy_version=scaled.policy_version,
        )

    def _map_k_to_b(
        self,
        k: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        return intrinsic_b_mapping(
            k,
            f_min=self.config.f_min,
            f_max=self.config.f_max,
            a_fixed=self.config.a_fixed,
            t_min=self.config.t_min,
            t_max=self.config.t_max,
            d_fixed=self.config.d_fixed,
        )


__all__ = [
    "ExperimentalAdaptiveConnectedDigitalLifeComponent",
    "ExperimentalFatigueSessionRecord",
    "ExperimentalSigmaSessionRecord",
    "FATIGUE_SESSION_RECORD_SCHEMA_VERSION",
    "SIGMA_SESSION_RECORD_SCHEMA_VERSION",
]
