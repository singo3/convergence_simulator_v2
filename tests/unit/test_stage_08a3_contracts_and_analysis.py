"""Stage 8A.3 contracts, records, causal analysis, and chart semantics."""

# ruff: noqa: E501 -- dense fixture matrices are easier to audit on one line.

from __future__ import annotations

import inspect
import json
import math
from dataclasses import replace

import pytest

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.analysis import (
    bootstrap_interval,
    bootstrap_median_interval,
    bpm_history_score,
    circular_hue_distance,
    circular_linear_correlation,
    circular_mean_and_concentration,
    classify_participant_effect,
    contemporaneous_response_row,
    counterfactual_percentile,
    deterministic_counterfactual_set,
    full_pattern_history_score,
    gaussian_kernel,
    history_before_session,
    life_history_score,
    linear_slope,
    paired_arm_difference_rows,
    pattern_closeness,
    pearson_correlation,
    prospective_rows,
    rmssd_benefit_row,
    session_block_bootstrap_interval,
    spearman_correlation,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.charts import (
    hue_color,
    participant_trajectory_svg,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    ARM_IDS,
    AUTONOMOUS_ARM,
    RANDOM_ARM,
    YOKED_ARM,
    ValidationCondition,
    ValidationConfig,
    arm_contract,
    build_participants,
    validation_plan_projection,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.output_policy import (
    cyclic_yoke_map,
    deterministic_random_session_outputs,
    output_sequence_checksum,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.profiles import (
    base_profile_payloads,
    participant_profile,
    validation_user_type_profile,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
)


def bundle(
    session_index: int,
    delta: float | None,
    *,
    arm: str = AUTONOMOUS_ARM,
    bundle_index: int = 0,
    life_id: str = "life-green",
    hue: float = 125.0,
    bpm: float = 100.0,
) -> BundleOutcome:
    return BundleOutcome(
        participant_id="fixture__p001",
        user_type_id="green_hue_dominant_broad_bpm",
        response_strength_scale=1.0,
        condition_id="fixture-condition",
        arm=arm,
        session_index=session_index,
        bundle_index=bundle_index,
        bundle_role="fixture",
        evaluation_quality="accepted" if delta is not None else "rejected",
        valid_for_analysis=delta is not None,
        baseline_rmssd_ms=20.0,
        bundle_rmssd_ms=None if delta is None else 20.0 + delta,
        delta_rmssd_ms=delta,
        baseline_n=0.2,
        bundle_n=None if delta is None else 0.3,
        w=None if delta is None else 0.5,
        w_anchor_session=0.5 if arm == AUTONOMOUS_ARM else None,
        displayed_life_id=life_id,
        displayed_hue_degree=hue,
        displayed_blink_bpm=bpm,
        displayed_b=(0.34, 0.5, 0.58, 0.5),
        anchor_or_trial="anchor" if arm == AUTONOMOUS_ARM else "replay",
        adoption_result=None,
        source_participant_id="donor" if arm == YOKED_ARM else None,
        source_session_index=session_index if arm == YOKED_ARM else None,
        source_bundle_index=bundle_index if arm == YOKED_ARM else None,
        target_rmssd_used_for_future_output=arm == AUTONOMOUS_ARM,
        physiology_seed=123,
        output_seed=456 if arm == RANDOM_ARM else None,
        event_digest="a" * 64,
        data_digest="b" * 64,
    )


def session(
    index: int,
    delta: float | None,
    *,
    arm: str = AUTONOMOUS_ARM,
    life_id: str = "life-green",
    hue: float = 125.0,
    bpm: float = 100.0,
) -> SessionOutcome:
    valid = delta is not None
    values = (delta, delta, delta)
    return SessionOutcome(
        participant_id="fixture__p001",
        user_type_id="green_hue_dominant_broad_bpm",
        response_strength_scale=1.0,
        condition_id="fixture-condition",
        arm=arm,
        session_index=index,
        physiology_seed=123,
        baseline_rmssd_ms=20.0,
        bundle_rmssd_ms=(
            (None, None, None)
            if delta is None
            else (20.0 + delta, 20.0 + delta, 20.0 + delta)
        ),
        bundle_delta_rmssd_ms=values,
        mean_valid_bundle_delta_rmssd_ms=delta,
        median_valid_bundle_delta_rmssd_ms=delta,
        holder_id=life_id,
        bundle_life_ids=(life_id, life_id, life_id),
        bundle_hue_degrees=(hue, hue, hue),
        bundle_blink_bpms=(bpm, bpm, bpm),
        representative_life_id=life_id,
        representative_hue_degree=hue,
        representative_blink_bpm=bpm,
        actual_bundle2_evaluation_output={"life": life_id, "hue": hue, "bpm": bpm},
        final_committed_anchor=(0.3, 0.5, 0.5, 0.5) if arm == AUTONOMOUS_ARM else None,
        exploration_decision="hold" if arm == AUTONOMOUS_ARM else None,
        candidate_generated=False,
        adoption_result=None,
        valid_bundle_count=3 if valid else 0,
        session_valid=valid,
        invalid_reason=None if valid else "fixture-invalid",
        source_participant_id="donor" if arm == YOKED_ARM else None,
        output_sequence_digest="c" * 64,
    )


@pytest.mark.parametrize("arm", ARM_IDS)
def test_arm_contract_round_trip_and_fixed_rmssd_use(arm: str) -> None:
    contract = arm_contract(arm)
    assert type(contract).from_json(contract.to_json()) == contract
    assert contract.target_rmssd_used_for_future_output is (arm == AUTONOMOUS_ARM)
    assert contract.adaptive_state_enabled is (arm == AUTONOMOUS_ARM)


def test_unknown_arm_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        arm_contract("unknown")


@pytest.mark.parametrize(
    ("preset", "planned"),
    (("smoke", 48), ("quick", 576), ("standard", 12_960), ("robust", 64_800)),
)
def test_validation_plan_budget(preset: str, planned: int) -> None:
    config = ValidationConfig.create(validation_preset=preset)
    assert config.planned_target_session_runs == planned
    assert validation_plan_projection(config)["simulation_jobs_executed"] == 0
    assert ValidationConfig.from_json(config.to_json()) == config


def test_budget_is_rejected_not_clipped() -> None:
    smoke = ValidationConfig.create(validation_preset="smoke")
    with pytest.raises(ValueError, match="rejected rather than clipped"):
        replace(smoke, maximum_target_session_runs=47)


def test_full_event_ledger_is_limited_to_smoke() -> None:
    standard = ValidationConfig.create(validation_preset="standard")
    with pytest.raises(ValueError, match="smoke preset"):
        replace(standard, retain_details="all")
    assert replace(
        ValidationConfig.create(validation_preset="smoke"),
        retain_details="all",
    ).retain_details == "all"


@pytest.mark.parametrize(
    "changes",
    (
        {"selected_session_fatigue_target": 0.15},
        {"unselected_full_recovery": True},
        {"sigma_multiplier": 0.5},
    ),
)
def test_reference_condition_cannot_encode_experimental_policy(changes) -> None:
    reference = ValidationConfig.create(validation_preset="standard").conditions[0]
    with pytest.raises(ValueError, match="v2_reference"):
        replace(reference, **changes)


def test_nonreference_condition_requires_reused_full_recovery_policy() -> None:
    with pytest.raises(ValueError, match="unselected-full-recovery"):
        ValidationCondition(
            condition_id="unsupported-no-recovery",
            fatigue_policy="experimental_selected_target",
            selected_session_fatigue_target=0.15,
            unselected_full_recovery=False,
            sigma_multiplier=0.5,
        )


@pytest.mark.parametrize(
    "user_type_id",
    (
        "red_hue_dominant_broad_bpm",
        "green_hue_dominant_broad_bpm",
        "blue_hue_dominant_broad_bpm",
        "bpm_common_100_hue_neutral",
        "three_life_bpm_equal",
        "three_life_bpm_green_dominant",
        "green_single_peak_narrow",
        "weak_bpm_common_100",
        "flat_control",
    ),
)
def test_fixed_profiles_are_available_and_stationary(user_type_id: str) -> None:
    first = validation_user_type_profile(user_type_id)
    second = validation_user_type_profile(user_type_id)
    assert first == second
    scale = 0.0 if user_type_id == "flat_control" else 0.6
    participant = participant_profile(user_type_id, scale)
    assert participant.user_type_id == user_type_id
    if user_type_id == "flat_control":
        assert participant.maximum_respiratory_amplitude_gain_ms == 0.0


def test_participants_are_unique_arm_independent_and_condition_independent() -> None:
    first = build_participants(
        user_type_ids=("green_hue_dominant_broad_bpm", "flat_control"),
        participants_per_type=6,
        base_master_seed=7,
        profile_payloads=base_profile_payloads(),
    )
    second = build_participants(
        user_type_ids=("green_hue_dominant_broad_bpm", "flat_control"),
        participants_per_type=6,
        base_master_seed=7,
        profile_payloads=base_profile_payloads(),
    )
    assert first == second
    assert len({item.participant_id for item in first}) == 12
    assert [item.response_strength_scale for item in first[:6]] == [
        1.0,
        0.8,
        0.6,
        0.4,
        0.2,
        1.0,
    ]
    assert {item.response_strength_scale for item in first[6:]} == {0.0}


@pytest.mark.parametrize("count", (1, 2, 3, 8))
def test_cyclic_yoke_map_never_self_yokes(count: int) -> None:
    participants = build_participants(
        user_type_ids=("green_hue_dominant_broad_bpm",),
        participants_per_type=count,
        base_master_seed=9,
        profile_payloads=base_profile_payloads(),
    )
    mapping = cyclic_yoke_map(participants)
    assert len(mapping) == count
    assert all(item.donor_participant_id != item.target_participant_id for item in mapping)
    assert mapping[0].hidden_donor is (count == 1)


@pytest.mark.parametrize("session_index", range(12))
def test_random_output_is_deterministic_fixed_holder_and_in_range(session_index: int) -> None:
    first = deterministic_random_session_outputs(
        validation_master_seed=20260806,
        participant_id="fixture__p001",
        session_index=session_index,
    )
    second = deterministic_random_session_outputs(
        validation_master_seed=20260806,
        participant_id="fixture__p001",
        session_index=session_index,
    )
    assert first == second
    assert len({item.displayed_life_id for item in first}) == 1
    assert all(10.0 <= item.blink_bpm <= 165.0 for item in first)
    bands = {"red": (0.0, 10.0), "green": (120.0, 130.0), "blue": (245.0, 255.0)}
    assert all(bands[item.displayed_role][0] <= item.hue_degree <= bands[item.displayed_role][1] for item in first)
    assert output_sequence_checksum(first) == output_sequence_checksum(second)


def test_random_output_has_no_condition_or_rmssd_input() -> None:
    names = tuple(inspect.signature(deterministic_random_session_outputs).parameters)
    assert names == ("validation_master_seed", "participant_id", "session_index")


@pytest.mark.parametrize("arm", ARM_IDS)
def test_bundle_and_session_round_trip_preserve_provenance(arm: str) -> None:
    bundle_row = bundle(2, 3.5, arm=arm, bundle_index=2)
    session_row = session(2, 3.5, arm=arm)
    assert BundleOutcome.from_dict(bundle_row.to_dict()) == bundle_row
    assert SessionOutcome.from_dict(session_row.to_dict()) == session_row
    assert bundle_row.delta_rmssd_ms == 3.5
    assert session_row.actual_bundle2_evaluation_output is not None
    assert (session_row.final_committed_anchor is not None) is (arm == AUTONOMOUS_ARM)


def test_invalid_bundle_record_is_explicit_not_zero_filled() -> None:
    row = bundle(0, None)
    assert row.valid_for_analysis is False
    assert row.delta_rmssd_ms is None


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    ((359.0, 1.0, 2.0), (10.0, 350.0, 20.0), (120.0, 130.0, 10.0)),
)
def test_circular_hue_distance(first: float, second: float, expected: float) -> None:
    assert circular_hue_distance(first, second) == pytest.approx(expected)


@pytest.mark.parametrize("distance", (0.0, 1.0, 5.0, 15.0, 30.0))
def test_gaussian_kernel_is_finite(distance: float) -> None:
    value = gaussian_kernel(distance, 15.0)
    assert 0.0 < value <= 1.0


def test_history_is_strictly_past_only() -> None:
    rows = tuple(bundle(index, float(index + 1)) for index in range(6))
    history = history_before_session(rows, 3)
    assert [item.session_index for item in history] == [0, 1, 2]
    assert all(item.session_index < 3 for item in history)


def test_history_models_and_minimum_count() -> None:
    rows = (
        bundle(0, 1.0, bpm=80.0, hue=359.0),
        bundle(1, 3.0, bpm=100.0, hue=1.0),
        bundle(2, 5.0, bpm=120.0, hue=0.0),
    )
    assert life_history_score(rows, "life-green") == pytest.approx(3.0)
    assert bpm_history_score(rows, 100.0) is not None
    assert full_pattern_history_score(
        rows,
        life_id="life-green",
        hue_degree=0.0,
        blink_bpm=100.0,
    ) is not None
    assert life_history_score(rows[:2], "life-green") is None
    assert bpm_history_score(rows[:2], 100.0) is None


def test_counterfactual_grid_and_percentile() -> None:
    grid = deterministic_counterfactual_set()
    assert len(grid) == 165
    assert grid == deterministic_counterfactual_set()
    assert counterfactual_percentile(4.0, [1.0, 2.0, 3.0, 4.0, 5.0]) == 70.0
    assert counterfactual_percentile(None, [1.0]) is None


def test_contemporaneous_response_is_separate_and_hue_is_circular() -> None:
    rows = tuple(
        bundle(
            session_index=index,
            delta=delta,
            bundle_index=index % 3,
            life_id=("life-red", "life-green", "life-blue")[index % 3],
            hue=(350.0, 0.0, 10.0, 170.0, 180.0, 190.0)[index],
            bpm=50.0 + 10.0 * index,
        )
        for index, delta in enumerate((2.0, 3.0, 2.0, -2.0, -3.0, -2.0))
    )
    result = contemporaneous_response_row(rows)
    assert result["same_bundle_only"] is True
    assert result["evidence_of_target_rmssd_used_for_future_output"] is False
    assert result["same_bundle_hue_delta_rmssd_circular_linear"] is not None
    assert circular_linear_correlation([359.0, 0.0, 1.0], [1.0, 2.0, 1.0]) is not None


def test_prospective_model_excludes_current_and_future_sessions() -> None:
    bundles = tuple(
        bundle(index, float(index + 1), bundle_index=bundle_index)
        for index in range(5)
        for bundle_index in range(3)
    )
    sessions = tuple(session(index, float(index + 1)) for index in range(5))
    rows = prospective_rows(bundles, sessions)
    for row in rows:
        assert row["history_cutoff_session_index"] == row["session_index"] - 1
        assert row["history_bundle_count"] == row["session_index"] * 3
    assert rows[0]["actual_predicted_delta_rmssd_full_pattern"] is None
    assert rows[-1]["actual_predicted_delta_rmssd_full_pattern"] is not None
    assert rows[-1]["full_pattern_counterfactual_mean_predicted_delta_rmssd_ms"] is not None
    assert rows[-1]["full_pattern_counterfactual_median_predicted_delta_rmssd_ms"] is not None
    assert rows[-1]["full_pattern_actual_minus_counterfactual_mean_ms"] == pytest.approx(
        rows[-1]["full_pattern_selection_enrichment"]
    )


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    (([1.0, 2.0, 3.0], [2.0, 4.0, 6.0], 1.0), ([1.0, 1.0], [1.0, 2.0], 0.0)),
)
def test_pearson(first: list[float], second: list[float], expected: float) -> None:
    assert pearson_correlation(first, second) == pytest.approx(expected)


def test_spearman_ties_and_slope() -> None:
    assert spearman_correlation([1, 2, 3, 4], [0, 0, 1, 1]) > 0.8
    assert linear_slope([(0.0, 1.0), (1.0, 3.0), (2.0, 5.0)]) == 2.0


def test_pattern_closeness_life_and_distance() -> None:
    close = pattern_closeness(session(0, 1.0, hue=359, bpm=100), session(1, 2.0, hue=1, bpm=103))
    assert close == pytest.approx(1.0 / 1.6)
    different = pattern_closeness(
        session(0, 1.0, life_id="life-green"),
        session(1, 2.0, life_id="life-red"),
    )
    assert different == 0.0


def test_rmssd_early_middle_late_slope_and_reject_rate() -> None:
    rows = tuple(session(index, float(index + 1)) for index in range(6))
    result = rmssd_benefit_row(rows)
    assert result["early_session_mean_delta_rmssd_ms"] == 1.5
    assert result["middle_session_mean_delta_rmssd_ms"] == 3.5
    assert result["late_session_mean_delta_rmssd_ms"] == 5.5
    assert result["late_minus_early_ms"] == 4.0
    assert result["delta_rmssd_session_slope"] == 1.0


def test_paired_effect_uses_matching_valid_session_indices() -> None:
    autonomous = tuple(
        session(index, None if index == 1 else float(index + 1))
        for index in range(6)
    )
    yoked = tuple(
        session(
            index,
            None if index == 4 else 0.0,
            arm=YOKED_ARM,
        )
        for index in range(6)
    )
    benefits = (rmssd_benefit_row(autonomous), rmssd_benefit_row(yoked))
    lagged = tuple(
        {
            "participant_id": "fixture__p001",
            "condition_id": "fixture-condition",
            "arm": arm,
            "mean_full_pattern_selection_enrichment": None,
            "lag1_response_vs_same_life": None,
            "lag1_response_vs_pattern_closeness": None,
        }
        for arm in (AUTONOMOUS_ARM, YOKED_ARM)
    )
    paired = paired_arm_difference_rows(
        benefits,
        lagged,
        (*autonomous, *yoked),
    )[0]
    assert paired["paired_valid_session_count"] == 4
    assert paired["late_delta_rmssd_advantage_ms"] == 6.0


def test_deterministic_bootstrap_and_session_block_bootstrap() -> None:
    first = bootstrap_interval([0.5, 1.0, 1.5, 2.0], seed_parts=("fixture",))
    second = bootstrap_interval([0.5, 1.0, 1.5, 2.0], seed_parts=("fixture",))
    assert first == second
    assert bootstrap_median_interval(
        [0.5, 1.0, 8.0, 9.0],
        seed_parts=("fixture",),
    ) == bootstrap_median_interval(
        [0.5, 1.0, 8.0, 9.0],
        seed_parts=("fixture",),
    )
    interval = session_block_bootstrap_interval(
        tuple(session(index, float(index + 1)) for index in range(9)),
        tuple(session(index, float(index)) for index in range(9)),
        seed_parts=("fixture",),
    )
    assert interval == pytest.approx((1.0, 1.0))


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    (
        ({"late_advantage_ms": 1.0, "selection_enrichment_advantage": 1.0, "slope_advantage": 1.0, "permutation_p_like": 0.1, "valid_session_count": 8}, "clear_positive_adaptation"),
        ({"late_advantage_ms": 0.3, "selection_enrichment_advantage": 1.0, "slope_advantage": 1.0, "permutation_p_like": 0.8, "valid_session_count": 8}, "partial_adaptation_signal"),
        ({"late_advantage_ms": 0.0, "selection_enrichment_advantage": 0.0, "slope_advantage": 0.0, "permutation_p_like": 0.8, "valid_session_count": 8}, "no_clear_effect"),
        ({"late_advantage_ms": -1.0, "selection_enrichment_advantage": -1.0, "slope_advantage": -1.0, "permutation_p_like": 0.8, "valid_session_count": 8}, "negative_or_unstable"),
        ({"late_advantage_ms": 1.0, "selection_enrichment_advantage": 1.0, "slope_advantage": 1.0, "permutation_p_like": 0.1, "valid_session_count": 3}, "insufficient_data"),
    ),
)
def test_participant_classification_has_all_outcomes(kwargs: dict[str, object], expected: str) -> None:
    assert classify_participant_effect(**kwargs) == expected  # type: ignore[arg-type]


def test_circular_mean_and_low_concentration() -> None:
    mean, concentration = circular_mean_and_concentration([359.0, 1.0, 0.0])
    assert mean is not None
    assert circular_hue_distance(mean, 0.0) == pytest.approx(0.0, abs=1e-12)
    assert concentration > 0.99
    mean, concentration = circular_mean_and_concentration([0.0, 180.0])
    assert mean is None
    assert concentration == 0.0


@pytest.mark.parametrize("hue", (0.0, 60.0, 120.0, 180.0, 240.0, 300.0, 360.0))
def test_hue_color_is_css_hex(hue: float) -> None:
    color = hue_color(hue)
    assert len(color) == 7 and color.startswith("#")
    int(color[1:], 16)


def test_participant_chart_encodes_required_semantics() -> None:
    life_ids = ("life-red", "life-green", "life-blue")
    bundles = tuple(
        bundle(
            0,
            1.0,
            arm=arm,
            bundle_index=index,
            life_id=life_ids[index],
        )
        for arm in ARM_IDS
        for index in range(3)
    )
    sessions = tuple(
        session(0, 1.0, arm=arm, life_id=life_ids[index])
        for index, arm in enumerate(ARM_IDS)
    )
    svg = participant_trajectory_svg(
        "fixture__p001",
        "fixture-condition",
        bundles,
        sessions,
    )
    assert "session index" in svg and "blink BPM" in svg
    assert "<circle" in svg and "<polygon" in svg
    assert "actual Hue" in svg
    assert all(label in svg for label in ("autonomous", "yoked replay", "pure random"))


def test_record_json_projection_is_finite() -> None:
    encoded = json.dumps(bundle(0, 1.0).to_dict(), allow_nan=False)
    assert math.isfinite(json.loads(encoded)["delta_rmssd_ms"])


def test_rejected_bundle_keeps_diagnostic_rmssd_but_not_analysis_delta() -> None:
    values = bundle(0, 1.0).to_dict()
    values.update(
        {
            "evaluation_quality": "rejected",
            "valid_for_analysis": False,
            "delta_rmssd_ms": None,
            "bundle_n": None,
            "w": None,
        }
    )
    rejected = BundleOutcome.from_dict(values)
    assert rejected.bundle_rmssd_ms == 21.0
    assert rejected.delta_rmssd_ms is None
    assert rejected.valid_for_analysis is False
