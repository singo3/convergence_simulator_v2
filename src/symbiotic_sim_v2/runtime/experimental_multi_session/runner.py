"""GUI-independent single-condition Stage 8A.1 multi-session runner."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType
from typing import Any

from symbiotic_sim_v2.digital_life.config import (
    DigitalLifeConfig,
    digital_life_config_for_role,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    relation_memory_state_map_from_dict,
    relation_memory_state_map_to_dict,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.condition import (
    FatigueSigmaCondition,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    SelectedSessionFatiguePolicy,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.sigma_policy import (
    ScaledReferenceSigmaPolicy,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.multi_session.session_seed import (
    SESSION_DURATION_US,
    global_time_us,
    physiology_root_seed_for_session,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    stationary_light_response_config_v2,
    stationary_user_type_profile_v2,
)

from .component_factory import (
    create_experimental_adaptive_relation_memory_closed_loop_simulation,
)
from .session_outcome import (
    ExperimentalSessionOutcome,
    experimental_session_outcome_from_simulation,
)
from .state import FatigueSigmaExperimentState

type SimulationFactory = Callable[..., AdaptiveRelationMemoryClosedLoopSimulation]
type BoundaryCallback = Callable[[int, int], None]
type CancelCheck = Callable[[], bool]


def _life_configs(
    values: Sequence[DigitalLifeConfig] | None,
) -> tuple[DigitalLifeConfig, DigitalLifeConfig, DigitalLifeConfig]:
    canonical = tuple(
        digital_life_config_for_role(role) for role in ("red", "green", "blue")
    )
    configs = canonical if values is None else tuple(values)
    if configs != canonical:
        raise ValueError("Stage 8A.1 requires the unchanged red/green/blue roster")
    return configs  # type: ignore[return-value]


def _validated_states(
    values: Mapping[str, RelationMemoryPersistentState] | None,
    *,
    life_ids: tuple[str, str, str],
) -> Mapping[str, RelationMemoryPersistentState]:
    if values is None:
        return MappingProxyType(
            {
                life_id: RelationMemoryPersistentState.fresh(life_id)
                for life_id in life_ids
            }
        )
    encoded = relation_memory_state_map_to_dict(
        values,
        expected_digital_life_ids=life_ids,
    )
    return relation_memory_state_map_from_dict(
        encoded,
        expected_digital_life_ids=life_ids,
    )


class FatigueSigmaSingleConditionRunner:
    """Run independent 240-second sessions with atomic experimental handoff."""

    def __init__(
        self,
        condition: FatigueSigmaCondition | None = None,
        *,
        compare_reference_arm: bool = False,
        initial_persistent_state_by_life: Mapping[
            str, RelationMemoryPersistentState
        ]
        | None = None,
        resume_state: FatigueSigmaExperimentState | None = None,
        digital_life_configs: Sequence[DigitalLifeConfig] | None = None,
        experimental_simulation_factory: SimulationFactory = (
            create_experimental_adaptive_relation_memory_closed_loop_simulation
        ),
        reference_simulation_factory: SimulationFactory = (
            create_adaptive_relation_memory_closed_loop_simulation
        ),
    ) -> None:
        if not callable(experimental_simulation_factory):
            raise TypeError("experimental_simulation_factory must be callable")
        if not callable(reference_simulation_factory):
            raise TypeError("reference_simulation_factory must be callable")
        if resume_state is not None and initial_persistent_state_by_life is not None:
            raise ValueError("resume_state and initial persistent states are exclusive")
        if resume_state is not None and not isinstance(
            resume_state, FatigueSigmaExperimentState
        ):
            raise TypeError("resume_state must be a FatigueSigmaExperimentState")
        self._configs = _life_configs(digital_life_configs)
        self._life_ids = tuple(config.digital_life_id for config in self._configs)
        if resume_state is None:
            self._condition = condition or FatigueSigmaCondition.create()
            if not isinstance(self._condition, FatigueSigmaCondition):
                raise TypeError("condition must be a FatigueSigmaCondition")
            if not isinstance(compare_reference_arm, bool):
                raise TypeError("compare_reference_arm must be boolean")
            self._compare_reference = compare_reference_arm
            initial = _validated_states(
                initial_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            self._initial_states = initial
            self._states = initial
            reference_initial = _validated_states(
                initial_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            self._reference_initial_states = reference_initial
            self._reference_states = reference_initial
            self._outcomes: list[ExperimentalSessionOutcome] = []
            self._reference_outcomes: list[ExperimentalSessionOutcome] = []
            self._next_session_index = 0
            self._stopped_on_error = False
        else:
            if condition is not None and condition != resume_state.condition:
                raise ValueError("resume state and requested condition differ")
            if compare_reference_arm != resume_state.reference_arm_enabled:
                raise ValueError("resume reference-arm setting differs")
            self._condition = resume_state.condition
            self._compare_reference = resume_state.reference_arm_enabled
            self._initial_states = _validated_states(
                resume_state.initial_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            self._states = _validated_states(
                resume_state.current_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            self._reference_initial_states = _validated_states(
                resume_state.reference_initial_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            self._reference_states = _validated_states(
                resume_state.reference_current_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            self._outcomes = list(resume_state.session_outcomes)
            self._reference_outcomes = list(resume_state.reference_session_outcomes)
            self._next_session_index = resume_state.next_session_index
            self._stopped_on_error = resume_state.stopped_on_error
        self._profile = stationary_user_type_profile_v2(self._condition.user_type_id)
        self._light_response_config = stationary_light_response_config_v2(self._profile)
        self._virtual_user_template = VirtualUserConfig(
            duration_seconds=SESSION_DURATION_US // 1_000_000
        )
        self._fatigue_policy = SelectedSessionFatiguePolicy(
            self._condition.selected_session_fatigue_target,
            self._condition.unselected_session_end_recovery_fraction,
        )
        self._sigma_policy = ScaledReferenceSigmaPolicy(
            self._condition.sigma_multiplier
        )
        self._experimental_factory = experimental_simulation_factory
        self._reference_factory = reference_simulation_factory
        self._current_simulation: AdaptiveRelationMemoryClosedLoopSimulation | None = None
        self._current_reference_simulation: (
            AdaptiveRelationMemoryClosedLoopSimulation | None
        ) = None
        self._previous_engine: object | None = None
        self._previous_reference_engine: object | None = None

    @property
    def condition(self) -> FatigueSigmaCondition:
        return self._condition

    @property
    def user_type_profile(self):
        return self._profile

    @property
    def compare_reference_arm(self) -> bool:
        return self._compare_reference

    @property
    def stopped_on_error(self) -> bool:
        return self._stopped_on_error

    @property
    def can_run_next_session(self) -> bool:
        return (
            not self._stopped_on_error
            and self._next_session_index < self._condition.maximum_sessions
        )

    @property
    def current_simulation(self) -> AdaptiveRelationMemoryClosedLoopSimulation | None:
        return self._current_simulation

    @property
    def current_reference_simulation(
        self,
    ) -> AdaptiveRelationMemoryClosedLoopSimulation | None:
        return self._current_reference_simulation

    def session_outcomes(self) -> tuple[ExperimentalSessionOutcome, ...]:
        return tuple(self._outcomes)

    def reference_session_outcomes(self) -> tuple[ExperimentalSessionOutcome, ...]:
        return tuple(self._reference_outcomes)

    def current_persistent_state_by_life(
        self,
    ) -> Mapping[str, RelationMemoryPersistentState]:
        return self._states

    def run_next_session(self) -> ExperimentalSessionOutcome:
        if self._stopped_on_error:
            raise RuntimeError("runner stopped after an invalid or incomplete session")
        if self._next_session_index >= self._condition.maximum_sessions:
            raise RuntimeError("maximum_sessions has already been reached")
        index = self._next_session_index
        seed = physiology_root_seed_for_session(
            master_seed=self._condition.master_seed,
            stationary_user_type_id=self._condition.user_type_id,
            session_index=index,
            policy=self._condition.session_seed_policy,
        )
        experimental, simulation = self._execute_arm(
            index=index,
            seed=seed,
            reference_arm=False,
            states=self._states,
        )
        reference: ExperimentalSessionOutcome | None = None
        reference_simulation = None
        if self._compare_reference:
            reference, reference_simulation = self._execute_arm(
                index=index,
                seed=seed,
                reference_arm=True,
                states=self._reference_states,
            )
        self._current_simulation = simulation
        self._current_reference_simulation = reference_simulation
        pair_failure_reason: str | None = None
        if not experimental.valid_for_convergence:
            pair_failure_reason = (
                "paired_experimental_invalid:"
                f"{experimental.invalid_reason or 'unknown_reason'}"
            )
        elif reference is not None and not reference.valid_for_convergence:
            pair_failure_reason = (
                "paired_reference_invalid:"
                f"{reference.invalid_reason or 'unknown_reason'}"
            )
        if pair_failure_reason is None:
            try:
                self._validate_handoff(experimental, self._states, experimental=True)
                if reference is not None:
                    self._validate_handoff(
                        reference,
                        self._reference_states,
                        experimental=False,
                    )
            except Exception as exc:
                pair_failure_reason = (
                    f"handoff_validation_error:{type(exc).__name__}:{exc}"
                )
        if pair_failure_reason is not None:
            experimental = self._invalidate_for_atomic_pair(
                experimental,
                pair_failure_reason,
            )
            if reference is not None:
                reference = self._invalidate_for_atomic_pair(
                    reference,
                    pair_failure_reason,
                )
        valid_pair = experimental.valid_for_convergence and (
            reference is None or reference.valid_for_convergence
        )
        self._outcomes.append(experimental)
        if reference is not None:
            self._reference_outcomes.append(reference)
        self._next_session_index += 1
        if valid_pair:
            self._states = _validated_states(
                experimental.final_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            if reference is not None:
                self._reference_states = _validated_states(
                    reference.final_persistent_state_by_life,
                    life_ids=self._life_ids,
                )
        else:
            # Neither arm is committed when a paired comparison is incomplete.
            self._stopped_on_error = True
        return experimental

    def run_all(
        self,
        *,
        cancel_check: CancelCheck | None = None,
        boundary_callback: BoundaryCallback | None = None,
    ) -> FatigueSigmaExperimentState:
        if cancel_check is not None and not callable(cancel_check):
            raise TypeError("cancel_check must be callable")
        if boundary_callback is not None and not callable(boundary_callback):
            raise TypeError("boundary_callback must be callable")
        while self.can_run_next_session:
            if cancel_check is not None and cancel_check():
                break
            outcome = self.run_next_session()
            if boundary_callback is not None:
                boundary_callback(
                    self._next_session_index,
                    self._condition.maximum_sessions,
                )
            if not outcome.valid_for_convergence:
                break
        return self.state()

    def reset(self) -> FatigueSigmaExperimentState:
        self._states = self._initial_states
        self._reference_states = self._reference_initial_states
        self._outcomes.clear()
        self._reference_outcomes.clear()
        self._next_session_index = 0
        self._stopped_on_error = False
        self._current_simulation = None
        self._current_reference_simulation = None
        self._previous_engine = None
        self._previous_reference_engine = None
        return self.state()

    def state(self) -> FatigueSigmaExperimentState:
        return FatigueSigmaExperimentState(
            condition=self._condition,
            initial_persistent_state_by_life=self._initial_states,
            current_persistent_state_by_life=self._states,
            session_outcomes=tuple(self._outcomes),
            reference_arm_enabled=self._compare_reference,
            reference_initial_persistent_state_by_life=self._reference_initial_states,
            reference_current_persistent_state_by_life=self._reference_states,
            reference_session_outcomes=tuple(self._reference_outcomes),
            next_session_index=self._next_session_index,
            stopped_on_error=self._stopped_on_error,
        )

    def result(self):
        from symbiotic_sim_v2.experiments.fatigue_sigma.result import (
            build_single_condition_result,
        )

        return build_single_condition_result(self.state(), self._profile)

    def _execute_arm(
        self,
        *,
        index: int,
        seed: int,
        reference_arm: bool,
        states: Mapping[str, RelationMemoryPersistentState],
    ) -> tuple[
        ExperimentalSessionOutcome,
        AdaptiveRelationMemoryClosedLoopSimulation | None,
    ]:
        virtual_user_config = replace(self._virtual_user_template, root_seed=seed)
        try:
            kwargs: dict[str, Any] = {
                "virtual_user_config": virtual_user_config,
                "digital_life_configs": self._configs,
                "light_response_config": self._light_response_config,
                "initial_persistent_states_by_life_id": states,
            }
            if reference_arm:
                simulation = self._reference_factory(**kwargs)
            else:
                simulation = self._experimental_factory(
                    **kwargs,
                    fatigue_policy=self._fatigue_policy,
                    sigma_policy=self._sigma_policy,
                )
            adaptive_digital_life_components(simulation)
            previous = (
                self._previous_reference_engine if reference_arm else self._previous_engine
            )
            if simulation.engine is previous:
                raise RuntimeError("session factory reused an engine")
            if reference_arm:
                self._previous_reference_engine = simulation.engine
            else:
                self._previous_engine = simulation.engine
            self._validate_fresh_boundary(simulation, states, seed)
        except Exception as exc:
            return (
                self._failed_outcome(
                    index,
                    seed,
                    reference_arm=reference_arm,
                    reason=f"factory_error:{type(exc).__name__}:{exc}",
                    states=states,
                ),
                None,
            )
        execution_error: Exception | None = None
        try:
            simulation.engine.run_until_end()
        except Exception as exc:
            execution_error = exc
        try:
            outcome = experimental_session_outcome_from_simulation(
                simulation,
                session_index=index,
                physiology_root_seed=seed,
                user_type_id=self._condition.user_type_id,
                reference_arm=reference_arm,
                execution_error=execution_error,
            )
        except Exception as exc:
            local_time = simulation.engine.clock.current_time_us
            if not isinstance(local_time, int) or not 0 <= local_time <= SESSION_DURATION_US:
                local_time = 0
            outcome = self._failed_outcome(
                index,
                seed,
                reference_arm=reference_arm,
                reason=f"outcome_projection_error:{type(exc).__name__}:{exc}",
                states=states,
                local_time_us=local_time,
            )
        return outcome, simulation

    def _validate_fresh_boundary(
        self,
        simulation: AdaptiveRelationMemoryClosedLoopSimulation,
        states: Mapping[str, RelationMemoryPersistentState],
        seed: int,
    ) -> None:
        if simulation.engine.clock.current_time_us != 0:
            raise RuntimeError("new engine must start at local time zero")
        if simulation.engine.clock.end_time_us != SESSION_DURATION_US:
            raise RuntimeError("Stage 8A.1 sessions must end at 240 seconds")
        if simulation.virtual_user_config.root_seed != seed:
            raise RuntimeError("VirtualUser root seed differs from seed policy")
        if simulation.light_response_config != self._light_response_config:
            raise RuntimeError("stationary preference changed between sessions")
        snapshot = simulation.garden_input_component.snapshot()
        if snapshot.baseline_available or snapshot.n_baseline_session is not None:
            raise RuntimeError("session-local Garden baseline was not reset")
        for life_id, component in adaptive_digital_life_components(simulation).items():
            if component.initial_persistent_state() != states[life_id]:
                raise RuntimeError("initial state differs from committed handoff")
            local = component.relation_memory_session_state()
            if (
                local.w_anchor_session is not None
                or local.k_trial is not None
                or local.exploration_decision is not None
            ):
                raise RuntimeError("session-local relation state was not reset")

    def _validate_handoff(
        self,
        outcome: ExperimentalSessionOutcome,
        before_states: Mapping[str, RelationMemoryPersistentState],
        *,
        experimental: bool,
    ) -> None:
        if not outcome.valid_for_convergence:
            raise RuntimeError("invalid session cannot commit persistent state")
        expected_seed = physiology_root_seed_for_session(
            master_seed=self._condition.master_seed,
            stationary_user_type_id=self._condition.user_type_id,
            session_index=outcome.session_index,
            policy=self._condition.session_seed_policy,
        )
        if outcome.physiology_root_seed != expected_seed:
            raise RuntimeError("outcome root seed differs from the condition policy")
        if outcome.user_type_id != self._condition.user_type_id:
            raise RuntimeError("outcome user type differs from the condition")
        if outcome.reference_arm == experimental:
            raise RuntimeError("outcome arm metadata differs from the handoff target")
        if dict(outcome.initial_persistent_state_by_life) != dict(before_states):
            raise RuntimeError("outcome initial state differs from committed handoff")
        for life_id in self._life_ids:
            before = before_states[life_id]
            after = outcome.final_persistent_state_by_life[life_id]
            if after.session_count != before.session_count + 1:
                raise RuntimeError("normal closing must increment session_count once")
            if after.trial_count < before.trial_count:
                raise RuntimeError("trial_count cannot decrease")
            if (
                after.profile_version,
                after.algorithm_version,
                after.state_schema_version,
            ) != (
                before.profile_version,
                before.algorithm_version,
                before.state_schema_version,
            ):
                raise RuntimeError("persistent-state versions changed")
            if experimental:
                fatigue = outcome.fatigue_trajectory_by_life[life_id]
                if after.e != fatigue["e_after_session_end_policy"]:
                    raise RuntimeError("component-owned fatigue policy differs from final E")
                selected = fatigue["selected_active_signal_count"]
                recovered = fatigue["full_recovery_applied"]
                if (selected == 0) != recovered:
                    raise RuntimeError("unselected recovery audit is inconsistent")
                if selected == 0 and after.e != 0.0:
                    raise RuntimeError("unselected life did not fully recover")

    @staticmethod
    def _invalidate_for_atomic_pair(
        outcome: ExperimentalSessionOutcome,
        reason: str,
    ) -> ExperimentalSessionOutcome:
        """Exclude one completed audit from convergence without erasing engine truth."""

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("atomic pair invalidation requires a non-empty reason")
        existing = outcome.invalid_reason
        combined = reason if existing is None else f"{existing};{reason}"
        return replace(
            outcome,
            valid_for_convergence=False,
            invalid_reason=combined,
        )

    def _failed_outcome(
        self,
        session_index: int,
        seed: int,
        *,
        reference_arm: bool,
        reason: str,
        states: Mapping[str, RelationMemoryPersistentState],
        local_time_us: int = 0,
    ) -> ExperimentalSessionOutcome:
        return ExperimentalSessionOutcome(
            session_index=session_index,
            local_time_us=local_time_us,
            global_time_us=global_time_us(session_index, local_time_us),
            valid_for_convergence=False,
            invalid_reason=reason,
            engine_completed=False,
            physiology_root_seed=seed,
            user_type_id=self._condition.user_type_id,
            reference_arm=reference_arm,
            holder_id=None,
            holder_role=None,
            initial_persistent_state_by_life=states,
            final_persistent_state_by_life={},
            holder_final_k_anchor=None,
            holder_final_hue_degree=None,
            holder_final_blink_bpm=None,
            exploration_decision=None,
            adoption_result=None,
            candidate_generated=False,
            candidate_accepted=False,
            holder_W_anchor_session=None,
            holder_W_trial_1=None,
            holder_W_trial_2=None,
            fatigue_trajectory_by_life={},
            sigma_trajectory_by_life={},
            bundle_presentations=(),
            session_digest=None,
        )


__all__ = [
    "BoundaryCallback",
    "CancelCheck",
    "FatigueSigmaSingleConditionRunner",
    "SimulationFactory",
]
