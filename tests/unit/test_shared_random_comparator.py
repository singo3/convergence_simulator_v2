"""Condition-independent shared random cache, projection, and checksum."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    RANDOM_ARM,
    build_participants,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.output_policy import (
    deterministic_random_session_outputs,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.profiles import (
    base_profile_payloads,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    CONDITION_IDS,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.shared_random import (
    clone_shared_random_for_condition,
    shared_random_cache_key,
    shared_random_result_checksum,
)


def _participant():
    return build_participants(
        user_type_ids=("green_hue_dominant_broad_bpm",),
        participants_per_type=1,
        base_master_seed=20260806,
        profile_payloads=base_profile_payloads(),
    )[0]


def _bundle(condition_id: str = "v2_reference") -> BundleOutcome:
    return BundleOutcome(
        participant_id=_participant().participant_id,
        user_type_id=_participant().user_type_id,
        response_strength_scale=1.0,
        condition_id=condition_id,
        arm=RANDOM_ARM,
        session_index=0,
        bundle_index=0,
        bundle_role="anchor",
        evaluation_quality="accepted",
        valid_for_analysis=True,
        baseline_rmssd_ms=20.0,
        bundle_rmssd_ms=22.0,
        delta_rmssd_ms=2.0,
        baseline_n=0.2,
        bundle_n=0.3,
        w=0.5,
        w_anchor_session=None,
        displayed_life_id="life-green",
        displayed_hue_degree=125.0,
        displayed_blink_bpm=100.0,
        displayed_b=(0.34, 0.5, 0.58, 0.5),
        anchor_or_trial="random",
        adoption_result=None,
        source_participant_id=None,
        source_session_index=None,
        source_bundle_index=None,
        target_rmssd_used_for_future_output=False,
        physiology_seed=123,
        output_seed=456,
        event_digest="a" * 64,
        data_digest="b" * 64,
    )


def _session(condition_id: str = "v2_reference") -> SessionOutcome:
    return SessionOutcome(
        participant_id=_participant().participant_id,
        user_type_id=_participant().user_type_id,
        response_strength_scale=1.0,
        condition_id=condition_id,
        arm=RANDOM_ARM,
        session_index=0,
        physiology_seed=123,
        baseline_rmssd_ms=20.0,
        bundle_rmssd_ms=(22.0, 22.0, 22.0),
        bundle_delta_rmssd_ms=(2.0, 2.0, 2.0),
        mean_valid_bundle_delta_rmssd_ms=2.0,
        median_valid_bundle_delta_rmssd_ms=2.0,
        holder_id="life-green",
        bundle_life_ids=("life-green",) * 3,
        bundle_hue_degrees=(125.0,) * 3,
        bundle_blink_bpms=(100.0,) * 3,
        representative_life_id="life-green",
        representative_hue_degree=125.0,
        representative_blink_bpm=100.0,
        actual_bundle2_evaluation_output={"life": "life-green"},
        final_committed_anchor=None,
        exploration_decision=None,
        candidate_generated=False,
        adoption_result=None,
        valid_bundle_count=3,
        session_valid=True,
        invalid_reason=None,
        source_participant_id=None,
        output_sequence_digest="c" * 64,
    )


def test_cache_key_has_required_fields_and_no_condition_factor() -> None:
    key = shared_random_cache_key(
        _participant(),
        maximum_sessions=24,
        code_fingerprint="f" * 64,
    )
    values = key.to_dict()
    assert {
        "participant_id",
        "user_type_id",
        "physiology_seed",
        "maximum_sessions",
        "random_output_version",
        "code_fingerprint",
    }.issubset(values)
    assert not {"condition_id", "recovery", "fatigue", "sigma"} & set(values)


def test_cache_key_is_deterministic_and_participant_specific() -> None:
    participant = _participant()
    first = shared_random_cache_key(
        participant,
        maximum_sessions=24,
        code_fingerprint="f" * 64,
    )
    second = shared_random_cache_key(
        participant,
        maximum_sessions=24,
        code_fingerprint="f" * 64,
    )
    assert first.digest == second.digest
    other = replace(participant, participant_id="different__p001")
    assert shared_random_cache_key(
        other,
        maximum_sessions=24,
        code_fingerprint="f" * 64,
    ).digest != first.digest


@pytest.mark.parametrize("condition_id", CONDITION_IDS)
def test_one_random_result_projects_identically_to_all_conditions(
    condition_id: str,
) -> None:
    bundles = (_bundle(),)
    sessions = (_session(),)
    projected_bundles, projected_sessions = clone_shared_random_for_condition(
        bundles,
        sessions,
        condition_id=condition_id,
    )
    assert projected_bundles[0].condition_id == condition_id
    assert projected_sessions[0].condition_id == condition_id
    assert projected_sessions[0].physiology_seed == sessions[0].physiology_seed
    assert projected_sessions[0].bundle_delta_rmssd_ms == sessions[0].bundle_delta_rmssd_ms
    assert projected_sessions[0].output_sequence_digest == sessions[0].output_sequence_digest
    assert shared_random_result_checksum(projected_bundles, projected_sessions) == (
        shared_random_result_checksum(bundles, sessions)
    )


def test_logical_condition_changes_only_wrapper_data_digest() -> None:
    bundles, sessions = clone_shared_random_for_condition(
        (_bundle(),),
        (_session(),),
        condition_id="full_recovery_sigma100",
    )
    assert bundles[0].data_digest != _bundle().data_digest
    assert bundles[0].event_digest == _bundle().event_digest
    assert sessions[0].output_sequence_digest == _session().output_sequence_digest


def test_random_output_seed_and_sequence_have_no_condition_input() -> None:
    first = deterministic_random_session_outputs(
        validation_master_seed=20260806,
        participant_id=_participant().participant_id,
        session_index=3,
    )
    second = deterministic_random_session_outputs(
        validation_master_seed=20260806,
        participant_id=_participant().participant_id,
        session_index=3,
    )
    assert first == second
    assert all(
        item.output_seed == other.output_seed
        for item, other in zip(first, second, strict=True)
    )


@pytest.mark.parametrize("fingerprint", ("short", "z" * 64))
def test_cache_key_rejects_invalid_fingerprint(fingerprint: str) -> None:
    with pytest.raises((ValueError, TypeError)):
        shared_random_cache_key(
            _participant(),
            maximum_sessions=24,
            code_fingerprint=fingerprint,
        )
