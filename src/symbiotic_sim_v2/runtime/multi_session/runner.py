"""GUI-independent Stage 8A orchestration over independent Stage 5C engines."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType

from symbiotic_sim_v2.convergence import (
    ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION,
    ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION,
    ROLLING_PATTERN_CONVERGENCE_CONFIG_SCHEMA_VERSION,
    STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION,
    RollingConvergenceEvaluator,
    TruthAlignmentRecord,
    evaluate_truth_alignment,
)
from symbiotic_sim_v2.digital_life.config import (
    ALGORITHM_VERSION,
    DOCUMENT_VERSION,
    PROFILE_VERSION,
    STATE_SCHEMA_VERSION,
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
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    AdaptiveRelationMemoryClosedLoopSimulation,
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION,
    STATIONARY_GAUSSIAN_PEAK_VERSION,
    STATIONARY_PREFERENCE_LANDSCAPE_VERSION,
    STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION,
    StationaryUserTypeProfile,
    stationary_light_response_config,
    stationary_user_type_profile,
)

from .config import (
    MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION,
    MultiSessionRunnerConfig,
)
from .session_outcome import (
    MULTI_SESSION_OUTCOME_SCHEMA_VERSION,
    SessionOutcome,
    session_outcome_from_simulation,
)
from .session_seed import (
    SESSION_DURATION_US,
    global_time_us,
    physiology_root_seed_for_session,
)
from .state import (
    INITIAL_CONVERGENCE_STATE,
    MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION,
    MultiSessionRelationState,
)

type SessionSimulationFactory = Callable[..., AdaptiveRelationMemoryClosedLoopSimulation]


def _default_life_configs() -> tuple[DigitalLifeConfig, DigitalLifeConfig, DigitalLifeConfig]:
    return tuple(  # type: ignore[return-value]
        digital_life_config_for_role(role) for role in ("red", "green", "blue")
    )


def _life_configs(
    values: Sequence[DigitalLifeConfig] | None,
) -> tuple[DigitalLifeConfig, DigitalLifeConfig, DigitalLifeConfig]:
    configs = _default_life_configs() if values is None else tuple(values)
    if len(configs) != 3:
        raise ValueError("Stage 8A requires exactly three Digital Life configs")
    if any(not isinstance(config, DigitalLifeConfig) for config in configs):
        raise TypeError("digital_life_configs must contain DigitalLifeConfig values")
    if len({config.digital_life_id for config in configs}) != 3:
        raise ValueError("Stage 8A Digital Life IDs must be unique")
    expected_roles_by_id = {
        digital_life_config_for_role(role).digital_life_id: role
        for role in ("red", "green", "blue")
    }
    actual_roles_by_id = {
        config.digital_life_id: config.role for config in configs
    }
    if actual_roles_by_id != expected_roles_by_id:
        raise ValueError(
            "Stage 8A requires the fixed red/green/blue Digital Life roster"
        )
    expected_configs_by_role = {
        role: digital_life_config_for_role(role)
        for role in ("red", "green", "blue")
    }
    if {config.role: config for config in configs} != expected_configs_by_role:
        raise ValueError("Stage 8A requires the unchanged Stage 5C role configs")
    return configs  # type: ignore[return-value]


def _validated_state_map(
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
    serialized = relation_memory_state_map_to_dict(
        values,
        expected_digital_life_ids=life_ids,
    )
    return relation_memory_state_map_from_dict(
        serialized,
        expected_digital_life_ids=life_ids,
    )


def _runner_versions(
    config: MultiSessionRunnerConfig,
) -> Mapping[str, str]:
    return MappingProxyType(
        {
            "document_version": DOCUMENT_VERSION,
            "profile_version": PROFILE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "runner_version": MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION,
            "stationary_landscape_version": STATIONARY_PREFERENCE_LANDSCAPE_VERSION,
            "stationary_peak_model_version": STATIONARY_GAUSSIAN_PEAK_VERSION,
            "multi_peak_combination_version": MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION,
            "stationary_user_type_schema_version": (
                STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION
            ),
            "session_seed_policy": config.session_seed_policy,
            "session_outcome_schema_version": MULTI_SESSION_OUTCOME_SCHEMA_VERSION,
            "convergence_config_schema_version": (
                ROLLING_PATTERN_CONVERGENCE_CONFIG_SCHEMA_VERSION
            ),
            "convergence_evaluator_version": (
                ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION
            ),
            "convergence_record_schema_version": (
                ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION
            ),
            "truth_alignment_version": STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION,
            "multi_session_state_schema_version": (
                MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION
            ),
        }
    )


class MultiSessionRelationMemoryRunner:
    """Run one unchanged Stage 5C factory product per fixed-preference session."""

    def __init__(
        self,
        config: MultiSessionRunnerConfig | None = None,
        *,
        initial_persistent_state_by_life: Mapping[
            str, RelationMemoryPersistentState
        ]
        | None = None,
        resume_state: MultiSessionRelationState | None = None,
        virtual_user_config_template: VirtualUserConfig | None = None,
        digital_life_configs: Sequence[DigitalLifeConfig] | None = None,
        session_simulation_factory: SessionSimulationFactory = (
            create_adaptive_relation_memory_closed_loop_simulation
        ),
    ) -> None:
        if not callable(session_simulation_factory):
            raise TypeError("session_simulation_factory must be callable")
        self._digital_life_configs = _life_configs(digital_life_configs)
        self._life_ids = tuple(
            config.digital_life_id for config in self._digital_life_configs
        )
        if resume_state is not None and initial_persistent_state_by_life is not None:
            raise ValueError("resume_state and initial persistent states are exclusive")
        if resume_state is not None and not isinstance(
            resume_state, MultiSessionRelationState
        ):
            raise TypeError("resume_state must be a MultiSessionRelationState")

        if resume_state is None:
            self._config = config or MultiSessionRunnerConfig()
        else:
            state_config = MultiSessionRunnerConfig(
                user_type_id=resume_state.user_type_id,
                master_seed=resume_state.master_seed,
                session_seed_policy=resume_state.seed_policy,
                convergence_config=resume_state.convergence_config,
                runner_version=resume_state.runner_version,
            )
            if config is not None and config != state_config:
                raise ValueError("resume state and requested runner config differ")
            self._config = state_config
        self._profile = stationary_user_type_profile(self._config.user_type_id)
        self._light_response_config = stationary_light_response_config(self._profile)
        canonical_template = VirtualUserConfig(
            duration_seconds=SESSION_DURATION_US // 1_000_000
        )
        template = virtual_user_config_template or canonical_template
        if not isinstance(template, VirtualUserConfig):
            raise TypeError("virtual_user_config_template must be a VirtualUserConfig")
        if template.duration_seconds != SESSION_DURATION_US // 1_000_000:
            raise ValueError("Stage 8A VirtualUserConfig duration must be 240 seconds")
        if replace(template, root_seed=canonical_template.root_seed) != canonical_template:
            raise ValueError(
                "Stage 8A requires the fixed default physiology template; "
                "only the versioned session root seed may vary"
            )
        self._virtual_user_config_template = template
        self._session_simulation_factory = session_simulation_factory
        self._versions = _runner_versions(self._config)
        self._current_simulation: AdaptiveRelationMemoryClosedLoopSimulation | None = None
        self._previous_engine: object | None = None

        if resume_state is None:
            starting_states = _validated_state_map(
                initial_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            self._initial_persistent_states = starting_states
            self._current_persistent_states = starting_states
            self._outcomes: list[SessionOutcome] = []
            self._convergence_evaluator = RollingConvergenceEvaluator(
                self._config.convergence_config
            )
            self._truth_records: list[TruthAlignmentRecord] = []
            self._next_session_index = 0
            self._stopped_on_error = False
        else:
            if set(resume_state.current_persistent_state_by_life) != set(
                self._life_ids
            ):
                raise ValueError("resume state Digital Life roster differs")
            roles_by_id = {
                config.digital_life_id: config.role
                for config in self._digital_life_configs
            }
            if any(
                outcome.holder_id is not None
                and roles_by_id.get(outcome.holder_id) != outcome.holder_role
                for outcome in resume_state.session_outcomes
            ):
                raise ValueError("resume outcome holder ID and configured role differ")
            if dict(resume_state.versions) != dict(self._versions):
                raise ValueError("resume state version tuple differs from this runner")
            self._current_persistent_states = _validated_state_map(
                resume_state.current_persistent_state_by_life,
                life_ids=self._life_ids,
            )
            resume_origin = (
                resume_state.current_persistent_state_by_life
                if not resume_state.session_outcomes
                else resume_state.session_outcomes[0].initial_persistent_state_by_life
            )
            self._initial_persistent_states = _validated_state_map(
                resume_origin,
                life_ids=self._life_ids,
            )
            self._outcomes = list(resume_state.session_outcomes)
            self._convergence_evaluator = RollingConvergenceEvaluator(
                self._config.convergence_config,
                self._outcomes,
                expected_records=resume_state.convergence_records,
            )
            self._truth_records = [
                evaluate_truth_alignment(
                    record,
                    self._profile,
                    self._config.convergence_config,
                )
                for record in resume_state.convergence_records
            ]
            self._next_session_index = resume_state.next_session_index
            self._stopped_on_error = resume_state.stopped_on_error

    @property
    def config(self) -> MultiSessionRunnerConfig:
        return self._config

    @property
    def user_type_profile(self) -> StationaryUserTypeProfile:
        return self._profile

    @property
    def digital_life_ids(self) -> tuple[str, str, str]:
        return self._life_ids

    @property
    def current_simulation(self) -> AdaptiveRelationMemoryClosedLoopSimulation | None:
        """Expose only the latest complete Stage 5C bundle for existing GUI panels."""

        return self._current_simulation

    @property
    def stopped_on_error(self) -> bool:
        return self._stopped_on_error

    @property
    def can_run_next_session(self) -> bool:
        return (
            not self._stopped_on_error
            and self._next_session_index < self._config.maximum_sessions
        )

    def session_outcomes(self) -> tuple[SessionOutcome, ...]:
        return tuple(self._outcomes)

    def convergence_records(self):
        return self._convergence_evaluator.records()

    def truth_alignment_records(self) -> tuple[TruthAlignmentRecord, ...]:
        return tuple(self._truth_records)

    def current_persistent_state_by_life(
        self,
    ) -> Mapping[str, RelationMemoryPersistentState]:
        return self._current_persistent_states

    def initial_persistent_state_by_life(
        self,
    ) -> Mapping[str, RelationMemoryPersistentState]:
        return self._initial_persistent_states

    def run_next_session(self) -> SessionOutcome:
        """Execute one independent local 0..240 s engine and atomically hand off state."""

        if self._stopped_on_error:
            raise RuntimeError("multi-session runner stopped after an incomplete session")
        if self._next_session_index >= self._config.maximum_sessions:
            raise RuntimeError("maximum_sessions has already been reached")
        index = self._next_session_index
        seed = physiology_root_seed_for_session(
            master_seed=self._config.master_seed,
            stationary_user_type_id=self._config.user_type_id,
            session_index=index,
            policy=self._config.session_seed_policy,
        )
        virtual_user_config = replace(
            self._virtual_user_config_template,
            root_seed=seed,
        )
        try:
            simulation = self._session_simulation_factory(
                virtual_user_config=virtual_user_config,
                digital_life_configs=self._digital_life_configs,
                light_response_config=self._light_response_config,
                initial_persistent_states_by_life_id=self._current_persistent_states,
            )
            # Validate the factory product before dereferencing its engine. A
            # callable returning an arbitrary object is still a factory failure,
            # not an unrecorded runner exception.
            adaptive_digital_life_components(simulation)
        except Exception as exc:
            outcome = self._factory_error_outcome(index, seed, exc)
            self._record_outcome(outcome)
            self._stopped_on_error = True
            return outcome

        if simulation.engine is self._previous_engine:
            # A reused engine contains the preceding session's observations.
            # Treat this as a factory-boundary failure so the new attempt cannot
            # falsely claim that those holder, light, or final-state records were
            # produced a second time.
            outcome = self._factory_error_outcome(
                index,
                seed,
                RuntimeError("session factory reused an engine"),
            )
            self._current_simulation = simulation
            self._record_outcome(outcome)
            self._stopped_on_error = True
            return outcome
        self._previous_engine = simulation.engine
        self._current_simulation = simulation
        try:
            self._validate_fresh_session_boundary(simulation, seed)
            simulation.engine.run_until_end()
            execution_error: Exception | None = None
        except Exception as exc:
            execution_error = exc
        try:
            outcome = session_outcome_from_simulation(
                simulation,
                session_index=index,
                physiology_root_seed=seed,
                user_type_id=self._config.user_type_id,
                execution_error=execution_error,
            )
        except Exception as exc:
            outcome = self._failed_attempt_outcome(
                index,
                seed,
                invalid_reason=(
                    f"outcome_projection_error:{type(exc).__name__}:{exc}"
                ),
                local_time_us=self._safe_local_time_us(simulation),
            )
            self._record_outcome(outcome)
            self._stopped_on_error = True
            return outcome

        committed_states: Mapping[str, RelationMemoryPersistentState] | None = None
        if outcome.engine_completed and len(outcome.final_persistent_state_by_life) == 3:
            try:
                self._validate_committed_handoff(outcome)
                committed_states = _validated_state_map(
                    outcome.final_persistent_state_by_life,
                    life_ids=self._life_ids,
                )
            except Exception as exc:
                outcome = self._failed_attempt_outcome(
                    index,
                    seed,
                    invalid_reason=(
                        f"handoff_validation_error:{type(exc).__name__}:{exc}"
                    ),
                    local_time_us=outcome.local_time_us,
                )
                self._record_outcome(outcome)
                self._stopped_on_error = True
                return outcome
        else:
            self._stopped_on_error = True
        try:
            self._record_outcome(outcome)
        except Exception:
            # _record_outcome prepares evaluator and truth results before it
            # mutates history, so an unexpected diagnostic failure cannot leave
            # a half-appended session or commit its persistent state.
            self._stopped_on_error = True
            raise
        if committed_states is not None:
            self._current_persistent_states = committed_states
        return outcome

    def run_all(self) -> MultiSessionRelationState:
        """Continue to maximum_sessions, stopping only at an incomplete attempt."""

        while self.can_run_next_session:
            outcome = self.run_next_session()
            if not outcome.engine_completed:
                break
        return self.state()

    def reset(self) -> MultiSessionRelationState:
        """Clear aggregate history and return to the runner's initial states."""

        self._current_persistent_states = self._initial_persistent_states
        self._outcomes.clear()
        self._convergence_evaluator = RollingConvergenceEvaluator(
            self._config.convergence_config
        )
        self._truth_records.clear()
        self._next_session_index = 0
        self._stopped_on_error = False
        self._current_simulation = None
        self._previous_engine = None
        return self.state()

    def state(self) -> MultiSessionRelationState:
        records = self._convergence_evaluator.records()
        latest = None if not records else records[-1]
        return MultiSessionRelationState(
            runner_version=MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION,
            schema_version=MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION,
            user_type_id=self._config.user_type_id,
            master_seed=self._config.master_seed,
            seed_policy=self._config.session_seed_policy,
            convergence_config=self._config.convergence_config,
            completed_session_count=sum(
                outcome.engine_completed for outcome in self._outcomes
            ),
            valid_session_count=sum(
                outcome.valid_for_convergence for outcome in self._outcomes
            ),
            next_session_index=self._next_session_index,
            current_persistent_state_by_life=self._current_persistent_states,
            session_outcomes=tuple(self._outcomes),
            convergence_records=records,
            first_convergence_session_index=(
                None if latest is None else latest.first_convergence_session_index
            ),
            current_convergence_state=(
                INITIAL_CONVERGENCE_STATE
                if latest is None
                else latest.convergence_state
            ),
            versions=self._versions,
        )

    def _record_outcome(self, outcome: SessionOutcome) -> None:
        if outcome.session_index != self._next_session_index:
            raise RuntimeError("session outcome index differs from runner position")
        next_outcomes = (*self._outcomes, outcome)
        next_evaluator = RollingConvergenceEvaluator(
            self._config.convergence_config,
            next_outcomes,
        )
        convergence = next_evaluator.current_record()
        if convergence is None:  # pragma: no cover - impossible after append
            raise RuntimeError("recorded outcome did not produce convergence state")
        truth = evaluate_truth_alignment(
            convergence,
            self._profile,
            self._config.convergence_config,
        )
        self._outcomes.append(outcome)
        self._convergence_evaluator = next_evaluator
        self._truth_records.append(truth)
        self._next_session_index += 1

    def _factory_error_outcome(
        self,
        session_index: int,
        seed: int,
        error: Exception,
    ) -> SessionOutcome:
        return self._failed_attempt_outcome(
            session_index,
            seed,
            invalid_reason=f"factory_error:{type(error).__name__}:{error}",
        )

    def _failed_attempt_outcome(
        self,
        session_index: int,
        seed: int,
        *,
        invalid_reason: str,
        local_time_us: int = 0,
    ) -> SessionOutcome:
        initial = self._current_persistent_states
        return SessionOutcome(
            session_index=session_index,
            local_time_us=local_time_us,
            global_time_us=global_time_us(session_index, local_time_us),
            valid_for_convergence=False,
            invalid_reason=invalid_reason,
            engine_completed=False,
            physiology_root_seed=seed,
            user_type_id=self._config.user_type_id,
            holder_id=None,
            holder_role=None,
            initial_k_anchor_by_life={
                life_id: state.k_anchor for life_id, state in initial.items()
            },
            initial_persistent_state_by_life=initial,
            final_k_anchor_by_life={},
            holder_final_k_anchor=None,
            holder_final_b_f=None,
            holder_final_b_a=None,
            holder_final_b_t=None,
            holder_final_b_d=None,
            holder_final_hue_degree=None,
            holder_final_blink_bpm=None,
            exploration_decision=None,
            adoption_result=None,
            candidate_generated=False,
            candidate_accepted=False,
            holder_W_anchor_session=None,
            holder_W_trial_1=None,
            holder_W_trial_2=None,
            baseline_evaluation=None,
            bundle_0_evaluation=None,
            bundle_1_evaluation=None,
            bundle_2_evaluation=None,
            session_count_before_by_life={
                life_id: state.session_count for life_id, state in initial.items()
            },
            session_count_after_by_life={},
            trial_count_before_by_life={
                life_id: state.trial_count for life_id, state in initial.items()
            },
            trial_count_after_by_life={},
            final_persistent_state_by_life={},
            bundle_presentations=(),
            session_digest=None,
        )

    @staticmethod
    def _safe_local_time_us(
        simulation: AdaptiveRelationMemoryClosedLoopSimulation,
    ) -> int:
        value = simulation.engine.clock.current_time_us
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= SESSION_DURATION_US
        ):
            return 0
        return value

    def _validate_fresh_session_boundary(
        self,
        simulation: AdaptiveRelationMemoryClosedLoopSimulation,
        seed: int,
    ) -> None:
        if simulation.engine.clock.current_time_us != 0:
            raise RuntimeError("a new session engine must start at local time zero")
        if simulation.engine.clock.end_time_us != SESSION_DURATION_US:
            raise RuntimeError("a Stage 8A session must end at 240 seconds")
        if simulation.virtual_user_config.root_seed != seed:
            raise RuntimeError("session VirtualUser root seed differs from seed policy")
        if simulation.light_response_config is not self._light_response_config:
            raise RuntimeError("stationary user profile changed between sessions")
        garden_input = simulation.garden_input_component.snapshot()
        if (
            garden_input.baseline_available
            or garden_input.n_baseline_session is not None
            or garden_input.n_current is not None
        ):
            raise RuntimeError("new session did not reset its baseline state")
        garden_output = simulation.garden_output_component.snapshot()
        if (
            garden_output.qualification_holder_id is not None
            or garden_output.last_assigned_holder_id is not None
            or garden_output.total_touch_count != 0
        ):
            raise RuntimeError("new session did not reset Garden qualification state")
        components = adaptive_digital_life_components(simulation)
        for life_id in self._life_ids:
            component = components[life_id]
            if component.initial_persistent_state() != self._current_persistent_states[life_id]:
                raise RuntimeError("session initial state differs from committed handoff")
            session = component.relation_memory_session_state()
            if (
                session.w_anchor_session is not None
                or session.k_trial is not None
                or session.w_trial_1 is not None
                or session.w_trial_2 is not None
                or session.adaptation_phase != "anchor_evaluation"
                or session.exploration_decision is not None
            ):
                raise RuntimeError("new session did not reset relation-local state")

    def _validate_committed_handoff(self, outcome: SessionOutcome) -> None:
        for life_id in self._life_ids:
            before = self._current_persistent_states[life_id]
            after = outcome.final_persistent_state_by_life[life_id]
            if after.session_count != before.session_count + 1:
                raise RuntimeError("normal closing must increment every session_count once")
            if after.trial_count < before.trial_count:
                raise RuntimeError("trial_count cannot decrease across a session")
            if (
                after.profile_version != before.profile_version
                or after.algorithm_version != before.algorithm_version
                or after.state_schema_version != before.state_schema_version
            ):
                raise RuntimeError("persistent-state versions changed across handoff")


__all__ = [
    "MultiSessionRelationMemoryRunner",
    "SessionSimulationFactory",
]
