"""Freshness and production agreement for independent Stage 7 vectors."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.domain.event_priorities import HEARTBEAT_EVENT_PRIORITY
from symbiotic_sim_v2.runtime.closed_loop import (
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.light_simulation import create_light_feedback_simulation
from symbiotic_sim_v2.virtual_user import physiology as base_physiology
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.config import (
    HEARTBEAT_CAUSALITY_POLICY_VERSION,
    LIGHT_RESPONSE_INPUT_SCHEMA_VERSION,
    LIGHT_RESPONSE_MODEL_VERSION,
    LIGHT_RESPONSE_SEGMENT_SCHEMA_VERSION,
    PHYSICAL_PROJECTION_VERSION,
    PHYSIOLOGY_COUPLING_VERSION,
    PREFERENCE_MODEL_VERSION,
    RESPONSE_DYNAMICS_VERSION,
    RESPONSIVE_HEARTBEAT_SCHEMA_VERSION,
    LightResponseConfig,
)
from symbiotic_sim_v2.virtual_user.light_response.dynamics import (
    first_order_response_at,
)
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
)
from symbiotic_sim_v2.virtual_user.light_response.physiology import (
    calculate_light_responsive_next_rri,
    effective_physiology,
)
from symbiotic_sim_v2.virtual_user.light_response.preference import (
    circular_hue_distance,
    evaluate_light_preference,
    response_target_for,
)
from symbiotic_sim_v2.virtual_user.light_response.presets import (
    light_insensitive_control,
    off_center_green,
)


def project_root() -> Path:
    return Path(__file__).parents[2]


def vectors() -> dict[str, object]:
    path = project_root() / "docs" / "conformance" / "stage-07-reference-vectors.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_stage7_reference_file_is_fresh_and_generator_is_production_independent() -> None:
    generator = project_root() / "tools" / "generate_stage_07_reference_vectors.py"
    completed = subprocess.run(
        [sys.executable, str(generator), "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout == completed.stderr == ""
    assert "symbiotic_sim_v2" not in generator.read_text(encoding="utf-8")


def test_stage7_versions_match_fixed_reference_vectors() -> None:
    assumptions = vectors()["simulation_assumptions"]
    assert __version__ == assumptions["project_version"] == "0.8.0"
    assert assumptions == {
        "diagnostic_sampling_policy_version": "fixed_virtual_grid_100ms_v0_1",
        "heartbeat_causality_policy_version": HEARTBEAT_CAUSALITY_POLICY_VERSION,
        "input_schema_version": LIGHT_RESPONSE_INPUT_SCHEMA_VERSION,
        "light_responsive_user_model_version": LIGHT_RESPONSE_MODEL_VERSION,
        "physical_projection_version": PHYSICAL_PROJECTION_VERSION,
        "physiology_coupling_version": PHYSIOLOGY_COUPLING_VERSION,
        "preference_model_version": PREFERENCE_MODEL_VERSION,
        "project_version": "0.8.0",
        "response_dynamics_version": RESPONSE_DYNAMICS_VERSION,
        "response_segment_schema_version": LIGHT_RESPONSE_SEGMENT_SCHEMA_VERSION,
        "responsive_heartbeat_schema_version": RESPONSIVE_HEARTBEAT_SCHEMA_VERSION,
    }


def test_independent_preference_and_response_vectors_match_production() -> None:
    data = vectors()
    preference_vectors = data["preference_vectors"]
    for vector in preference_vectors["circular_hue_distance"]:
        assert circular_hue_distance(
            vector["first_degree"], vector["second_degree"]
        ) == pytest.approx(vector["distance"])

    aligned = preference_vectors["aligned"]
    stimulus = PhysicalLightStimulus(
        effective_time_us=60_551_540,
        active=True,
        render_hue_degree=aligned["render_hue_degree"],
        saturation=1.0,
        value_center=0.425,
        value_amplitude=0.075,
        value_min=0.35,
        value_max=0.5,
        blink_bpm=aligned["blink_bpm"],
        waveform="sine",
        phase_cycles_at_start=0.0,
    )
    config = LightResponseConfig()
    match = evaluate_light_preference(stimulus, config)
    assert match.hue_match == aligned["hue_match"]
    assert match.bpm_match == aligned["bpm_match"]
    assert match.preference_match == aligned["preference_match"]
    assert response_target_for(stimulus, match, config) == aligned["response_target"]

    off_center = preference_vectors["off_center"]
    off_center_match = evaluate_light_preference(stimulus, off_center_green())
    assert off_center_match.hue_match == pytest.approx(off_center["hue_match"])
    assert off_center_match.bpm_match == pytest.approx(off_center["bpm_match"])
    assert off_center_match.preference_match == pytest.approx(
        off_center["preference_match"]
    )

    inactive = PhysicalLightStimulus(
        effective_time_us=0,
        active=False,
        render_hue_degree=None,
        saturation=0.0,
        value_center=0.0,
        value_amplitude=0.0,
        value_min=0.0,
        value_max=0.0,
        blink_bpm=None,
        waveform="off",
        phase_cycles_at_start=None,
    )
    inactive_match = evaluate_light_preference(inactive, config)
    assert inactive_match.hue_match is None
    assert inactive_match.bpm_match is None
    assert inactive_match.preference_match == 0.0
    assert response_target_for(inactive, inactive_match, config) == 0.0

    response_vectors = data["response_vectors"]
    assert first_order_response_at(
        8_000_000,
        start_time_us=0,
        response_at_start=0.0,
        target=1.0,
        time_constant_seconds=8.0,
    ) == pytest.approx(response_vectors["onset_after_one_tau"])

    onset = response_vectors["onset_after_one_tau"]
    recovery = first_order_response_at(
        20_000_000,
        start_time_us=8_000_000,
        response_at_start=onset,
        target=0.0,
        time_constant_seconds=12.0,
    )
    assert recovery == pytest.approx(response_vectors["recovery_after_one_tau"])
    continuity = first_order_response_at(
        8_000_000,
        start_time_us=8_000_000,
        response_at_start=onset,
        target=0.0,
        time_constant_seconds=12.0,
    )
    assert continuity == pytest.approx(
        response_vectors["continuity_at_target_change"]["response_before"]
    )
    assert continuity == pytest.approx(
        response_vectors["continuity_at_target_change"]["response_after_same_time"]
    )


def test_independent_physiology_projection_control_and_ordering_vectors(
    monkeypatch,
) -> None:
    data = vectors()
    physiology = data["physiology_vectors"]
    virtual_config = VirtualUserConfig(duration_seconds=240)
    response_config = LightResponseConfig()
    assert effective_physiology(virtual_config, response_config, 0.0) == pytest.approx(
        (
            physiology["base_mean_rri_ms"],
            physiology["response_zero"]["effective_mean_rri_ms"],
            0.0,
            physiology["base_respiratory_amplitude_ms"],
            physiology["response_zero"]["effective_respiratory_amplitude_ms"],
            0.0,
        )
    )
    response_one = effective_physiology(virtual_config, response_config, 1.0)
    assert response_one[1] == pytest.approx(
        physiology["response_one"]["effective_mean_rri_ms"]
    )
    assert response_one[4] == pytest.approx(
        physiology["response_one"]["effective_respiratory_amplitude_ms"]
    )

    manual = physiology["responsive_rri_manual_fixture"]
    components = manual["components"]
    persistence = virtual_config.correlated_variability_persistence

    def fixed_standard_normal(_root_seed: int, stream_name: str, _index: int) -> float:
        if stream_name == base_physiology.CORRELATED_STREAM:
            target_state = (
                components["correlated_component_ms"]
                / virtual_config.correlated_variability_sd_ms
            )
            return target_state / math.sqrt(1.0 - persistence**2)
        if stream_name == base_physiology.JITTER_STREAM:
            return (
                components["beat_jitter_component_ms"]
                / virtual_config.beat_jitter_sd_ms
            )
        raise AssertionError(f"unexpected random stream: {stream_name}")

    monkeypatch.setattr(base_physiology, "standard_normal", fixed_standard_normal)
    monkeypatch.setattr(
        base_physiology,
        "respiratory_component_with_amplitude_ms",
        lambda *_args: components["respiratory_component_ms"],
    )
    monkeypatch.setattr(
        base_physiology,
        "slow_wave_component_ms",
        lambda *_args: components["slow_wave_component_ms"],
    )
    responsive = calculate_light_responsive_next_rri(
        virtual_config,
        response_config,
        current_heartbeat_time_us=0,
        beat_index=0,
        previous_correlated_state=0.0,
        response_level=manual["response_level"],
    ).computation
    assert responsive.mean_rri_ms == pytest.approx(components["mean_rri_ms"])
    assert responsive.respiratory_component_ms == pytest.approx(
        components["respiratory_component_ms"]
    )
    assert responsive.slow_wave_component_ms == pytest.approx(
        components["slow_wave_component_ms"]
    )
    assert responsive.correlated_component_ms == pytest.approx(
        components["correlated_component_ms"]
    )
    assert responsive.beat_jitter_component_ms == pytest.approx(
        components["beat_jitter_component_ms"]
    )
    assert responsive.unclamped_rri_ms == pytest.approx(manual["unclamped_rri_ms"])
    assert responsive.final_rri_ms == pytest.approx(manual["final_rri_ms"])
    assert responsive.rri_us == manual["rri_us_half_up"]

    projection_fields = set(PhysicalLightStimulus.__dataclass_fields__)
    boundary = data["projection_boundary"]
    assert projection_fields == set(boundary["allowed_fields"])
    assert projection_fields.isdisjoint(boundary["excluded_provenance_fields"])
    assert boundary["provenance_used_by_physiology"] is False

    causality = data["causality_vectors"]
    assert causality["heartbeat_priority"] == HEARTBEAT_EVENT_PRIORITY
    assert causality["light_stimulus_state_priority"] == 67
    assert causality["same_time_order"] == ["heartbeat", "light_stimulus_state"]
    assert causality["pending_heartbeat_rescheduled"] is False

    control = light_insensitive_control()
    assert control.maximum_respiratory_amplitude_gain_ms == 0.0
    assert control.maximum_mean_rri_increase_ms == 0.0
    off_center = off_center_green()
    assert (off_center.preferred_hue_degree, off_center.preferred_blink_bpm) == (
        129.0,
        125.0,
    )


def test_independent_standard_and_control_scenario_vectors_match_production() -> None:
    data = vectors()
    standard = data["standard_scenario"]
    response_vectors = data["response_vectors"]
    physiology = data["physiology_vectors"]

    simulation = create_light_responsive_closed_loop_simulation()
    simulation.engine.run_until_end()
    component = simulation.light_responsive_virtual_user_component
    first_active = next(record for record in component.light_receipt_records() if record.active)
    assert standard["preset"] == "aligned_green_center"
    assert first_active.event_time_us == standard["first_active_effective_time_us"]
    assert first_active.physical_stimulus.render_hue_degree == (
        standard["first_active_hue_degree"]
    )
    assert first_active.physical_stimulus.blink_bpm == (
        standard["first_active_blink_bpm"]
    )
    assert first_active.preference_match == standard["first_active_preference_match"]
    assert len(component.light_receipt_records()) == standard["light_stimulus_input_count"]
    assert len(component.response_samples()) == standard["response_sample_count"]
    assert component.response_samples()[1].time_us == standard["response_sample_interval_us"]
    assert simulation.engine.clock.current_time_us == standard["simulation_end_time_us"]
    assert component.light_response_config.preference_stationary is (
        standard["preference_stationary"]
    )
    assert len(component.response_segments()) == 2
    assert response_vectors["same_target_continues_without_new_segment"] is True

    checkpoints = response_vectors["checkpoints"]
    for key, time_us in (
        ("response_at_90s", 90_000_000),
        ("response_at_120s", 120_000_000),
        ("response_at_180s", 180_000_000),
        ("response_at_240s_before_closing", 240_000_000),
    ):
        assert component.response_at(time_us) == pytest.approx(checkpoints[key])
    response_at_90 = physiology["response_at_90s"]
    assert component.response_at(90_000_000) == pytest.approx(
        response_at_90["response_level"]
    )
    effective_at_90 = effective_physiology(
        simulation.virtual_user_config,
        simulation.light_response_config,
        component.response_at(90_000_000),
    )
    assert effective_at_90[1] == pytest.approx(response_at_90["effective_mean_rri_ms"])
    assert effective_at_90[4] == pytest.approx(
        response_at_90["effective_respiratory_amplitude_ms"]
    )

    control_vectors = data["control"]
    control = create_light_responsive_closed_loop_simulation(
        light_response_config=light_insensitive_control()
    )
    stage6 = create_light_feedback_simulation()
    control.engine.run_until_end()
    stage6.engine.run_until_end()
    assert control.component.heartbeat_digest() == control_vectors[
        "stage_6_heartbeat_digest"
    ]
    assert control.engine.deterministic_digest() == stage6.engine.deterministic_digest()
    assert control_vectors["formal_event_stream_equals_stage_6"] is True
    assert bool(control.component.light_receipt_records()) is control_vectors[
        "light_receipts_recorded"
    ]
