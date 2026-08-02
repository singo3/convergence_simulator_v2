"""Command entry point for Stage 1-5B headless demos and the Stage 5B GUI."""

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
from symbiotic_sim_v2.garden.output_layer.config import (
    DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
    GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION,
    GARDEN_OUTPUT_MODEL_VERSION,
    GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION,
    GARDEN_QUALIFIED_B_SCHEMA_VERSION,
)
from symbiotic_sim_v2.garden.output_layer.diagnostics import (
    export_garden_output_diagnostics,
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
from symbiotic_sim_v2.virtual_user.scenario import create_virtual_user_simulation

DOCUMENT_VERSION = "v2.0"
PROFILE_VERSION = "symbiotic_signal_loop_reference_v1_0"
STAGE_3_HEADLESS_PROJECT_VERSION = "0.3.0"
STAGE_4_HEADLESS_PROJECT_VERSION = "0.4.0"
STAGE_5A_HEADLESS_PROJECT_VERSION = "0.5.0"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Symbiotic simulator Stage 5B")
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
        help="run the 240-second Stage 5B three-life competition and second round",
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
        default=4500,
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
        ),
        default="window",
        help="capture the selected Stage 5A/5B diagnostic view",
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
    life_ids = tuple(sorted(simulation.digital_life_components))
    life_snapshots = {
        life_id: simulation.digital_life_components[life_id].snapshot()
        for life_id in life_ids
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
        "project_version": __version__,
        "document_version": DOCUMENT_VERSION,
        "profile_version": PROFILE_VERSION,
        "algorithm_version": ALGORITHM_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "runtime_model_version": THREE_DIGITAL_LIFE_RUNTIME_MODEL_VERSION,
        "garden_output_model_version": GARDEN_OUTPUT_MODEL_VERSION,
        "qualification_state_schema_version": (
            GARDEN_QUALIFICATION_STATE_SCHEMA_VERSION
        ),
        "tau_delivery_policy_version": TAU_TOUCH_DELIVERY_POLICY_VERSION,
        "event_schema_versions": {
            "touch": DIGITAL_LIFE_TOUCH_SCHEMA_VERSION,
            "interoceptive_feedback": (
                GARDEN_INTEROCEPTIVE_FEEDBACK_SCHEMA_VERSION
            ),
            "qualified_b": GARDEN_QUALIFIED_B_SCHEMA_VERSION,
            "second_round_record": (
                DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION
            ),
        },
        "final_virtual_time_us": simulation.engine.clock.current_time_us,
        "final_state": simulation.engine.clock.state.value,
        "executed_event_count": len(simulation.engine.executed_events()),
        "garden_signal_count": len(
            simulation.garden_input_component.signal_records()
        ),
        "touch_count": len(touch_records),
        "feedback_count": len(feedback_records),
        "qualified_b_output_count": len(qualified_b_records),
        "active_output_count": garden_snapshot.active_output_count,
        "inactive_output_count": garden_snapshot.inactive_output_count,
        "assignment_count": garden_snapshot.assignment_count,
        "release_count": garden_snapshot.release_count,
        "qualification_holder_id_during_session": (
            garden_snapshot.last_assigned_holder_id
        ),
        "final_qualification_holder_id": (
            garden_snapshot.qualification_holder_id
        ),
        "holder_assignment_signal_index": assignment_signal_index,
        "holder_assignment_time_us": (
            garden_snapshot.qualification_assignment_time_us
        ),
        "touch_count_by_life": touch_count_by_life,
        "first_touch_order": first_touch_order,
        "per_life": per_life,
        "per_life_first_round_count": {
            life_id: snapshot.first_round_count
            for life_id, snapshot in life_snapshots.items()
        },
        "per_life_second_round_count": {
            life_id: snapshot.second_round_count
            for life_id, snapshot in life_snapshots.items()
        },
        "per_life_final_E": {
            life_id: snapshot.e for life_id, snapshot in life_snapshots.items()
        },
        "per_life_final_q": {
            life_id: snapshot.q for life_id, snapshot in life_snapshots.items()
        },
        "per_life_final_G": {
            life_id: snapshot.current_g
            for life_id, snapshot in life_snapshots.items()
        },
        "per_life_final_k": {
            life_id: snapshot.k_current
            for life_id, snapshot in life_snapshots.items()
        },
        "per_life_q_update_count": {
            life_id: snapshot.q_update_count
            for life_id, snapshot in life_snapshots.items()
        },
        "k_update_count": sum(
            snapshot.k_update_count for snapshot in life_snapshots.values()
        ),
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
                failures.append(
                    f"life_evaluation_count={len(life.evaluation_update_records())}"
                )
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
            target = (
                window
                if screenshot_target == "window"
                else window.digital_life_panel.chart
            )
            if not target.grab().save(str(screenshot)):
                raise RuntimeError(f"failed to save screenshot: {screenshot}")

        screenshot_delay_ms = (
            min(2200, max(1500, auto_close_ms - 100)) if smoke_test else 250
        )
        QTimer.singleShot(screenshot_delay_ms, save_screenshot)

    return app.exec()


def run_gui(
    *,
    smoke_test: bool,
    auto_close_ms: int,
    screenshot: Path | None,
    screenshot_target: str = "window",
) -> int:
    """Start the Stage 5B six-tab GUI over the shared production factory."""

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
    from symbiotic_sim_v2.gui.three_life_window import ThreeDigitalLifeMainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    available_fonts = set(QFontDatabase.families())
    for family in (".AppleSystemUIFont", "Noto Sans", "DejaVu Sans", "Arial"):
        if family in available_fonts:
            app.setFont(QFont(family))
            break
    simulation = create_three_digital_life_competition_simulation()
    controller = SimulationController(simulation.engine)
    window = ThreeDigitalLifeMainWindow(controller, simulation)
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
                "3生命・資格競争",
                "Garden出力資格層",
                "Garden入力層",
                "仮想ユーザー",
                "Polar H10",
                "時間・イベント診断",
            )
            actual_tabs = tuple(
                window.tabs.tabText(index) for index in range(window.tabs.count())
            )
            if actual_tabs != expected_tabs:
                failures.append(f"tabs={actual_tabs!r}")
            active = window.simulation
            if active.engine.clock.state.value != "completed":
                failures.append(f"state={active.engine.clock.state.value}")
            if len(active.virtual_user_component.heartbeat_records()) != 280:
                failures.append("heartbeat count")
            if len(active.polar_h10_component.measurement_records()) != 279:
                failures.append("RRI count")
            if len(active.garden_input_component.signal_records()) != 241:
                failures.append("Garden signal count")
            garden_snapshot = active.garden_output_component.snapshot()
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
            for life_id, component in active.digital_life_components.items():
                snapshot = component.snapshot()
                if (
                    snapshot.first_round_count != 241
                    or snapshot.second_round_count != 241
                    or snapshot.touch_dispatched_count != 180
                    or snapshot.current_g != 0
                    or snapshot.k_update_count != 0
                ):
                    failures.append(f"life={life_id}:{snapshot!r}")
            green = active.green_life_component.snapshot()
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
                or output_panel.qualification_model.rowCount() != 241
            ):
                failures.append("Garden output chart/table data")
            if window.virtual_user_panel.chart.record_count != 280:
                failures.append("Virtual User chart")
            if window.polar_h10_panel.chart.record_count != 279:
                failures.append("H10 chart")
            if window.garden_input_panel.chart.signal_count != 241:
                failures.append("Garden input chart")
            event_types = {event.event_type for event in active.engine.executed_events()}
            required_types = {
                "digital_life_touch",
                "garden_qualified_b",
                "garden_interoceptive_feedback",
                "garden_holder_release",
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
            targets = {
                "window": window,
                "three-life-overview": window,
                "touch-holder-second-round": (
                    window.multi_life_panel.chart_table_splitter
                ),
                "garden-output-qualified-b": (
                    window.garden_output_panel.diagnostics_content
                ),
            }
            if screenshot_target == "garden-output-qualified-b":
                window.tabs.setCurrentWidget(window.garden_output_panel)
            elif screenshot_target in {
                "three-life-overview",
                "touch-holder-second-round",
            }:
                window.tabs.setCurrentWidget(window.multi_life_panel)
            target = targets.get(screenshot_target, window)
            if not target.grab().save(str(screenshot)):
                raise RuntimeError(f"failed to save screenshot: {screenshot}")

        screenshot_delay_ms = max(1_500, auto_close_ms - 100) if smoke_test else 250
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
            "--export-three-life-competition-csv requires "
            "--headless-three-life-competition-demo"
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
        return run_headless_three_life_competition_demo(
            args.export_three_life_competition_csv
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
    )


if __name__ == "__main__":
    raise SystemExit(main())
