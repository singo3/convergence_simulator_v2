"""Strict immutable Stage 8A orchestration records and JSON boundaries."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.math import intrinsic_b_mapping
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.mapping import map_active_b_to_light
from symbiotic_sim_v2.runtime.multi_session import (
    MultiSessionRelationMemoryRunner,
    MultiSessionRelationState,
    MultiSessionRunnerConfig,
    SessionOutcome,
)


@pytest.fixture(scope="module")
def one_session_runner() -> MultiSessionRelationMemoryRunner:
    runner = MultiSessionRelationMemoryRunner()
    runner.run_next_session()
    return runner


def test_runner_config_strict_json_round_trip_and_uint32_master_seed() -> None:
    config = MultiSessionRunnerConfig(master_seed=2**32 - 1)
    assert MultiSessionRunnerConfig.from_json(config.to_json()) == config
    values = config.to_dict()
    values["unknown"] = True
    with pytest.raises(ValueError, match="unknown"):
        MultiSessionRunnerConfig.from_dict(values)
    with pytest.raises(TypeError):
        MultiSessionRunnerConfig(master_seed=True)


def test_session_outcome_is_immutable_and_strictly_round_trippable(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    outcome = one_session_runner.session_outcomes()[0]
    assert SessionOutcome.from_json(outcome.to_json()) == outcome
    with pytest.raises(TypeError):
        outcome.final_k_anchor_by_life["life-green"] = (0.0, 0.0, 0.0, 0.0)
    values = outcome.to_dict()
    del values["holder_id"]
    with pytest.raises(ValueError, match="missing"):
        SessionOutcome.from_dict(values)

    assert {record.bundle_index for record in outcome.bundle_presentations} == {
        0,
        1,
        2,
    }
    assert outcome.holder_initial_hue_degree is not None
    assert outcome.holder_initial_blink_bpm is not None
    assert outcome.candidate_generated
    assert outcome.holder_k_trial is not None
    assert outcome.holder_k_trial != outcome.holder_final_k_anchor


def test_session_outcome_rejects_duplicate_and_nonfinite_json_fields(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    outcome = one_session_runner.session_outcomes()[0]
    duplicate = outcome.to_json()[:-1] + ',"session_index":0}'
    with pytest.raises(ValueError, match="duplicate"):
        SessionOutcome.from_json(duplicate)
    values = outcome.to_dict()
    values["holder_final_hue_degree"] = float("nan")
    encoded = json.dumps(values, allow_nan=True)
    with pytest.raises(ValueError, match="non-finite"):
        SessionOutcome.from_json(encoded)


def test_session_outcome_rejects_impossible_adaptation_audit_values(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    values = one_session_runner.session_outcomes()[0].to_dict()
    values["exploration_decision"] = "banana"
    with pytest.raises(ValueError, match="exploration_decision"):
        SessionOutcome.from_dict(values)

    values = one_session_runner.session_outcomes()[0].to_dict()
    values["candidate_generated"] = False
    values["candidate_accepted"] = False
    values["adoption_result"] = "accepted"
    with pytest.raises(ValueError, match="candidate_accepted"):
        SessionOutcome.from_dict(values)

    outcome = one_session_runner.session_outcomes()[0]
    assert outcome.candidate_generated and not outcome.candidate_accepted
    with pytest.raises(ValueError, match="audited adoption result"):
        replace(
            outcome,
            adoption_result="accepted",
            candidate_accepted=True,
        )


def test_session_outcome_rejects_tampered_derived_physical_patterns(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    values = one_session_runner.session_outcomes()[0].to_dict()
    values["holder_final_hue_degree"] = 200.0
    with pytest.raises(ValueError, match="physical mapping"):
        SessionOutcome.from_dict(values)

    values = one_session_runner.session_outcomes()[0].to_dict()
    values["bundle_presentations"][0]["b_presented"][0] = 0.123
    with pytest.raises(ValueError, match="presented k"):
        SessionOutcome.from_dict(values)

    values = one_session_runner.session_outcomes()[0].to_dict()
    values["bundle_presentations"][1]["first_effective_time_us"] = 0
    values["bundle_presentations"][1]["first_global_time_us"] = 0
    with pytest.raises(ValueError, match="outside its signal interval"):
        SessionOutcome.from_dict(values)


def test_session_outcome_rejects_a_physically_consistent_but_impossible_candidate(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    outcome = one_session_runner.session_outcomes()[0]
    assert outcome.holder_role is not None
    assert outcome.holder_k_trial is not None
    forged = (0.123, 0.5, 0.987, 0.5)
    holder_config = digital_life_config_for_role(outcome.holder_role)
    forged_b = intrinsic_b_mapping(
        forged,
        f_min=holder_config.f_min,
        f_max=holder_config.f_max,
        a_fixed=holder_config.a_fixed,
        t_min=holder_config.t_min,
        t_max=holder_config.t_max,
        d_fixed=holder_config.d_fixed,
    )
    forged_light = map_active_b_to_light(forged_b, GardenLightMapperConfig())
    forged_presentations = tuple(
        replace(
            presentation,
            k_presented=forged,
            b_presented=forged_b,
            hue_degree=forged_light.hue_degree,
            blink_bpm=forged_light.blink_bpm,
        )
        if presentation.k_presented == outcome.holder_k_trial
        else presentation
        for presentation in outcome.bundle_presentations
    )

    with pytest.raises(ValueError, match="fixed Hash/reflect policy"):
        replace(outcome, bundle_presentations=forged_presentations)


def test_multi_session_state_strict_round_trip_and_count_invariants(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    state = one_session_runner.state()
    restored = MultiSessionRelationState.from_json(
        state.to_json(),
        expected_digital_life_ids=one_session_runner.digital_life_ids,
    )
    assert restored == state
    assert restored.completed_session_count == 1
    assert restored.valid_session_count == 1
    with pytest.raises(TypeError):
        restored.current_persistent_state_by_life["life-red"] = object()


def test_state_rejects_config_version_roster_and_counter_mismatches(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    state = one_session_runner.state()
    with pytest.raises(ValueError, match="completed_session_count"):
        replace(state, completed_session_count=0)
    with pytest.raises(ValueError, match="runner_version"):
        replace(state, runner_version="wrong")
    with pytest.raises(ValueError, match="relation state IDs"):
        MultiSessionRelationState.from_json(
            state.to_json(),
            expected_digital_life_ids=("life-red", "life-green", "life-other"),
        )


def test_convergence_config_is_embedded_exactly_in_state(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    state = one_session_runner.state()
    altered = replace(
        state.convergence_config,
        hue_tolerance_degree=3.0,
    )
    with pytest.raises(ValueError):
        MultiSessionRelationMemoryRunner(
            MultiSessionRunnerConfig(convergence_config=altered),
            resume_state=state,
        )


def test_state_rejects_a_tampered_full_persistent_handoff() -> None:
    runner = MultiSessionRelationMemoryRunner()
    runner.run_next_session()
    runner.run_next_session()
    values = runner.state().to_dict()
    second_initial = values["session_outcomes"][1][
        "initial_persistent_state_by_life"
    ]["life-green"]
    second_initial["q"] = 0.123

    with pytest.raises(ValueError, match="handoff"):
        MultiSessionRelationState.from_dict(
            values,
            expected_digital_life_ids=runner.digital_life_ids,
        )


def test_state_rejects_a_root_seed_impossible_under_its_saved_policy(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    values = one_session_runner.state().to_dict()
    values["session_outcomes"][0]["physiology_root_seed"] ^= 1

    with pytest.raises(ValueError, match="root seed differs"):
        MultiSessionRelationState.from_dict(
            values,
            expected_digital_life_ids=one_session_runner.digital_life_ids,
        )


def test_state_rejects_an_impossible_completed_persistent_transition(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    values = one_session_runner.state().to_dict()
    outcome = values["session_outcomes"][0]
    outcome["final_persistent_state_by_life"]["life-green"][
        "session_count"
    ] = 99
    outcome["session_count_after_by_life"]["life-green"] = 99
    values["current_persistent_state_by_life"]["life-green"]["session_count"] = 99

    with pytest.raises(ValueError, match="increment every session_count once"):
        MultiSessionRelationState.from_dict(
            values,
            expected_digital_life_ids=one_session_runner.digital_life_ids,
        )


def test_state_rejects_more_than_one_trial_increment_per_session(
    one_session_runner: MultiSessionRelationMemoryRunner,
) -> None:
    values = one_session_runner.state().to_dict()
    outcome = values["session_outcomes"][0]
    holder_id = outcome["holder_id"]
    outcome["final_persistent_state_by_life"][holder_id]["trial_count"] = 2
    outcome["trial_count_after_by_life"][holder_id] = 2
    values["current_persistent_state_by_life"][holder_id]["trial_count"] = 2

    with pytest.raises(ValueError, match="trial_count at most once"):
        MultiSessionRelationState.from_dict(
            values,
            expected_digital_life_ids=one_session_runner.digital_life_ids,
        )


def test_state_rejects_attempt_count_above_its_saved_maximum() -> None:
    runner = MultiSessionRelationMemoryRunner()
    for _ in range(5):
        runner.run_next_session()
    values = runner.state().to_dict()
    values["convergence_config"]["maximum_sessions"] = 4

    with pytest.raises(ValueError, match="exceeds maximum_sessions"):
        MultiSessionRelationState.from_dict(
            values,
            expected_digital_life_ids=runner.digital_life_ids,
        )
