"""Stage 8A.1 policy ownership, closing barrier, and factory integration."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.fatigue_policy import (
    SelectedSessionFatiguePolicy,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.sigma_policy import (
    ScaledReferenceSigmaPolicy,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.component_factory import (
    create_experimental_adaptive_relation_memory_closed_loop_simulation,
    experimental_adaptive_digital_life_components,
)

LIFE_IDS = ("life-red", "life-green", "life-blue")


def nonzero_states() -> dict[str, RelationMemoryPersistentState]:
    return {
        life_id: replace(RelationMemoryPersistentState.fresh(life_id), e=0.4)
        for life_id in LIFE_IDS
    }


@pytest.fixture(scope="module")
def completed_experiment():
    simulation = create_experimental_adaptive_relation_memory_closed_loop_simulation(
        fatigue_policy=SelectedSessionFatiguePolicy(0.05),
        sigma_policy=ScaledReferenceSigmaPolicy(1.0),
        initial_persistent_states_by_life_id=nonzero_states(),
    )
    simulation.engine.run_until_end()
    return simulation


def test_factory_injects_three_policy_owning_components(completed_experiment) -> None:
    components = experimental_adaptive_digital_life_components(completed_experiment)
    assert set(components) == set(LIFE_IDS)
    assert len({id(component) for component in components.values()}) == 3
    assert all(
        component.fatigue_policy.selected_session_fatigue_target == 0.05
        and component.sigma_policy.sigma_multiplier == 1.0
        for component in components.values()
    )


def test_nonholders_recover_only_at_component_owned_session_end_policy(
    completed_experiment,
) -> None:
    components = experimental_adaptive_digital_life_components(completed_experiment)
    holder_id = completed_experiment.garden_output_component.snapshot().last_assigned_holder_id
    assert holder_id in LIFE_IDS
    for life_id, component in components.items():
        initial = component.initial_persistent_state()
        final = component.final_persistent_state()
        record = component.fatigue_session_record()
        assert final is not None and record is not None
        assert initial.e == record.e_at_session_start == record.e_before_baseline == 0.4
        assert final.session_count == initial.session_count + 1
        assert final.q == component.current_persistent_state().q
        assert final.k_anchor == component.current_persistent_state().k_anchor
        assert final.trial_count == component.current_persistent_state().trial_count
        assert len(component.persistent_state_records()) == 2
        assert component.persistent_state_records()[-1].e == final.e
        if life_id == holder_id:
            assert record.selected_active_signal_count == 180
            assert not record.full_recovery_applied
            assert final.e == record.e_before_session_end_policy
            assert record.e_after_active > record.e_after_baseline
            assert final.e < record.e_after_active  # closing S=0 reference recovery
        else:
            assert record.selected_active_signal_count == 0
            assert record.full_recovery_applied
            assert record.e_before_session_end_policy > 0.0
            assert final.e == record.e_after_session_end_policy == 0.0
            assert final.q == initial.q
            assert final.k_anchor == initial.k_anchor
            assert final.trial_count == initial.trial_count


def test_sigma_record_keeps_reference_and_effective_values_distinct(
    completed_experiment,
) -> None:
    holder_id = completed_experiment.garden_output_component.snapshot().last_assigned_holder_id
    components = experimental_adaptive_digital_life_components(completed_experiment)
    assert holder_id is not None
    record = components[holder_id].sigma_session_record()
    assert record is not None
    assert record.reference_sigma_at_w == record.effective_sigma
    assert record.sigma_multiplier == 1.0
    assert record.policy_version == "scaled_reference_sigma_v0_1"
    for life_id, component in components.items():
        if life_id != holder_id:
            assert component.sigma_session_record() is None


def test_incomplete_session_never_publishes_recovery_or_final_state() -> None:
    simulation = create_experimental_adaptive_relation_memory_closed_loop_simulation(
        fatigue_policy=SelectedSessionFatiguePolicy(0.05),
        sigma_policy=ScaledReferenceSigmaPolicy(1.0),
        initial_persistent_states_by_life_id=nonzero_states(),
    )
    for _ in range(239):
        simulation.engine.step_one_second()
    components = experimental_adaptive_digital_life_components(simulation)
    assert simulation.engine.clock.current_time_us == 239_000_000
    assert all(component.final_persistent_state() is None for component in components.values())
    assert all(component.fatigue_session_record() is None for component in components.values())
    assert all(
        component.initial_persistent_state().e == 0.4
        for component in components.values()
    )


def test_reset_clears_policy_records_and_reproduces_the_same_final_states(
    completed_experiment,
) -> None:
    components = experimental_adaptive_digital_life_components(completed_experiment)
    first = {
        life_id: component.final_persistent_state() for life_id, component in components.items()
    }
    completed_experiment.engine.reset()
    assert all(component.final_persistent_state() is None for component in components.values())
    assert all(component.fatigue_session_record() is None for component in components.values())
    completed_experiment.engine.run_until_end()
    second = {
        life_id: component.final_persistent_state() for life_id, component in components.items()
    }
    assert second == first
