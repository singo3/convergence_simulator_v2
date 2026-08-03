"""Command entry point for Stage 1-7.1 compatibility and the Stage 5C app."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.devices.polar_h10.config import (
    POLAR_H10_MODEL_VERSION,
    RRI_EVENT_SCHEMA_VERSION,
    PolarH10Config,
)
from symbiotic_sim_v2.devices.polar_h10.diagnostics import (
    H10_DIAGNOSTIC_NOTICE,
    compare_rri_measurements,
    export_rri_measurement_diagnostics_csv,
)
from symbiotic_sim_v2.devices.polar_h10.scenario import create_polar_h10_simulation
from symbiotic_sim_v2.devices.virtual_light.config import (
    LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION,
    LIGHT_STIMULUS_STATE_SCHEMA_VERSION,
    VIRTUAL_LIGHT_DEVICE_MODEL_VERSION,
    WAVEFORM_SAMPLE_POLICY_VERSION,
)
from symbiotic_sim_v2.devices.virtual_light.diagnostics import (
    export_light_diagnostics,
)
from symbiotic_sim_v2.digital_life.config import (
    ALGORITHM_VERSION,
    DIGITAL_LIFE_CONFIG_SCHEMA_VERSION,
    DIGITAL_LIFE_MODEL_VERSION,
    STATE_SCHEMA_VERSION,
    digital_life_config_for_role,
)
from symbiotic_sim_v2.digital_life.diagnostics import (
    EVALUATION_UPDATE_CSV_FILENAME,
    FIRST_ROUND_CSV_FILENAME,
    export_evaluation_updates_csv,
    export_first_round_diagnostics_csv,
)
from symbiotic_sim_v2.digital_life.relation_memory.config import (
    ADAPTIVE_DIGITAL_LIFE_MODEL_VERSION,
    ADAPTIVE_DIGITAL_LIFE_SIGNAL_RECORD_SCHEMA_VERSION,
    BUNDLE1_REJECT_POLICY_VERSION,
    RELATION_MEMORY_INTRINSIC_PROFILE_SCHEMA_VERSION,
    RELATION_MEMORY_PERSISTENT_STATE_RECORD_SCHEMA_VERSION,
    RELATION_MEMORY_SESSION_STATE_RECORD_SCHEMA_VERSION,
    RELATION_MEMORY_TRANSITION_RECORD_SCHEMA_VERSION,
    RELATION_UPDATE_EFFECTIVE_POLICY_VERSION,
)
from symbiotic_sim_v2.digital_life.relation_memory.diagnostics import (
    adaptive_signal_digest,
    export_relation_memory_diagnostics,
    final_persistent_state_digest,
    intrinsic_profile_digest,
    relation_memory_transition_digest,
    session_summary_digest,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    export_relation_memory_state_file,
    load_relation_memory_state_file,
    relation_memory_state_map_to_dict,
)
from symbiotic_sim_v2.digital_life.scenario import create_single_digital_life_simulation
from symbiotic_sim_v2.digital_life.second_round_diagnostics import (
    SECOND_ROUND_CSV_FILENAME,
    export_second_round_diagnostics_csv,
)
from symbiotic_sim_v2.digital_life.second_round_records import (
    DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION,
)
from symbiotic_sim_v2.domain.event_types import GARDEN_PHASE_CHANGED_EVENT_TYPE
from symbiotic_sim_v2.garden.input_layer.config import (
    BASELINE_INVALID_POLICY,
    GARDEN_EVALUATION_SCHEMA_VERSION,
    GARDEN_INPUT_MODEL_VERSION,
    GARDEN_INPUT_SIGNAL_SCHEMA_VERSION,
    GARDEN_MANIFEST_VERSION,
    GARDEN_PHASE_SCHEMA_VERSION,
    RRI_WINDOW_MEMBERSHIP_POLICY,
    GardenInputConfig,
)
from symbiotic_sim_v2.garden.input_layer.diagnostics import (
    export_garden_input_diagnostics,
)
from symbiotic_sim_v2.garden.input_layer.scenario import create_garden_input_simulation
from symbiotic_sim_v2.garden.light_mapper.config import (
    B_TO_I_MAPPING_VERSION,
    COMMAND_HOLD_POLICY_VERSION,
    CONTINUOUS_PHASE_POLICY_VERSION,
    GARDEN_LIGHT_MAPPER_MODEL_VERSION,
    INACTIVE_OUTPUT_POLICY_VERSION,
    LIGHT_COMMAND_SCHEMA_VERSION,
)
from symbiotic_sim_v2.garden.output_layer.config import (
    DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
    GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION,
    GARDEN_OUTPUT_MODEL_VERSION,
    GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION,
    GARDEN_QUALIFIED_B_SCHEMA_VERSION,
    QUALIFIED_B_EMISSION_POLICY_VERSION,
)
from symbiotic_sim_v2.garden.output_layer.diagnostics import (
    export_garden_output_diagnostics,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.closed_loop import (
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    create_light_feedback_simulation,
)
from symbiotic_sim_v2.runtime.multi_life.config import (
    TAU_TOUCH_DELIVERY_POLICY_VERSION,
    THREE_DIGITAL_LIFE_RUNTIME_MODEL_VERSION,
)
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    create_three_digital_life_competition_simulation,
)
from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine
from symbiotic_sim_v2.virtual_user.config import VIRTUAL_USER_MODEL_VERSION, VirtualUserConfig
from symbiotic_sim_v2.virtual_user.diagnostics import (
    export_heartbeat_diagnostics_csv,
    full_run_rmssd_ms,
    rolling_rmssd_ms,
)
from symbiotic_sim_v2.virtual_user.light_response.config import (
    HEARTBEAT_CAUSALITY_POLICY_VERSION,
    LIGHT_RESPONSE_DYNAMICS_EPOCH_SCHEMA_VERSION,
    LIGHT_RESPONSE_MODEL_VERSION,
    LIGHT_RESPONSE_SEGMENT_SCHEMA_VERSION,
    PHYSICAL_LIGHT_PARAMETER_SIGNATURE_VERSION,
    PHYSICAL_PROJECTION_VERSION,
    PHYSICAL_STIMULUS_CHANGE_POLICY_VERSION,
    PHYSIOLOGY_COUPLING_VERSION,
    PREFERENCE_MODEL_VERSION,
    RESPONSE_DYNAMICS_VERSION,
    SEGMENT_SPLIT_POLICY_VERSION,
)
from symbiotic_sim_v2.virtual_user.light_response.diagnostics import (
    export_light_response_diagnostics,
)
from symbiotic_sim_v2.virtual_user.light_response.physiology import (
    effective_physiology,
)
from symbiotic_sim_v2.virtual_user.light_response.presets import (
    DEFAULT_LIGHT_RESPONSE_PRESET,
    light_response_config_for_preset,
    light_response_preset_names,
)
from symbiotic_sim_v2.virtual_user.scenario import create_virtual_user_simulation

DOCUMENT_VERSION = "v2.0"
PROFILE_VERSION = "symbiotic_signal_loop_reference_v1_0"
STAGE_3_HEADLESS_PROJECT_VERSION = "0.3.0"
STAGE_4_HEADLESS_PROJECT_VERSION = "0.4.0"
STAGE_5A_HEADLESS_PROJECT_VERSION = "0.5.0"
STAGE_5B1_HEADLESS_PROJECT_VERSION = "0.6.1"
STAGE_6_HEADLESS_PROJECT_VERSION = "0.7.0"
STAGE_7_1_HEADLESS_PROJECT_VERSION = "0.8.1"
DEFAULT_RELATION_MEMORY_PRESET = "off_center_green"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Symbiotic simulator Stage 5C")
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument(
        "--headless-demo",
        action="store_true",
        help="run the backward-compatible Stage 1 time diagnostic",
    )
    headless_group.add_argument(
        "--headless-time-demo",
        action="store_true",
        help="alias for the Stage 1 --headless-demo command",
    )
    headless_group.add_argument(
        "--headless-virtual-user-demo",
        action="store_true",
        help="run the 180-second Stage 2 baseline virtual user",
    )
    headless_group.add_argument(
        "--headless-h10-demo",
        action="store_true",
        help="run the 180-second Stage 3 ideal Polar H10 simulation",
    )
    headless_group.add_argument(
        "--headless-garden-input-demo",
        action="store_true",
        help="run the 240-second Stage 4 Garden input-layer simulation",
    )
    headless_group.add_argument(
        "--headless-single-life-demo",
        action="store_true",
        help="run the 240-second Stage 5A single-Digital-Life first round",
    )
    headless_group.add_argument(
        "--headless-three-life-competition-demo",
        action="store_true",
        help=(
            "run the 240-second Stage 5B.1 three-life competition with corrected "
            "Garden output timing"
        ),
    )
    headless_group.add_argument(
        "--headless-light-device-demo",
        action="store_true",
        help="run the 240-second Stage 6 Garden-to-virtual-light simulation",
    )
    headless_group.add_argument(
        "--headless-light-responsive-user-demo",
        action="store_true",
        help="run the 240-second Stage 7 light-responsive closed loop",
    )
    headless_group.add_argument(
        "--headless-relation-memory-demo",
        action="store_true",
        help="run the Stage 5C confirmed relation-memory closed loop",
    )
    parser.add_argument(
        "--life-role",
        choices=("red", "green", "blue"),
        default=None,
        help="select the backward-compatible Stage 5A GUI/CLI role preset",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="exercise GUI controls and close automatically",
    )
    parser.add_argument(
        "--auto-close-ms",
        type=int,
        default=6500,
        help="GUI smoke-test auto-close delay in milliseconds",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="save a GUI screenshot after smoke actions (or shortly after launch)",
    )
    parser.add_argument(
        "--screenshot-target",
        choices=(
            "window",
            "digital-life-graphs",
            "three-life-overview",
            "touch-holder-second-round",
            "garden-output-qualified-b",
            "light-output-overview",
            "continuous-phase-waveform",
            "light-command-segments",
            "stage-07-light-response-overview",
            "stage-07-preference-response-physiology",
            "stage-07-heartbeat-rmssd-closed-loop",
            "stage-05c-relation-memory-overview",
            "stage-05c-k-ft-search-and-thresholds",
            "stage-05c-transition-and-persistent-state",
        ),
        default="window",
        help="capture the selected Stage 5A/5B/5C/6/7 diagnostic view",
    )
    parser.add_argument(
        "--export-virtual-user-csv",
        type=Path,
        help="write Stage 2 true-value diagnostics CSV on a headless virtual-user run",
    )
    parser.add_argument(
        "--export-h10-csv",
        type=Path,
        help="write Stage 3 raw-RRI and true-value comparison diagnostics CSV",
    )
    parser.add_argument(
        "--export-garden-input-csv",
        type=Path,
        help="write the three Stage 4 Garden diagnostic CSV files to a directory",
    )
    parser.add_argument(
        "--export-single-life-csv",
        type=Path,
        help="write the two Stage 5A Digital Life diagnostic CSV files to a directory",
    )
    parser.add_argument(
        "--export-three-life-competition-csv",
        type=Path,
        help="write the four Stage 5B competition diagnostic CSV files to a directory",
    )
    parser.add_argument(
        "--export-light-device-csv",
        type=Path,
        help="write the four Stage 6 light diagnostic CSV files to a directory",
    )
    parser.add_argument(
        "--light-response-preset",
        choices=light_response_preset_names(),
        default=None,
        help=(
            "select the fixed light-response characteristic (Stage 7 default: "
            f"{DEFAULT_LIGHT_RESPONSE_PRESET}; Stage 5C default: "
            f"{DEFAULT_RELATION_MEMORY_PRESET})"
        ),
    )
    parser.add_argument(
        "--export-light-responsive-user-csv",
        type=Path,
        help="write the five Stage 7.1 response diagnostic CSV files to a directory",
    )
    parser.add_argument(
        "--initial-relation-state-json",
        type=Path,
        help="load the exact three-life Stage 5C persistent-state JSON document",
    )
    parser.add_argument(
        "--export-final-relation-state-json",
        type=Path,
        help="write the normally finalized Stage 5C persistent states as JSON",
    )
    parser.add_argument(
        "--export-relation-memory-csv",
        type=Path,
        help="write the five Stage 5C relation-memory CSV files to a directory",
    )
    return parser


def run_headless_demo() -> int:
    """Run the diagnostic scenario and emit one self-contained JSON document."""

    engine = create_demo_engine()
    engine.run_until_end()
    events = [
        {"execution_order": index, **event.to_dict()}
        for index, event in enumerate(engine.executed_events(), start=1)
    ]
    result = {
        "scenario": "stage_01_time_foundation_diagnostic",
        "events": events,
        "final_virtual_time_us": engine.clock.current_time_us,
        "final_virtual_time_seconds": engine.clock.current_time_us / 1_000_000,
        "executed_event_count": len(events),
        "deterministic_digest": engine.deterministic_digest(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_headless_virtual_user_demo(export_csv: Path | None = None) -> int:
    """Run the standard Stage 2 user and emit deterministic diagnostic JSON."""

    config = VirtualUserConfig()
    simulation = create_virtual_user_simulation(config)
    simulation.engine.run_until_end()
    records = simulation.component.heartbeat_records()
    rri_values = tuple(record.true_rri_ms for record in records if record.true_rri_ms is not None)
    mean_rri = statistics.fmean(rri_values)
    if export_csv is not None:
        export_heartbeat_diagnostics_csv(export_csv, records)
    result = {
        "virtual_user_model_version": VIRTUAL_USER_MODEL_VERSION,
        "config": config.to_dict(),
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "heartbeat_count": len(records),
        "first_heartbeat_time_us": records[0].heartbeat_time_us,
        "last_heartbeat_time_us": records[-1].heartbeat_time_us,
        "first_true_rri_ms": rri_values[0],
        "last_true_rri_ms": rri_values[-1],
        "mean_true_rri_ms": mean_rri,
        "mean_heart_rate_bpm": 60_000.0 / mean_rri,
        "minimum_true_rri_ms": min(rri_values),
        "maximum_true_rri_ms": max(rri_values),
        "full_run_rmssd_ms": full_run_rmssd_ms(records),
        "final_rolling_rmssd_ms": rolling_rmssd_ms(
            records,
            simulation.engine.clock.current_time_us,
        ),
        "clamped_beat_count": simulation.component.snapshot().clamped_beat_count,
        "heartbeat_digest": simulation.component.heartbeat_digest(),
        "diagnostic_digest": simulation.component.diagnostic_digest(),
        "full_event_digest": simulation.engine.deterministic_digest(),
    }
    if export_csv is not None:
        result["diagnostic_csv"] = str(export_csv)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_headless_h10_demo(export_csv: Path | None = None) -> int:
    """Run the standard ideal H10 and emit raw-signal diagnostics as JSON."""

    virtual_user_config = VirtualUserConfig()
    polar_h10_config = PolarH10Config(expected_user_id=virtual_user_config.user_id)
    simulation = create_polar_h10_simulation(virtual_user_config, polar_h10_config)
    simulation.engine.run_until_end()
    heartbeat_records = simulation.virtual_user_component.heartbeat_records()
    measurement_records = simulation.polar_h10_component.measurement_records()
    comparisons = compare_rri_measurements(measurement_records, heartbeat_records)
    measured_rri_ms = tuple(record.rri_ms for record in measurement_records)
    written_csv: Path | None = None
    if export_csv is not None:
        written_csv = export_rri_measurement_diagnostics_csv(
            export_csv,
            measurement_records,
            heartbeat_records,
        )
    result = {
        "project_version": STAGE_3_HEADLESS_PROJECT_VERSION,
        "virtual_user_model_version": VIRTUAL_USER_MODEL_VERSION,
        "polar_h10_model_version": POLAR_H10_MODEL_VERSION,
        "rri_event_schema_version": RRI_EVENT_SCHEMA_VERSION,
        "virtual_user_config": virtual_user_config.to_dict(),
        "polar_h10_config": polar_h10_config.to_dict(),
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "heartbeat_count": len(heartbeat_records),
        "observed_heartbeat_count": (
            simulation.polar_h10_component.snapshot().observed_heartbeat_count
        ),
        "rri_measurement_count": len(measurement_records),
        "first_rri_event_time_us": measurement_records[0].event_time_us,
        "last_rri_event_time_us": measurement_records[-1].event_time_us,
        "first_measured_rri_us": measurement_records[0].rri_us,
        "last_measured_rri_us": measurement_records[-1].rri_us,
        "mean_measured_rri_ms": statistics.fmean(measured_rri_ms),
        "minimum_measured_rri_ms": min(measured_rri_ms),
        "maximum_measured_rri_ms": max(measured_rri_ms),
        "matched_measurement_count": sum(record.match for record in comparisons),
        "mismatched_measurement_count": sum(not record.match for record in comparisons),
        "maximum_absolute_error_us": max(record.absolute_error_us for record in comparisons),
        "heartbeat_digest": simulation.virtual_user_component.heartbeat_digest(),
        "rri_measurement_digest": simulation.polar_h10_component.measurement_digest(),
        "full_event_digest": simulation.engine.deterministic_digest(),
        "diagnostic_notice": H10_DIAGNOSTIC_NOTICE,
    }
    if written_csv is not None:
        result["diagnostic_csv"] = str(written_csv)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_headless_garden_input_demo(export_csv: Path | None = None) -> int:
    """Run the standard Stage 4 input layer and emit deterministic N/S JSON."""

    garden_config = GardenInputConfig()
    simulation = create_garden_input_simulation(garden_input_config=garden_config)
    simulation.engine.run_until_end()
    garden = simulation.garden_input_component
    snapshot = garden.snapshot()
    evaluations = [
        {
            "evaluation_id": record.evaluation_id,
            "kind": record.evaluation_kind,
            "bundle_index": record.bundle_index,
            "total_rri_count": record.total_rri_count,
            "artifact_rri_count": record.artifact_rri_count,
            "valid_rri_count": record.valid_rri_count,
            "artifact_rate": record.artifact_rate,
            "rmssd_ms": record.rmssd_ms,
            "n": record.n,
            "quality": record.quality,
            "is_valid": record.is_valid,
            "reject_reasons": list(record.reject_reasons),
        }
        for record in garden.evaluation_records()
    ]
    result = {
        "project_version": STAGE_4_HEADLESS_PROJECT_VERSION,
        "document_version": DOCUMENT_VERSION,
        "profile_version": PROFILE_VERSION,
        "virtual_user_model_version": VIRTUAL_USER_MODEL_VERSION,
        "polar_h10_model_version": POLAR_H10_MODEL_VERSION,
        "rri_event_schema_version": RRI_EVENT_SCHEMA_VERSION,
        "garden_manifest_version": GARDEN_MANIFEST_VERSION,
        "garden_input_model_version": GARDEN_INPUT_MODEL_VERSION,
        "garden_input_signal_schema_version": GARDEN_INPUT_SIGNAL_SCHEMA_VERSION,
        "garden_evaluation_schema_version": GARDEN_EVALUATION_SCHEMA_VERSION,
        "garden_phase_schema_version": GARDEN_PHASE_SCHEMA_VERSION,
        "rri_window_membership_policy": RRI_WINDOW_MEMBERSHIP_POLICY,
        "baseline_invalid_policy": BASELINE_INVALID_POLICY,
        "virtual_user_config": simulation.virtual_user_config.to_dict(),
        "polar_h10_config": simulation.polar_h10_config.to_dict(),
        "garden_input_config": garden_config.to_dict(),
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "heartbeat_count": len(simulation.virtual_user_component.heartbeat_records()),
        "rri_measurement_count": len(simulation.polar_h10_component.measurement_records()),
        "garden_signal_count": len(garden.signal_records()),
        "phase_event_count": sum(
            event.event_type == GARDEN_PHASE_CHANGED_EVENT_TYPE
            for event in simulation.engine.executed_events()
        ),
        "evaluation_count": len(garden.evaluation_records()),
        "received_rri_count": snapshot.received_rri_count,
        "valid_rri_count": snapshot.valid_rri_count,
        "artifact_rri_count": snapshot.artifact_rri_count,
        "baseline_available": snapshot.baseline_available,
        "N_baseline_session": snapshot.n_baseline_session,
        "N_current": snapshot.n_current,
        "valid_evaluation_revision": snapshot.valid_evaluation_revision,
        "evaluations": evaluations,
        "artifact_digest": garden.artifact_digest(),
        "evaluation_digest": garden.evaluation_digest(),
        "signal_digest": garden.signal_digest(),
        "full_event_digest": simulation.engine.deterministic_digest(),
    }
    if export_csv is not None:
        paths = export_garden_input_diagnostics(export_csv, garden)
        result["diagnostic_csvs"] = {
            "rri_classification": str(paths.rri_classification),
            "evaluations": str(paths.evaluations),
            "signals": str(paths.signals),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_headless_single_life_demo(
    *,
    life_role: str = "green",
    export_csv: Path | None = None,
) -> int:
    """Run one Stage 5A first round and emit deterministic life diagnostics."""

    life_config = digital_life_config_for_role(life_role)
    simulation = create_single_digital_life_simulation(
        digital_life_config=life_config,
    )
    simulation.engine.run_until_end()
    life = simulation.digital_life_component
    garden = simulation.garden_input_component
    snapshot = life.snapshot()
    intrinsic = life.intrinsic_profile
    result = {
        "project_version": STAGE_5A_HEADLESS_PROJECT_VERSION,
        "document_version": life_config.document_version,
        "profile_version": life_config.profile_version,
        "algorithm_version": life_config.algorithm_version,
        "state_schema_version": life_config.state_schema_version,
        "digital_life_model_version": DIGITAL_LIFE_MODEL_VERSION,
        "digital_life_config_schema_version": DIGITAL_LIFE_CONFIG_SCHEMA_VERSION,
        "selected_life_config": life_config.to_dict(),
        "intrinsic_values": {
            "p_intrinsic": intrinsic.p_intrinsic,
            "birth_phase": intrinsic.birth_phase,
            "initial_B": intrinsic.initial_b,
        },
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "garden_signal_count": len(garden.signal_records()),
        "first_round_record_count": len(life.first_round_records()),
        "evaluation_update_count": len(life.evaluation_update_records()),
        "baseline_initialized": snapshot.baseline_initialized,
        "N_baseline_session": snapshot.n_baseline_session,
        "final_N_current": snapshot.n_current,
        "final_Nd": snapshot.nd,
        "final_W": snapshot.w,
        "final_P": snapshot.p,
        "final_E": snapshot.e,
        "final_q": snapshot.q,
        "final_V": snapshot.v,
        "final_k_anchor": snapshot.k_anchor,
        "final_k_current": snapshot.k_current,
        "final_B": snapshot.b,
        "final_tau": snapshot.tau,
        "G_status": snapshot.g_status,
        "second_round_connected": snapshot.second_round_connected,
        "touch_dispatched_count": snapshot.touch_dispatched_count,
        "new_valid_evaluation_count": snapshot.new_valid_evaluation_count,
        "first_round_digest": life.first_round_digest(),
        "evaluation_update_digest": life.evaluation_update_digest(),
        "full_event_digest": simulation.engine.deterministic_digest(),
    }
    if export_csv is not None:
        export_csv.mkdir(parents=True, exist_ok=True)
        first_round_path = export_first_round_diagnostics_csv(
            export_csv / FIRST_ROUND_CSV_FILENAME,
            life.first_round_records(),
        )
        evaluation_path = export_evaluation_updates_csv(
            export_csv / EVALUATION_UPDATE_CSV_FILENAME,
            life.evaluation_update_records(),
        )
        result["diagnostic_csvs"] = {
            "first_round": str(first_round_path),
            "evaluation_updates": str(evaluation_path),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_headless_three_life_competition_demo(
    export_csv: Path | None = None,
) -> int:
    """Run Stage 5B and emit qualification/second-round diagnostics as JSON."""

    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()
    garden = simulation.garden_output_component
    garden_snapshot = garden.snapshot()
    runtime_snapshot = simulation.runtime_coordinator.snapshot()
    touch_records = garden.touch_records()
    qualification_records = garden.qualification_records()
    qualified_b_records = garden.qualified_b_records()
    feedback_records = garden.feedback_records()
    active_qualified_b_records = tuple(record for record in qualified_b_records if record.active)
    inactive_qualified_b_records = tuple(
        record for record in qualified_b_records if not record.active
    )
    touch_by_signal_and_id = {
        (record.signal_index, record.digital_life_id): record for record in touch_records
    }
    holder_touch_delays_us = tuple(
        record.effective_time_us
        - touch_by_signal_and_id[
            (record.signal_index, record.qualification_holder_id)
        ].arrival_time_us
        for record in active_qualified_b_records
    )
    round_finalize_offset_us = simulation.garden_output_config.round_finalize_offset_us
    life_ids = tuple(sorted(simulation.digital_life_components))
    life_snapshots = {
        life_id: simulation.digital_life_components[life_id].snapshot() for life_id in life_ids
    }
    touch_count_by_life = {
        life_id: sum(record.digital_life_id == life_id for record in touch_records)
        for life_id in life_ids
    }
    assignment_signal_index = garden_snapshot.qualification_assigned_signal_index
    first_touch_order = [
        record.digital_life_id
        for record in touch_records
        if record.signal_index == assignment_signal_index
    ]
    per_life = {
        life_id: {
            "role": snapshot.role,
            "first_round_count": snapshot.first_round_count,
            "second_round_count": snapshot.second_round_count,
            "touch_count": snapshot.touch_dispatched_count,
            "final_E": snapshot.e,
            "final_q": snapshot.q,
            "final_G": snapshot.current_g,
            "final_k_anchor": snapshot.k_anchor,
            "final_k_current": snapshot.k_current,
            "q_update_count": snapshot.q_update_count,
            "k_update_count": snapshot.k_update_count,
        }
        for life_id, snapshot in life_snapshots.items()
    }
    result = {
        "project_version": STAGE_5B1_HEADLESS_PROJECT_VERSION,
        "document_version": DOCUMENT_VERSION,
        "profile_version": PROFILE_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "runtime_model_version": THREE_DIGITAL_LIFE_RUNTIME_MODEL_VERSION,
        "garden_output_model_version": GARDEN_OUTPUT_MODEL_VERSION,
        "qualification_state_schema_version": (GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION),
        "tau_delivery_policy_version": TAU_TOUCH_DELIVERY_POLICY_VERSION,
        "qualified_b_emission_policy_version": (QUALIFIED_B_EMISSION_POLICY_VERSION),
        "digital_life_touch_schema_version": DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
        "garden_qualified_b_schema_version": GARDEN_QUALIFIED_B_SCHEMA_VERSION,
        "event_schema_versions": {
            "touch": DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
            "interoceptive_feedback": (GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION),
            "qualified_b": GARDEN_QUALIFIED_B_SCHEMA_VERSION,
            "second_round_record": (DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION),
        },
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "garden_signal_count": len(simulation.garden_input_component.signal_records()),
        "touch_count": len(touch_records),
        "feedback_count": len(feedback_records),
        "qualified_b_output_count": len(qualified_b_records),
        "active_output_count": garden_snapshot.active_output_count,
        "inactive_output_count": garden_snapshot.inactive_output_count,
        "assignment_count": garden_snapshot.assignment_count,
        "release_count": garden_snapshot.release_count,
        "first_active_qualified_b_effective_time_us": (
            active_qualified_b_records[0].effective_time_us
        ),
        "last_active_qualified_b_effective_time_us": (
            active_qualified_b_records[-1].effective_time_us
        ),
        "closing_inactive_effective_time_us": (inactive_qualified_b_records[-1].effective_time_us),
        "holder_touch_to_qualified_b_delay_us_max": max(holder_touch_delays_us),
        "active_qualified_b_at_holder_touch_count": sum(
            delay_us == 0 for delay_us in holder_touch_delays_us
        ),
        "active_qualified_b_at_round_finalize_count": sum(
            record.effective_time_us == record.signal_time_us + round_finalize_offset_us
            for record in active_qualified_b_records
        ),
        "qualification_holder_id_during_session": (garden_snapshot.last_assigned_holder_id),
        "final_qualification_holder_id": (garden_snapshot.qualification_holder_id),
        "holder_assignment_signal_index": assignment_signal_index,
        "holder_assignment_time_us": (garden_snapshot.qualification_assignment_time_us),
        "touch_count_by_life": touch_count_by_life,
        "first_touch_order": first_touch_order,
        "per_life": per_life,
        "per_life_first_round_count": {
            life_id: snapshot.first_round_count for life_id, snapshot in life_snapshots.items()
        },
        "per_life_second_round_count": {
            life_id: snapshot.second_round_count for life_id, snapshot in life_snapshots.items()
        },
        "per_life_final_E": {life_id: snapshot.e for life_id, snapshot in life_snapshots.items()},
        "per_life_final_q": {life_id: snapshot.q for life_id, snapshot in life_snapshots.items()},
        "per_life_final_G": {
            life_id: snapshot.current_g for life_id, snapshot in life_snapshots.items()
        },
        "per_life_final_k": {
            life_id: snapshot.k_current for life_id, snapshot in life_snapshots.items()
        },
        "per_life_q_update_count": {
            life_id: snapshot.q_update_count for life_id, snapshot in life_snapshots.items()
        },
        "k_update_count": sum(snapshot.k_update_count for snapshot in life_snapshots.values()),
        "completed_round_count": runtime_snapshot.completed_round_count,
        "qualification_record_count": len(qualification_records),
        "touch_digest": garden.touch_digest(),
        "qualification_digest": garden.qualification_digest(),
        "qualified_b_digest": garden.qualified_b_digest(),
        "feedback_digest": garden.feedback_digest(),
        "second_round_digest_by_life": {
            life_id: simulation.digital_life_components[life_id].second_round_digest()
            for life_id in life_ids
        },
        "full_event_digest": simulation.engine.deterministic_digest(),
    }
    if export_csv is not None:
        export_csv.mkdir(parents=True, exist_ok=True)
        garden_paths = export_garden_output_diagnostics(export_csv, garden)
        combined_second_round = tuple(
            sorted(
                (
                    record
                    for component in simulation.digital_life_components.values()
                    for record in component.second_round_records()
                ),
                key=lambda record: (record.signal_index, record.digital_life_id),
            )
        )
        second_round_path = export_second_round_diagnostics_csv(
            export_csv / SECOND_ROUND_CSV_FILENAME,
            combined_second_round,
        )
        result["diagnostic_csvs"] = {
            "touches": str(garden_paths.touches),
            "qualification": str(garden_paths.qualification),
            "qualified_b": str(garden_paths.qualified_b),
            "second_round": str(second_round_path),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_headless_light_device_demo(export_csv: Path | None = None) -> int:
    """Run Stage 6 and emit deterministic Garden-to-light diagnostics."""

    simulation = create_light_feedback_simulation()
    simulation.engine.run_until_end()
    upstream = simulation.upstream_simulation
    mapper = simulation.garden_light_mapper_component
    device = simulation.virtual_light_device_component
    qualified_b_records = upstream.garden_output_component.qualified_b_records()
    command_records = mapper.command_records()
    state_records = device.stimulus_state_records()
    segment_records = device.stimulus_segments()
    waveform_samples = device.waveform_samples()
    active_commands = tuple(record for record in command_records if record.active)
    inactive_commands = tuple(record for record in command_records if not record.active)
    active_segments = tuple(record for record in segment_records if record.active)
    inactive_segments = tuple(record for record in segment_records if not record.active)
    first_active_command = active_commands[0]
    first_active_state = state_records[first_active_command.command_index]
    final_snapshot = device.snapshot()

    result = {
        "project_version": STAGE_6_HEADLESS_PROJECT_VERSION,
        "document_version": DOCUMENT_VERSION,
        "profile_version": PROFILE_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "garden_light_mapper_model_version": GARDEN_LIGHT_MAPPER_MODEL_VERSION,
        "mapping_version": B_TO_I_MAPPING_VERSION,
        "light_command_schema_version": LIGHT_COMMAND_SCHEMA_VERSION,
        "virtual_light_device_model_version": VIRTUAL_LIGHT_DEVICE_MODEL_VERSION,
        "light_stimulus_state_schema_version": (LIGHT_STIMULUS_STATE_SCHEMA_VERSION),
        "light_stimulus_segment_schema_version": (LIGHT_STIMULUS_SEGMENT_SCHEMA_VERSION),
        "phase_policy_version": CONTINUOUS_PHASE_POLICY_VERSION,
        "command_hold_policy_version": COMMAND_HOLD_POLICY_VERSION,
        "inactive_output_policy_version": INACTIVE_OUTPUT_POLICY_VERSION,
        "waveform_sample_policy_version": WAVEFORM_SAMPLE_POLICY_VERSION,
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "qualified_b_input_count": len(qualified_b_records),
        "light_command_count": len(command_records),
        "light_stimulus_state_event_count": len(state_records),
        "segment_count": len(segment_records),
        "active_command_count": len(active_commands),
        "inactive_command_count": len(inactive_commands),
        "active_segment_count": len(active_segments),
        "inactive_segment_count": len(inactive_segments),
        "first_active_effective_time_us": first_active_command.effective_time_us,
        "last_active_effective_time_us": active_commands[-1].effective_time_us,
        "closing_inactive_effective_time_us": (inactive_commands[-1].effective_time_us),
        "first_active_holder_id": first_active_command.qualification_holder_id,
        "first_active_source_b": first_active_command.source_b,
        "first_active_hue_degree": first_active_command.hue_degree,
        "first_active_blink_bpm": first_active_command.blink_bpm,
        "first_active_phase_cycles": first_active_state.phase_cycles_at_start,
        "first_active_value": first_active_state.value_at_start,
        "phase_reset_count": final_snapshot.phase_reset_count,
        "phase_continuation_count": final_snapshot.phase_continuation_count,
        "equivalent_command_count": final_snapshot.equivalent_command_count,
        "physical_parameter_change_count": (final_snapshot.physical_parameter_change_count),
        "final_active": final_snapshot.active,
        "final_value": final_snapshot.current_value,
        "final_phase": final_snapshot.phase_cycles,
        "waveform_sample_interval_us": (
            simulation.virtual_light_device_config.diagnostic_sample_interval_us
        ),
        "waveform_sample_count": len(waveform_samples),
        "command_digest": mapper.command_digest(),
        "stimulus_state_digest": device.stimulus_state_digest(),
        "segment_digest": device.segment_digest(),
        "waveform_sample_digest": device.waveform_sample_digest(),
        "full_event_digest": simulation.engine.deterministic_digest(),
    }
    if export_csv is not None:
        paths = export_light_diagnostics(export_csv, device, command_records)
        result["diagnostic_csvs"] = {
            "commands": str(paths.commands),
            "stimulus_states": str(paths.stimulus_states),
            "stimulus_segments": str(paths.stimulus_segments),
            "waveform_samples": str(paths.waveform_samples),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_headless_light_responsive_user_demo(
    *,
    preset_name: str = DEFAULT_LIGHT_RESPONSE_PRESET,
    export_csv: Path | None = None,
) -> int:
    """Run the Stage 7 closed loop and emit separated causal diagnostics."""

    light_response_config = light_response_config_for_preset(preset_name)
    simulation = create_light_responsive_closed_loop_simulation(
        light_response_config=light_response_config,
    )
    simulation.engine.run_until_end()
    component = simulation.light_responsive_virtual_user_component
    receipts = component.light_receipt_records()
    segments = component.response_segments()
    response_dynamics_epochs = component.response_dynamics_epoch_records()
    samples = component.response_samples()
    heartbeats = component.heartbeat_records()
    responsive_heartbeats = component.responsive_heartbeat_records()
    first_active = next(record for record in receipts if record.active)
    first_heartbeat_at_or_after_active = next(
        record for record in heartbeats if record.heartbeat_time_us >= first_active.event_time_us
    )
    first_affected_interval = next(
        record
        for record in responsive_heartbeats
        if record.true_rri_us is not None
        and record.response_sample_time_us >= first_active.event_time_us
        and record.response_level > 0.0
    )
    garden = simulation.garden_input_component
    garden_snapshot = garden.snapshot()
    evaluations = garden.evaluation_records()
    baseline_evaluation = next(
        record for record in evaluations if record.evaluation_kind == "baseline"
    )
    bundle_evaluations = {
        record.bundle_index: record for record in evaluations if record.evaluation_kind == "bundle"
    }
    life_snapshots = {
        life_id: component.snapshot()
        for life_id, component in sorted(simulation.digital_life_components.items())
    }
    garden_output_snapshot = simulation.garden_output_component.snapshot()
    response_at_90s = component.response_at(90_000_000)
    response_at_120s = component.response_at(120_000_000)
    response_at_180s = component.response_at(180_000_000)
    response_at_240s = component.response_at(240_000_000)
    physiology_at_90s = effective_physiology(
        simulation.virtual_user_config,
        light_response_config,
        response_at_90s,
    )
    written_csvs: tuple[Path, Path, Path, Path, Path] | None = None
    if export_csv is not None:
        written_csvs = export_light_response_diagnostics(export_csv, component)

    result = {
        "project_version": STAGE_7_1_HEADLESS_PROJECT_VERSION,
        "document_version": DOCUMENT_VERSION,
        "profile_version": PROFILE_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "light_responsive_user_model_version": LIGHT_RESPONSE_MODEL_VERSION,
        "physical_projection_version": PHYSICAL_PROJECTION_VERSION,
        "preference_model_version": PREFERENCE_MODEL_VERSION,
        "response_dynamics_version": RESPONSE_DYNAMICS_VERSION,
        "response_segment_schema_version": LIGHT_RESPONSE_SEGMENT_SCHEMA_VERSION,
        "response_dynamics_epoch_schema_version": (LIGHT_RESPONSE_DYNAMICS_EPOCH_SCHEMA_VERSION),
        "physical_stimulus_change_policy_version": (PHYSICAL_STIMULUS_CHANGE_POLICY_VERSION),
        "physical_light_parameter_signature_version": (PHYSICAL_LIGHT_PARAMETER_SIGNATURE_VERSION),
        "segment_split_policy_version": SEGMENT_SPLIT_POLICY_VERSION,
        "physiology_coupling_version": PHYSIOLOGY_COUPLING_VERSION,
        "heartbeat_causality_policy_version": (HEARTBEAT_CAUSALITY_POLICY_VERSION),
        "virtual_user_config": simulation.virtual_user_config.to_dict(),
        "light_response_config": light_response_config.to_dict(),
        "preset": preset_name,
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "light_stimulus_input_count": len(receipts),
        "active_light_input_count": sum(record.active for record in receipts),
        "inactive_light_input_count": sum(not record.active for record in receipts),
        "response_target_change_count": (component.snapshot().response_target_change_count),
        "physical_stimulus_change_count": (component.snapshot().physical_stimulus_change_count),
        "physical_audit_segment_count": len(segments),
        "response_dynamics_epoch_count": len(response_dynamics_epochs),
        "response_segment_count": len(segments),
        "response_sample_count": len(samples),
        "first_active_effective_time_us": first_active.event_time_us,
        "first_active_hue_degree": (first_active.physical_stimulus.render_hue_degree),
        "first_active_blink_bpm": first_active.physical_stimulus.blink_bpm,
        "first_active_hue_match": first_active.hue_match,
        "first_active_bpm_match": first_active.bpm_match,
        "first_active_preference_match": first_active.preference_match,
        "first_heartbeat_at_or_after_active_time_us": (
            first_heartbeat_at_or_after_active.heartbeat_time_us
        ),
        "first_light_affected_interval_start_us": (first_affected_interval.response_sample_time_us),
        "first_light_affected_interval_end_us": (first_affected_interval.heartbeat_time_us),
        "response_at_90s": response_at_90s,
        "response_at_120s": response_at_120s,
        "response_at_180s": response_at_180s,
        "response_at_240s": response_at_240s,
        "effective_respiratory_amplitude_at_90s": physiology_at_90s[4],
        "effective_mean_rri_at_90s": physiology_at_90s[1],
        "heartbeat_count": len(heartbeats),
        "rri_measurement_count": len(simulation.polar_h10_component.measurement_records()),
        "artifact_count": garden_snapshot.artifact_rri_count,
        "evaluation_count": len(evaluations),
        "baseline_evaluation": baseline_evaluation.to_dict(),
        "bundle_0_evaluation": bundle_evaluations[0].to_dict(),
        "bundle_1_evaluation": bundle_evaluations[1].to_dict(),
        "bundle_2_evaluation": bundle_evaluations[2].to_dict(),
        "per_life_final_E": {life_id: snapshot.e for life_id, snapshot in life_snapshots.items()},
        "per_life_final_q": {life_id: snapshot.q for life_id, snapshot in life_snapshots.items()},
        "per_life_final_k": {
            life_id: snapshot.k_current for life_id, snapshot in life_snapshots.items()
        },
        "holder_id": garden_output_snapshot.last_assigned_holder_id,
        "final_holder_id": garden_output_snapshot.qualification_holder_id,
        "heartbeat_digest": component.heartbeat_digest(),
        "responsive_diagnostic_digest": component.responsive_diagnostic_digest(),
        "light_receipt_digest": component.light_receipt_digest(),
        "physical_audit_segment_digest": (component.physical_audit_segment_digest()),
        "response_segment_digest": component.response_segment_digest(),
        "response_dynamics_epoch_digest": (component.response_dynamics_epoch_digest()),
        "response_sample_digest": component.response_sample_digest(),
        "full_event_digest": simulation.engine.deterministic_digest(),
    }
    if written_csvs is not None:
        result["diagnostic_csvs"] = {
            "light_stimulus_receipts": str(written_csvs[0]),
            "light_response_segments": str(written_csvs[1]),
            "response_dynamics_epochs": str(written_csvs[2]),
            "light_responsive_heartbeats": str(written_csvs[3]),
            "light_response_samples": str(written_csvs[4]),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_headless_relation_memory_demo(
    *,
    preset_name: str = DEFAULT_RELATION_MEMORY_PRESET,
    initial_state_json: Path | None = None,
    export_final_state_json: Path | None = None,
    export_csv: Path | None = None,
) -> int:
    """Run one Stage 5C session and emit state, transition, and causal audits."""

    digital_life_configs = tuple(
        digital_life_config_for_role(role) for role in ("red", "green", "blue")
    )
    life_ids = tuple(config.digital_life_id for config in digital_life_configs)
    initial_states = (
        None
        if initial_state_json is None
        else load_relation_memory_state_file(
            initial_state_json,
            expected_digital_life_ids=life_ids,
        )
    )
    light_response_config = light_response_config_for_preset(preset_name)
    simulation = create_adaptive_relation_memory_closed_loop_simulation(
        digital_life_configs=digital_life_configs,
        light_response_config=light_response_config,
        initial_persistent_states_by_life_id=initial_states,
    )
    simulation.engine.run_until_end()
    components = adaptive_digital_life_components(simulation)
    initial_by_life = {
        life_id: components[life_id].initial_persistent_state() for life_id in life_ids
    }
    final_by_life = {life_id: components[life_id].final_persistent_state() for life_id in life_ids}
    if any(state is None for state in final_by_life.values()):
        raise RuntimeError("Stage 5C session did not commit every final state")
    committed_final_by_life = {
        life_id: state for life_id, state in final_by_life.items() if state is not None
    }
    initial_state_values = relation_memory_state_map_to_dict(
        initial_by_life,
        expected_digital_life_ids=life_ids,
    )
    final_state_values = relation_memory_state_map_to_dict(
        committed_final_by_life,
        expected_digital_life_ids=life_ids,
    )
    if export_final_state_json is not None:
        export_relation_memory_state_file(
            export_final_state_json,
            committed_final_by_life,
            expected_digital_life_ids=life_ids,
        )

    session_by_life = {
        life_id: components[life_id].relation_memory_session_state() for life_id in life_ids
    }
    intrinsic_by_life = {
        life_id: components[life_id].relation_memory_intrinsic_profile() for life_id in life_ids
    }
    candidate_by_life = {
        life_id: next(
            (
                record.k_trial
                for record in components[life_id].relation_memory_transition_records()
                if record.k_trial is not None
            ),
            None,
        )
        for life_id in life_ids
    }
    garden_output_snapshot = simulation.garden_output_component.snapshot()
    holder_id = garden_output_snapshot.last_assigned_holder_id
    holder_session = None if holder_id is None else session_by_life[holder_id]

    evaluations = {
        record.bundle_index: record
        for record in simulation.garden_input_component.evaluation_records()
        if record.evaluation_kind == "bundle"
    }
    if set(evaluations) != {0, 1, 2}:
        raise RuntimeError("Stage 5C requires one evaluation for every bundle")

    qualified_by_signal = {
        record.signal_index: record
        for record in simulation.garden_output_component.qualified_b_records()
    }
    command_by_signal = {
        record.source_signal_index: record
        for record in simulation.garden_light_mapper_component.command_records()
    }
    # Bundle 0 is presented from signal 60. Decisions made in the second round
    # of signals 120 and 180 can affect presentation only from 121 and 181.
    representative_signal_by_bundle = {0: 60, 1: 121, 2: 181}
    qualified_b_by_bundle = {
        str(bundle_index): {
            "representative_signal_index": signal_index,
            "effective_time_us": qualified_by_signal[signal_index].effective_time_us,
            "qualification_holder_id": qualified_by_signal[signal_index].qualification_holder_id,
            "b": qualified_by_signal[signal_index].b,
        }
        for bundle_index, signal_index in representative_signal_by_bundle.items()
    }
    hue_bpm_by_bundle = {
        str(bundle_index): {
            "representative_signal_index": signal_index,
            "effective_time_us": command_by_signal[signal_index].command_effective_time_us,
            "hue_degree": command_by_signal[signal_index].hue_degree,
            "blink_bpm": command_by_signal[signal_index].blink_bpm,
        }
        for bundle_index, signal_index in representative_signal_by_bundle.items()
    }

    responsive_user = simulation.light_responsive_virtual_user_component
    result = {
        "project_version": __version__,
        "document_version": DOCUMENT_VERSION,
        "profile_version": PROFILE_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "adaptive_life_model_version": ADAPTIVE_DIGITAL_LIFE_MODEL_VERSION,
        "intrinsic_profile_schema_version": (RELATION_MEMORY_INTRINSIC_PROFILE_SCHEMA_VERSION),
        "transition_schema_version": (RELATION_MEMORY_TRANSITION_RECORD_SCHEMA_VERSION),
        "persistent_state_schema_version": (RELATION_MEMORY_PERSISTENT_STATE_RECORD_SCHEMA_VERSION),
        "session_state_schema_version": (RELATION_MEMORY_SESSION_STATE_RECORD_SCHEMA_VERSION),
        "adaptive_signal_schema_version": (ADAPTIVE_DIGITAL_LIFE_SIGNAL_RECORD_SCHEMA_VERSION),
        "relation_update_effective_policy_version": (RELATION_UPDATE_EFFECTIVE_POLICY_VERSION),
        "bundle1_reject_policy_version": BUNDLE1_REJECT_POLICY_VERSION,
        "light_response_preset": preset_name,
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "holder_id": holder_id,
        "final_holder_id": garden_output_snapshot.qualification_holder_id,
        "initial_persistent_state_by_life": initial_state_values,
        "final_persistent_state_by_life": final_state_values,
        "intrinsic_relation_profile_by_life": {
            life_id: intrinsic_by_life[life_id].to_dict() for life_id in life_ids
        },
        "session_state_by_life": {
            life_id: session_by_life[life_id].to_dict() for life_id in life_ids
        },
        "per_life_adaptation_phase": {
            life_id: session_by_life[life_id].adaptation_phase for life_id in life_ids
        },
        "per_life_exploration_decision": {
            life_id: session_by_life[life_id].exploration_decision for life_id in life_ids
        },
        "per_life_adoption_result": {
            life_id: session_by_life[life_id].adoption_result for life_id in life_ids
        },
        "per_life_initial_k_anchor": {
            life_id: initial_by_life[life_id].k_anchor for life_id in life_ids
        },
        "per_life_k_trial": candidate_by_life,
        "per_life_final_k_anchor": {
            life_id: committed_final_by_life[life_id].k_anchor for life_id in life_ids
        },
        "per_life_trial_count_before": {
            life_id: initial_by_life[life_id].trial_count for life_id in life_ids
        },
        "per_life_trial_count_after": {
            life_id: committed_final_by_life[life_id].trial_count for life_id in life_ids
        },
        "per_life_session_count_before": {
            life_id: initial_by_life[life_id].session_count for life_id in life_ids
        },
        "per_life_session_count_after": {
            life_id: committed_final_by_life[life_id].session_count for life_id in life_ids
        },
        "holder_W_anchor_session": (
            None if holder_session is None else holder_session.w_anchor_session
        ),
        "holder_W_trial_1": (None if holder_session is None else holder_session.w_trial_1),
        "holder_W_trial_2": (None if holder_session is None else holder_session.w_trial_2),
        "holder_sigma": None if holder_session is None else holder_session.sigma,
        "holder_p_explore": (None if holder_session is None else holder_session.p_explore),
        "holder_u_explore": (None if holder_session is None else holder_session.u_explore),
        "holder_epsilon_accept": (
            None if holder_session is None else holder_session.epsilon_accept
        ),
        "bundle_0_evaluation": evaluations[0].to_dict(),
        "bundle_1_evaluation": evaluations[1].to_dict(),
        "bundle_2_evaluation": evaluations[2].to_dict(),
        "qualified_B_by_bundle": qualified_b_by_bundle,
        "Hue_BPM_by_bundle": hue_bpm_by_bundle,
        "relation_memory_transition_count": sum(
            len(component.relation_memory_transition_records()) for component in components.values()
        ),
        "k_anchor_update_count": sum(
            component.k_anchor_update_count() for component in components.values()
        ),
        "candidate_count": sum(component.candidate_count() for component in components.values()),
        "intrinsic_profile_digest": intrinsic_profile_digest(components),
        "adaptive_signal_digest": adaptive_signal_digest(components),
        "relation_memory_transition_digest": (relation_memory_transition_digest(components)),
        "final_persistent_state_digest": (final_persistent_state_digest(components)),
        "session_summary_digest": session_summary_digest(components),
        "physical_audit_segment_digest": (responsive_user.physical_audit_segment_digest()),
        "response_dynamics_epoch_digest": (responsive_user.response_dynamics_epoch_digest()),
        "full_event_digest": simulation.engine.deterministic_digest(),
        "single_session_only": True,
        "convergence_evaluated": False,
        "multi_session_not_implemented": True,
    }
    if export_final_state_json is not None:
        result["final_relation_state_json"] = str(export_final_state_json)
    if export_csv is not None:
        csv_paths = export_relation_memory_diagnostics(export_csv, components)
        result["relation_memory_csvs"] = {
            "intrinsic_profiles": str(csv_paths[0]),
            "relation_transitions": str(csv_paths[1]),
            "adaptive_signals": str(csv_paths[2]),
            "persistent_states": str(csv_paths[3]),
            "session_summary": str(csv_paths[4]),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def run_single_life_gui(
    *,
    smoke_test: bool,
    auto_close_ms: int,
    screenshot: Path | None,
    screenshot_target: str = "window",
    life_role: str = "green",
) -> int:
    """Start the backward-compatible Stage 5A single-life Qt application."""

    if auto_close_ms <= 0:
        raise ValueError("--auto-close-ms must be positive")

    # Qt on macOS warns and substitutes defaults when launched from a shell with
    # the unsupported C.UTF-8 locale. Keep normal user locales, but normalize C.
    if os.environ.get("LC_ALL", "") in {"", "C", "C.UTF-8", "POSIX"}:
        os.environ["LC_ALL"] = "en_US.UTF-8"
    if os.environ.get("LANG", "") in {"", "C", "C.UTF-8", "POSIX"}:
        os.environ["LANG"] = "en_US.UTF-8"

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from symbiotic_sim_v2.gui.controller import SimulationController
    from symbiotic_sim_v2.gui.digital_life_window import SingleDigitalLifeMainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    available_fonts = set(QFontDatabase.families())
    for family in (".AppleSystemUIFont", "Noto Sans", "DejaVu Sans", "Arial"):
        if family in available_fonts:
            app.setFont(QFont(family))
            break
    simulation = create_single_digital_life_simulation(
        digital_life_config=digital_life_config_for_role(life_role),
    )
    controller = SimulationController(simulation.engine)
    window = SingleDigitalLifeMainWindow(controller, simulation)
    app.aboutToQuit.connect(controller.shutdown)
    window.show()

    if smoke_test:
        actions = (
            (50, window.start_button.click),
            (100, window.pause_button.click),
            (150, window.resume_button.click),
            (200, window.pause_button.click),
            (250, window.step_second_button.click),
            (300, window.step_event_button.click),
            (350, lambda: window.speed_combo.setCurrentIndex(1)),
            (400, lambda: window.speed_combo.setCurrentIndex(2)),
            (450, lambda: window.speed_combo.setCurrentIndex(3)),
            (500, window.reset_button.click),
            (525, lambda: window.digital_life_panel.role_combo.setCurrentText("red")),
            (550, lambda: window.digital_life_panel.role_combo.setCurrentText(life_role)),
            (600, window.run_to_end_button.click),
            (700, lambda: window.tabs.setCurrentIndex(0)),
            (775, lambda: window.tabs.setCurrentIndex(1)),
            (850, lambda: window.tabs.setCurrentIndex(2)),
            (925, lambda: window.tabs.setCurrentIndex(3)),
            (1000, lambda: window.tabs.setCurrentIndex(4)),
            (1075, lambda: window.tabs.setCurrentIndex(0)),
        )
        for delay_ms, action in actions:
            QTimer.singleShot(delay_ms, action)

        def validate_smoke() -> None:
            failures: list[str] = []
            expected_tabs = (
                "デジタル生命",
                "Garden入力層",
                "仮想ユーザー",
                "Polar H10",
                "時間・イベント診断",
            )
            actual_tabs = tuple(window.tabs.tabText(index) for index in range(window.tabs.count()))
            if actual_tabs != expected_tabs:
                failures.append(f"tabs={actual_tabs!r}")
            active = window.simulation
            if active.engine.clock.state.value != "completed":
                failures.append(f"state={active.engine.clock.state.value}")
            if active.digital_life_config.role != life_role:
                failures.append(f"role={active.digital_life_config.role}")
            heartbeat_records = active.virtual_user_component.heartbeat_records()
            measurement_records = active.polar_h10_component.measurement_records()
            garden = active.garden_input_component
            life = active.digital_life_component
            if len(heartbeat_records) != 280:
                failures.append(f"heartbeat_count={len(heartbeat_records)}")
            if len(measurement_records) != 279:
                failures.append(f"rri_count={len(measurement_records)}")
            if len(garden.rri_records()) != 279:
                failures.append(f"garden_rri_count={len(garden.rri_records())}")
            if len(garden.signal_records()) != 241:
                failures.append(f"garden_signal_count={len(garden.signal_records())}")
            if len(garden.evaluation_records()) != 4:
                failures.append(f"evaluation_count={len(garden.evaluation_records())}")
            if len(life.first_round_records()) != 241:
                failures.append(f"life_record_count={len(life.first_round_records())}")
            if len(life.evaluation_update_records()) != 4:
                failures.append(f"life_evaluation_count={len(life.evaluation_update_records())}")
            life_snapshot = life.snapshot()
            if life_snapshot.g_status != "not_connected":
                failures.append(f"G_status={life_snapshot.g_status}")
            if life_snapshot.second_round_connected:
                failures.append("second round unexpectedly connected")
            if life_snapshot.touch_dispatched_count != 0:
                failures.append("touch was unexpectedly dispatched")
            life_panel = window.digital_life_panel
            if life_panel.chart.record_count != 241:
                failures.append("Digital Life chart data missing")
            if life_panel.chart.evaluation_point_count != 4:
                failures.append("Digital Life evaluation points missing")
            if life_panel.signal_model.rowCount() != 241:
                failures.append("Digital Life signal table rows missing")
            if life_panel.evaluation_model.rowCount() != 4:
                failures.append("Digital Life evaluation table rows missing")
            if life_panel.role_combo.isEnabled():
                failures.append("Digital Life role selector enabled after completion")
            if window.virtual_user_panel.chart.record_count != 280:
                failures.append("virtual-user chart data missing")
            if window.polar_h10_panel.chart.record_count != 279:
                failures.append("H10 comparison chart data missing")
            error_data = window.polar_h10_panel.chart.error_item.yData
            if error_data is None or len(error_data) != 279 or any(error_data):
                failures.append("H10 error chart is not the 279-point zero series")
            if window.polar_h10_panel.measurement_model.rowCount() != 279:
                failures.append("H10 table rows missing")
            garden_panel = window.garden_input_panel
            if garden_panel.chart.rri_count != 279:
                failures.append("Garden RRI chart data missing")
            if garden_panel.chart.evaluation_count != 4:
                failures.append("Garden evaluation chart data missing")
            if garden_panel.chart.signal_count != 241:
                failures.append("Garden N/S chart data missing")
            if garden_panel.rri_model.rowCount() != 279:
                failures.append("Garden RRI table rows missing")
            if garden_panel.evaluation_model.rowCount() != 4:
                failures.append("Garden evaluation table rows missing")
            if garden_panel.timeline.phase_region_count != 8:
                failures.append("Garden phase timeline regions missing")
            if garden_panel.timeline.signal_count != 241:
                failures.append("Garden S timeline data missing")
            event_types = {event.event_type for event in active.engine.executed_events()}
            if (
                not {
                    "heartbeat",
                    "rri_measurement",
                    "garden_input_signal",
                    "garden_evaluation_finalized",
                }
                <= event_types
            ):
                failures.append("timeline event types missing")
            if failures:
                print("GUI smoke failed: " + "; ".join(failures), file=sys.stderr)
                app.exit(1)

        QTimer.singleShot(2000, validate_smoke)
        QTimer.singleShot(auto_close_ms, app.quit)

    if screenshot is not None:
        screenshot.parent.mkdir(parents=True, exist_ok=True)

        def save_screenshot() -> None:
            target = window if screenshot_target == "window" else window.digital_life_panel.chart
            if not target.grab().save(str(screenshot)):
                raise RuntimeError(f"failed to save screenshot: {screenshot}")

        screenshot_delay_ms = min(2200, max(1500, auto_close_ms - 100)) if smoke_test else 250
        QTimer.singleShot(screenshot_delay_ms, save_screenshot)

    return app.exec()


def run_stage6_gui(
    *,
    smoke_test: bool,
    auto_close_ms: int,
    screenshot: Path | None,
    screenshot_target: str = "window",
) -> int:
    """Retain the Stage 6 seven-tab GUI as a backward-compatible helper."""

    if auto_close_ms <= 0:
        raise ValueError("--auto-close-ms must be positive")
    if os.environ.get("LC_ALL", "") in {"", "C", "C.UTF-8", "POSIX"}:
        os.environ["LC_ALL"] = "en_US.UTF-8"
    if os.environ.get("LANG", "") in {"", "C", "C.UTF-8", "POSIX"}:
        os.environ["LANG"] = "en_US.UTF-8"

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from symbiotic_sim_v2.gui.controller import SimulationController
    from symbiotic_sim_v2.gui.light_simulation_window import LightSimulationMainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    available_fonts = set(QFontDatabase.families())
    for family in (".AppleSystemUIFont", "Noto Sans", "DejaVu Sans", "Arial"):
        if family in available_fonts:
            app.setFont(QFont(family))
            break
    simulation = create_light_feedback_simulation()
    controller = SimulationController(simulation.engine)
    window = LightSimulationMainWindow(controller, simulation)
    app.aboutToQuit.connect(controller.shutdown)
    window.show()

    smoke_failures: list[str] = []
    if smoke_test:

        def finish_smoke_run() -> None:
            # The button below exercises the normal bounded GUI path. Finish the
            # same production engine synchronously so dense offscreen chart draws
            # cannot make the fixed 4500 ms smoke contract machine-dependent.
            if window.simulation.engine.clock.state.value != "completed":
                window.simulation.engine.run_until_end()
            controller.set_speed(controller.speed_mode)

        actions = (
            (50, window.start_button.click),
            (100, window.pause_button.click),
            (150, window.resume_button.click),
            (200, window.pause_button.click),
            (250, window.step_second_button.click),
            (300, window.step_event_button.click),
            (350, lambda: window.speed_combo.setCurrentIndex(1)),
            (400, lambda: window.speed_combo.setCurrentIndex(2)),
            (450, lambda: window.speed_combo.setCurrentIndex(3)),
            (500, window.reset_button.click),
            (600, window.run_to_end_button.click),
            (650, finish_smoke_run),
            (900, lambda: window.tabs.setCurrentIndex(0)),
            (1_000, lambda: window.tabs.setCurrentIndex(1)),
            (1_100, lambda: window.tabs.setCurrentIndex(2)),
            (1_200, lambda: window.tabs.setCurrentIndex(3)),
            (1_300, lambda: window.tabs.setCurrentIndex(4)),
            (1_400, lambda: window.tabs.setCurrentIndex(5)),
            (1_500, lambda: window.tabs.setCurrentIndex(0)),
        )
        for delay_ms, action in actions:
            QTimer.singleShot(delay_ms, action)

        def validate_smoke() -> None:
            failures: list[str] = []
            expected_tabs = (
                "光点滅シミュレーター",
                "3生命・資格競争",
                "Garden出力資格層",
                "Garden入力層",
                "仮想ユーザー",
                "Polar H10",
                "時間・イベント診断",
            )
            actual_tabs = tuple(window.tabs.tabText(index) for index in range(window.tabs.count()))
            if actual_tabs != expected_tabs:
                failures.append(f"tabs={actual_tabs!r}")
            active = window.simulation
            if active.engine.clock.state.value != "completed":
                failures.append(f"state={active.engine.clock.state.value}")
            upstream = active.upstream_simulation
            if len(upstream.virtual_user_component.heartbeat_records()) != 280:
                failures.append("heartbeat count")
            if len(upstream.polar_h10_component.measurement_records()) != 279:
                failures.append("RRI count")
            if len(upstream.garden_input_component.signal_records()) != 241:
                failures.append("Garden signal count")
            garden_snapshot = upstream.garden_output_component.snapshot()
            expected_garden = (
                garden_snapshot.total_touch_count == 540
                and garden_snapshot.feedback_count == 723
                and garden_snapshot.active_output_count == 180
                and garden_snapshot.inactive_output_count == 61
                and garden_snapshot.assignment_count == 1
                and garden_snapshot.release_count == 1
                and garden_snapshot.last_assigned_holder_id == "life-green"
                and garden_snapshot.qualification_holder_id is None
            )
            if not expected_garden:
                failures.append(f"Garden output={garden_snapshot!r}")
            for life_id, component in upstream.digital_life_components.items():
                snapshot = component.snapshot()
                if (
                    snapshot.first_round_count != 241
                    or snapshot.second_round_count != 241
                    or snapshot.touch_dispatched_count != 180
                    or snapshot.current_g != 0
                    or snapshot.k_update_count != 0
                ):
                    failures.append(f"life={life_id}:{snapshot!r}")
            green = upstream.green_life_component.snapshot()
            if green.e <= 0.14 or green.q_update_count != 3:
                failures.append("green E/q")
            multi_panel = window.multi_life_panel
            if (
                multi_panel.chart.first_round_count != 723
                or multi_panel.chart.second_round_count != 723
                or multi_panel.chart.touch_count != 540
                or multi_panel.touch_model.rowCount() != 540
                or multi_panel.second_round_model.rowCount() != 723
            ):
                failures.append("multi-life chart/table data")
            output_panel = window.garden_output_panel
            if (
                output_panel.chart.qualification_count != 241
                or output_panel.chart.qualified_b_count != 241
                or output_panel.chart.active_effective_count != 180
                or output_panel.chart.holder_touch_count != 180
                or output_panel.chart.round_finalize_count != 180
                or output_panel.qualification_model.rowCount() != 241
            ):
                failures.append("Garden output chart/table data")
            effective_times = output_panel.chart.active_effective_item.xData
            holder_touch_times = output_panel.chart.holder_touch_item.xData
            finalize_times = output_panel.chart.round_finalize_item.xData
            if (
                effective_times is None
                or holder_touch_times is None
                or finalize_times is None
                or effective_times[0] != holder_touch_times[0]
                or effective_times[0] >= finalize_times[0]
                or output_panel.qualified_b_delay_label.text() != "0 us"
                or output_panel.active_emission_status_label.text()
                != "yes — holder touchと同じmicrosecond"
                or "role" in multi_panel.touch_model.HEADERS
            ):
                failures.append("qualified B effective timing/boundary")
            if window.virtual_user_panel.chart.record_count != 280:
                failures.append("Virtual User chart")
            if window.polar_h10_panel.chart.record_count != 279:
                failures.append("H10 chart")
            if window.garden_input_panel.chart.signal_count != 241:
                failures.append("Garden input chart")
            mapper = active.garden_light_mapper_component
            device = active.virtual_light_device_component
            commands = mapper.command_records()
            states = device.stimulus_state_records()
            segments = device.stimulus_segments()
            active_commands = tuple(record for record in commands if record.active)
            final_light = device.snapshot()
            first_command = active_commands[0] if active_commands else None
            light_panel = window.light_output_panel
            if (
                len(commands) != 241
                or len(states) != 241
                or len(segments) != 240
                or len(active_commands) != 180
                or sum(not record.active for record in commands) != 61
            ):
                failures.append("Stage 6 command/state/segment counts")
            if (
                first_command is None
                or first_command.qualification_holder_id != "life-green"
                or first_command.source_b != (125.0 / 360.0, 0.5, 0.5, 0.5)
                or first_command.hue_degree != 125.0
                or first_command.blink_bpm != 87.5
            ):
                failures.append("Stage 6 first active mapping")
            if (
                final_light.active
                or final_light.current_value != 0.0
                or final_light.phase_cycles is not None
                or final_light.phase_reset_count != 1
                or final_light.phase_continuation_count != 179
            ):
                failures.append("Stage 6 phase/final inactive state")
            if (
                light_panel.command_model.rowCount() != 241
                or light_panel.segment_model.rowCount() != 240
                or light_panel.parameter_chart.command_count != 241
                or light_panel.preview_checkbox.isChecked()
            ):
                failures.append("Stage 6 GUI chart/table/preview")
            event_types = {event.event_type for event in active.engine.executed_events()}
            required_types = {
                "digital_life_touch",
                "garden_qualified_b",
                "garden_interoceptive_feedback",
                "garden_holder_release",
                "light_command",
                "light_stimulus_state",
            }
            if not required_types <= event_types:
                failures.append("Stage 5B event types")
            if failures:
                smoke_failures.extend(failures)
                print("GUI smoke failed: " + "; ".join(failures), file=sys.stderr)
                app.quit()

        # Stage 5B publishes several dense charts while bounded max-speed batches
        # execute.  Validate near (but safely before) the requested close time so
        # the smoke test remains deterministic on slower offscreen renderers.
        QTimer.singleShot(max(2_000, auto_close_ms - 200), validate_smoke)
        QTimer.singleShot(auto_close_ms, app.quit)

    if screenshot is not None:
        screenshot.parent.mkdir(parents=True, exist_ok=True)

        def save_screenshot() -> None:
            light_panel = window.light_output_panel
            if screenshot_target == "light-output-overview":
                controller.reset()
                window.speed_combo.setCurrentIndex(0)
                engine = window.simulation.engine
                for _ in range(10_000):
                    event = engine.step_one_event()
                    if event is None:
                        raise RuntimeError("first active light state was not reached")
                    if (
                        event.event_type == "light_stimulus_state"
                        and event.payload["active"] is True
                    ):
                        break
                else:  # pragma: no cover - bounded production fixture guard
                    raise RuntimeError("first active light state search exceeded limit")
                controller.snapshot_changed.emit(controller.current_snapshot())
                light_panel.preview_checkbox.setChecked(True)
            elif screenshot_target == "continuous-phase-waveform":
                controller.reset()
                window.speed_combo.setCurrentIndex(0)
                engine = window.simulation.engine
                for _ in range(75):
                    engine.step_one_second()
                controller.snapshot_changed.emit(controller.current_snapshot())
            targets = {
                "window": window,
                "three-life-overview": window,
                "touch-holder-second-round": (window.multi_life_panel.chart_table_splitter),
                "garden-output-qualified-b": (window.garden_output_panel.diagnostics_content),
                "light-output-overview": window,
                "continuous-phase-waveform": light_panel.waveform_chart,
                "light-command-segments": light_panel.chart_table_splitter,
            }
            if screenshot_target == "garden-output-qualified-b":
                window.tabs.setCurrentWidget(window.garden_output_panel)
            elif screenshot_target in {
                "three-life-overview",
                "touch-holder-second-round",
            }:
                window.tabs.setCurrentWidget(window.multi_life_panel)
            elif screenshot_target in {
                "light-output-overview",
                "continuous-phase-waveform",
                "light-command-segments",
            }:
                window.tabs.setCurrentWidget(light_panel)
                if screenshot_target == "light-output-overview":
                    light_panel.diagnostics_scroll.verticalScrollBar().setValue(0)
                elif screenshot_target == "continuous-phase-waveform":
                    light_panel.diagnostics_scroll.ensureWidgetVisible(light_panel.waveform_chart)
                else:
                    light_panel.table_tabs.setCurrentIndex(1)
                    light_panel.chart_table_splitter.setSizes([480, 520, 480])
                    light_panel.diagnostics_scroll.ensureWidgetVisible(
                        light_panel.chart_table_splitter
                    )
            app.processEvents()
            target = targets.get(screenshot_target, window)
            if not target.grab().save(str(screenshot)):
                raise RuntimeError(f"failed to save screenshot: {screenshot}")

        screenshot_delay_ms = max(1_500, auto_close_ms - 100) if smoke_test else 250
        QTimer.singleShot(screenshot_delay_ms, save_screenshot)

    exit_code = app.exec()
    return 1 if smoke_failures else exit_code


def run_gui(
    *,
    smoke_test: bool,
    auto_close_ms: int,
    screenshot: Path | None,
    screenshot_target: str = "window",
    preset_name: str = DEFAULT_RELATION_MEMORY_PRESET,
) -> int:
    """Start the Stage 5C nine-tab confirmed relation-memory GUI."""

    if auto_close_ms <= 0:
        raise ValueError("--auto-close-ms must be positive")
    light_response_config = light_response_config_for_preset(preset_name)
    if os.environ.get("LC_ALL", "") in {"", "C", "C.UTF-8", "POSIX"}:
        os.environ["LC_ALL"] = "en_US.UTF-8"
    if os.environ.get("LANG", "") in {"", "C", "C.UTF-8", "POSIX"}:
        os.environ["LANG"] = "en_US.UTF-8"

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication

    from symbiotic_sim_v2.gui.adaptive_closed_loop_window import (
        AdaptiveClosedLoopMainWindow,
    )
    from symbiotic_sim_v2.gui.controller import SimulationController

    app = QApplication.instance() or QApplication(sys.argv[:1])
    available_fonts = set(QFontDatabase.families())
    for family in (".AppleSystemUIFont", "Noto Sans", "DejaVu Sans", "Arial"):
        if family in available_fonts:
            app.setFont(QFont(family))
            break
    simulation = create_adaptive_relation_memory_closed_loop_simulation(
        light_response_config=light_response_config,
    )
    controller = SimulationController(simulation.engine)
    window = AdaptiveClosedLoopMainWindow(
        controller,
        simulation,
        preset_name=preset_name,
    )
    app.aboutToQuit.connect(controller.shutdown)
    window.show()

    smoke_failures: list[str] = []
    if smoke_test:

        def select_preset(name: str) -> None:
            combo = window.light_response_user_panel.preset_combo
            index = combo.findData(name)
            if index < 0:
                raise RuntimeError(f"missing Stage 7 preset: {name}")
            combo.setCurrentIndex(index)
            combo.activated.emit(index)

        def finish_smoke_run() -> None:
            if window.simulation.engine.clock.state.value != "completed":
                window.simulation.engine.run_until_end()
            controller.set_speed(controller.speed_mode)

        actions = (
            (50, window.start_button.click),
            (100, window.pause_button.click),
            (150, window.resume_button.click),
            (200, window.pause_button.click),
            (250, window.step_second_button.click),
            (300, window.step_event_button.click),
            (350, lambda: window.speed_combo.setCurrentIndex(1)),
            (400, lambda: window.speed_combo.setCurrentIndex(2)),
            (450, lambda: window.speed_combo.setCurrentIndex(3)),
            (500, window.reset_button.click),
            (650, lambda: select_preset("light_insensitive_control")),
            (850, lambda: select_preset("off_center_green")),
            (1_050, window.run_to_end_button.click),
            (1_250, finish_smoke_run),
            (1_500, lambda: window.tabs.setCurrentIndex(0)),
            (1_600, lambda: window.tabs.setCurrentIndex(1)),
            (1_700, lambda: window.tabs.setCurrentIndex(2)),
            (1_800, lambda: window.tabs.setCurrentIndex(3)),
            (1_900, lambda: window.tabs.setCurrentIndex(4)),
            (2_000, lambda: window.tabs.setCurrentIndex(5)),
            (2_100, lambda: window.tabs.setCurrentIndex(6)),
            (2_200, lambda: window.tabs.setCurrentIndex(7)),
            (2_300, lambda: window.tabs.setCurrentIndex(8)),
            (2_400, lambda: window.tabs.setCurrentIndex(0)),
        )
        for delay_ms, action in actions:
            QTimer.singleShot(delay_ms, action)

        def validate_smoke() -> None:
            failures: list[str] = []
            expected_tabs = (
                "関係記憶探索",
                "光応答仮想ユーザー",
                "光点滅シミュレーター",
                "3生命・資格競争",
                "Garden出力資格層",
                "Garden入力層",
                "仮想ユーザー心拍",
                "Polar H10",
                "時間・イベント診断",
            )
            actual_tabs = tuple(window.tabs.tabText(index) for index in range(window.tabs.count()))
            if actual_tabs != expected_tabs:
                failures.append(f"tabs={actual_tabs!r}")
            active = window.simulation
            component = active.light_responsive_virtual_user_component
            response_panel = window.light_response_user_panel
            if active.engine.clock.state.value != "completed":
                failures.append(f"state={active.engine.clock.state.value}")
            if response_panel.preset_name != "off_center_green":
                failures.append(f"preset={response_panel.preset_name}")
            receipts = component.light_receipt_records()
            responsive_heartbeats = component.responsive_heartbeat_records()
            segments = component.response_segments()
            response_epochs = component.response_dynamics_epoch_records()
            samples = component.response_samples() if component.snapshot().completed else ()
            first_active = next((record for record in receipts if record.active), None)
            if (
                len(receipts) != 241
                or len(responsive_heartbeats) != 279
                or len(segments) != 2
                or len(response_epochs) != 2
                or len(samples) != 2_401
            ):
                failures.append("Stage 7 record counts")
            if (
                first_active is None
                or first_active.event_time_us != 60_551_540
                or not 0.33 < first_active.preference_match < 0.34
                or first_active.response_before != 0.0
                or not 0.32 < component.response_at(90_000_000) < 0.33
            ):
                failures.append("first active/preference/response onset")
            snapshot = component.snapshot()
            if (
                snapshot.current_light_active
                or snapshot.current_response_target != 0.0
                or not 0.33 < snapshot.current_response_level < 0.34
                or snapshot.effective_respiratory_amplitude_ms <= 44.9
                or not snapshot.completed
            ):
                failures.append(f"closing response={snapshot!r}")
            evaluations = active.garden_input_component.evaluation_records()
            if (
                len(evaluations) != 4
                or any(record.rmssd_ms is None for record in evaluations)
                or any(record.n is None for record in evaluations)
                or any(record.rmssd_ms <= evaluations[0].rmssd_ms for record in evaluations[1:])
            ):
                failures.append("Garden RMSSD/N evaluations")
            if len(active.polar_h10_component.measurement_records()) != 278:
                failures.append("H10 changed RRI count")
            if (
                response_panel.receipt_model.rowCount() != 241
                or response_panel.audit_segment_model.rowCount() != 2
                or response_panel.response_epoch_model.rowCount() != 2
                or response_panel.heartbeat_model.rowCount() != 279
                or response_panel.light_response_chart.sample_count != 2_401
                or response_panel.light_response_chart.audit_segment_boundary_count != 2
                or response_panel.light_response_chart.response_epoch_boundary_count != 2
                or response_panel.physiology_chart.record_count != 279
                or response_panel.garden_evaluation_chart.evaluation_count != 4
            ):
                failures.append("Stage 7 charts/tables")
            if (
                window.light_output_panel.command_model.rowCount() != 241
                or window.multi_life_panel.touch_model.rowCount() != 540
                or window.garden_output_panel.qualification_model.rowCount() != 241
                or window.garden_input_panel.chart.evaluation_count != 4
                or window.virtual_user_panel.chart.record_count != 279
                or window.polar_h10_panel.chart.record_count != 278
            ):
                failures.append("retained Stage 2-6 tabs")
            relation_panel = window.relation_memory_panel
            adaptive_components = adaptive_digital_life_components(active)
            holder_session = adaptive_components[
                "life-green"
            ].relation_memory_session_state()
            if (
                relation_panel.transition_model.rowCount() != 12
                or relation_panel.signal_model.rowCount() != 723
                or relation_panel.persistent_model.rowCount() != 6
                or relation_panel.chart.transition_count != 12
                or relation_panel.chart.signal_count != 723
                or relation_panel.chart.qualified_b_change_count != 1
                or relation_panel.chart.hue_bpm_change_count != 1
                or holder_session.w_anchor_session != 1.0
                or holder_session.exploration_decision != "hold"
                or holder_session.candidate_generated
                or holder_session.adoption_result != "hold"
                or not holder_session.session_finalized
                or any(
                    component.final_persistent_state() is None
                    for component in adaptive_components.values()
                )
                or any(
                    component.final_persistent_state().session_count != 1
                    for component in adaptive_components.values()
                )
            ):
                failures.append("Stage 5C relation-memory diagnostics")
            if window.light_output_panel.preview_checkbox.isChecked():
                failures.append("real-light preview unexpectedly enabled")
            if response_panel.settings_frame.isEnabled():
                failures.append("fixed preference settings enabled after completion")
            life_snapshots = {
                life_id: life.snapshot() for life_id, life in active.digital_life_components.items()
            }
            if any(snapshot.k_update_count != 0 for snapshot in life_snapshots.values()):
                failures.append("Stage 5C k update unexpectedly present")
            if failures:
                smoke_failures.extend(failures)
                print("GUI smoke failed: " + "; ".join(failures), file=sys.stderr)
                app.quit()

        QTimer.singleShot(max(2_500, auto_close_ms - 350), validate_smoke)
        QTimer.singleShot(auto_close_ms, app.quit)

    if screenshot is not None:
        screenshot.parent.mkdir(parents=True, exist_ok=True)

        def save_screenshot() -> None:
            panel = window.light_response_user_panel
            relation_panel = window.relation_memory_panel
            targets = {
                "window": window,
                "stage-05c-relation-memory-overview": window,
                "stage-05c-k-ft-search-and-thresholds": relation_panel.chart,
                "stage-05c-transition-and-persistent-state": (
                    relation_panel.table_tabs
                ),
                "stage-07-light-response-overview": window,
                "stage-07-preference-response-physiology": (panel.chart_table_splitter),
                "stage-07-heartbeat-rmssd-closed-loop": (panel.chart_table_splitter),
                "three-life-overview": window,
                "touch-holder-second-round": window.multi_life_panel.chart_table_splitter,
                "garden-output-qualified-b": (window.garden_output_panel.diagnostics_content),
                "light-output-overview": window,
                "continuous-phase-waveform": window.light_output_panel.waveform_chart,
                "light-command-segments": (window.light_output_panel.chart_table_splitter),
            }
            if screenshot_target in {
                "stage-05c-relation-memory-overview",
                "stage-05c-k-ft-search-and-thresholds",
                "stage-05c-transition-and-persistent-state",
            }:
                window.tabs.setCurrentWidget(relation_panel)
                if screenshot_target == "stage-05c-relation-memory-overview":
                    relation_panel.diagnostics_scroll.verticalScrollBar().setValue(0)
                elif screenshot_target == "stage-05c-k-ft-search-and-thresholds":
                    relation_panel.diagnostics_scroll.ensureWidgetVisible(
                        relation_panel.chart
                    )
                else:
                    relation_panel.table_tabs.setCurrentIndex(2)
                    relation_panel.diagnostics_scroll.ensureWidgetVisible(
                        relation_panel.table_tabs
                    )
            elif screenshot_target in {
                "stage-07-light-response-overview",
                "stage-07-preference-response-physiology",
                "stage-07-heartbeat-rmssd-closed-loop",
            }:
                window.tabs.setCurrentWidget(panel)
                if screenshot_target == "stage-07-light-response-overview":
                    panel.diagnostics_scroll.verticalScrollBar().setValue(0)
                elif screenshot_target == "stage-07-preference-response-physiology":
                    panel.table_tabs.setCurrentIndex(0)
                    panel.diagnostics_scroll.ensureWidgetVisible(panel.light_response_chart)
                else:
                    panel.table_tabs.setCurrentIndex(1)
                    panel.diagnostics_scroll.ensureWidgetVisible(panel.garden_evaluation_chart)
            elif screenshot_target in {
                "three-life-overview",
                "touch-holder-second-round",
            }:
                window.tabs.setCurrentWidget(window.multi_life_panel)
            elif screenshot_target == "garden-output-qualified-b":
                window.tabs.setCurrentWidget(window.garden_output_panel)
            elif screenshot_target in {
                "light-output-overview",
                "continuous-phase-waveform",
                "light-command-segments",
            }:
                window.tabs.setCurrentWidget(window.light_output_panel)
            app.processEvents()
            target = targets.get(screenshot_target, window)
            if not target.grab().save(str(screenshot)):
                raise RuntimeError(f"failed to save screenshot: {screenshot}")

        screenshot_delay_ms = max(2_000, auto_close_ms - 150) if smoke_test else 250
        QTimer.singleShot(screenshot_delay_ms, save_screenshot)

    exit_code = app.exec()
    return 1 if smoke_failures else exit_code


def main(argv: list[str] | None = None) -> int:
    """Parse CLI options without importing Qt on the headless path."""

    args = _build_parser().parse_args(argv)
    if args.export_virtual_user_csv is not None and not args.headless_virtual_user_demo:
        raise ValueError("--export-virtual-user-csv requires --headless-virtual-user-demo")
    if args.export_h10_csv is not None and not args.headless_h10_demo:
        raise ValueError("--export-h10-csv requires --headless-h10-demo")
    if args.export_garden_input_csv is not None and not args.headless_garden_input_demo:
        raise ValueError("--export-garden-input-csv requires --headless-garden-input-demo")
    if args.export_single_life_csv is not None and not args.headless_single_life_demo:
        raise ValueError("--export-single-life-csv requires --headless-single-life-demo")
    if (
        args.export_three_life_competition_csv is not None
        and not args.headless_three_life_competition_demo
    ):
        raise ValueError(
            "--export-three-life-competition-csv requires --headless-three-life-competition-demo"
        )
    if args.export_light_device_csv is not None and not args.headless_light_device_demo:
        raise ValueError("--export-light-device-csv requires --headless-light-device-demo")
    if (
        args.export_light_responsive_user_csv is not None
        and not args.headless_light_responsive_user_demo
    ):
        raise ValueError(
            "--export-light-responsive-user-csv requires --headless-light-responsive-user-demo"
        )
    relation_memory_options = (
        args.initial_relation_state_json,
        args.export_final_relation_state_json,
        args.export_relation_memory_csv,
    )
    if any(value is not None for value in relation_memory_options) and not (
        args.headless_relation_memory_demo
    ):
        raise ValueError(
            "Stage 5C state/CSV options require --headless-relation-memory-demo"
        )
    if args.headless_demo or args.headless_time_demo:
        return run_headless_demo()
    if args.headless_virtual_user_demo:
        return run_headless_virtual_user_demo(args.export_virtual_user_csv)
    if args.headless_h10_demo:
        return run_headless_h10_demo(args.export_h10_csv)
    if args.headless_garden_input_demo:
        return run_headless_garden_input_demo(args.export_garden_input_csv)
    if args.headless_single_life_demo:
        return run_headless_single_life_demo(
            life_role=args.life_role or "green",
            export_csv=args.export_single_life_csv,
        )
    if args.headless_three_life_competition_demo:
        return run_headless_three_life_competition_demo(args.export_three_life_competition_csv)
    if args.headless_light_device_demo:
        return run_headless_light_device_demo(args.export_light_device_csv)
    if args.headless_light_responsive_user_demo:
        return run_headless_light_responsive_user_demo(
            preset_name=args.light_response_preset or DEFAULT_LIGHT_RESPONSE_PRESET,
            export_csv=args.export_light_responsive_user_csv,
        )
    if args.headless_relation_memory_demo:
        return run_headless_relation_memory_demo(
            preset_name=args.light_response_preset or DEFAULT_RELATION_MEMORY_PRESET,
            initial_state_json=args.initial_relation_state_json,
            export_final_state_json=args.export_final_relation_state_json,
            export_csv=args.export_relation_memory_csv,
        )
    if args.life_role is not None or args.screenshot_target == "digital-life-graphs":
        return run_single_life_gui(
            smoke_test=args.smoke_test,
            auto_close_ms=args.auto_close_ms,
            screenshot=args.screenshot,
            screenshot_target=args.screenshot_target,
            life_role=args.life_role or "green",
        )
    return run_gui(
        smoke_test=args.smoke_test,
        auto_close_ms=args.auto_close_ms,
        screenshot=args.screenshot,
        screenshot_target=args.screenshot_target,
        preset_name=args.light_response_preset or DEFAULT_RELATION_MEMORY_PRESET,
    )


if __name__ == "__main__":
    raise SystemExit(main())
