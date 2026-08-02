"""Command entry point for Stage 1-3 headless demos and the Stage 3 GUI."""

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
from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine
from symbiotic_sim_v2.virtual_user.config import VIRTUAL_USER_MODEL_VERSION, VirtualUserConfig
from symbiotic_sim_v2.virtual_user.diagnostics import (
    export_heartbeat_diagnostics_csv,
    full_run_rmssd_ms,
    rolling_rmssd_ms,
)
from symbiotic_sim_v2.virtual_user.scenario import create_virtual_user_simulation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Symbiotic simulator Stage 3")
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
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="exercise GUI controls and close automatically",
    )
    parser.add_argument(
        "--auto-close-ms",
        type=int,
        default=2000,
        help="GUI smoke-test auto-close delay in milliseconds",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="save a GUI screenshot after smoke actions (or shortly after launch)",
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
        "project_version": __version__,
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


def run_gui(*, smoke_test: bool, auto_close_ms: int, screenshot: Path | None) -> int:
    """Start the Qt application; smoke mode performs a bounded control sequence."""

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
    from symbiotic_sim_v2.gui.polar_h10_window import PolarH10MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    available_fonts = set(QFontDatabase.families())
    for family in (".AppleSystemUIFont", "Noto Sans", "DejaVu Sans", "Arial"):
        if family in available_fonts:
            app.setFont(QFont(family))
            break
    simulation = create_polar_h10_simulation()
    controller = SimulationController(simulation.engine)
    window = PolarH10MainWindow(controller, simulation)
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
            (550, window.run_to_end_button.click),
            (650, lambda: window.tabs.setCurrentIndex(0)),
            (725, lambda: window.tabs.setCurrentIndex(1)),
            (800, lambda: window.tabs.setCurrentIndex(2)),
            (875, lambda: window.tabs.setCurrentIndex(1)),
        )
        for delay_ms, action in actions:
            QTimer.singleShot(delay_ms, action)

        def validate_smoke() -> None:
            failures: list[str] = []
            expected_tabs = ("仮想ユーザー", "Polar H10", "時間・イベント診断")
            actual_tabs = tuple(
                window.tabs.tabText(index) for index in range(window.tabs.count())
            )
            if actual_tabs != expected_tabs:
                failures.append(f"tabs={actual_tabs!r}")
            if simulation.engine.clock.state.value != "completed":
                failures.append(f"state={simulation.engine.clock.state.value}")
            heartbeat_records = simulation.virtual_user_component.heartbeat_records()
            measurement_records = simulation.polar_h10_component.measurement_records()
            if len(heartbeat_records) != 211:
                failures.append(f"heartbeat_count={len(heartbeat_records)}")
            if len(measurement_records) != 210:
                failures.append(f"rri_count={len(measurement_records)}")
            if window.virtual_user_panel.chart.record_count != 211:
                failures.append("virtual-user chart data missing")
            if window.polar_h10_panel.chart.record_count != 210:
                failures.append("H10 comparison chart data missing")
            error_data = window.polar_h10_panel.chart.error_item.yData
            if error_data is None or len(error_data) != 210 or any(error_data):
                failures.append("H10 error chart is not the 210-point zero series")
            if window.polar_h10_panel.measurement_model.rowCount() != 210:
                failures.append("H10 table rows missing")
            event_types = {event.event_type for event in simulation.engine.executed_events()}
            if not {"heartbeat", "rri_measurement"} <= event_types:
                failures.append("timeline event types missing")
            if failures:
                print("GUI smoke failed: " + "; ".join(failures), file=sys.stderr)
                app.exit(1)

        QTimer.singleShot(1200, validate_smoke)
        QTimer.singleShot(auto_close_ms, app.quit)

    if screenshot is not None:
        screenshot.parent.mkdir(parents=True, exist_ok=True)

        def save_screenshot() -> None:
            if not window.grab().save(str(screenshot)):
                raise RuntimeError(f"failed to save screenshot: {screenshot}")

        QTimer.singleShot(1100 if smoke_test else 250, save_screenshot)

    return app.exec()


def main(argv: list[str] | None = None) -> int:
    """Parse CLI options without importing Qt on the headless path."""

    args = _build_parser().parse_args(argv)
    if args.export_virtual_user_csv is not None and not args.headless_virtual_user_demo:
        raise ValueError("--export-virtual-user-csv requires --headless-virtual-user-demo")
    if args.export_h10_csv is not None and not args.headless_h10_demo:
        raise ValueError("--export-h10-csv requires --headless-h10-demo")
    if args.headless_demo or args.headless_time_demo:
        return run_headless_demo()
    if args.headless_virtual_user_demo:
        return run_headless_virtual_user_demo(args.export_virtual_user_csv)
    if args.headless_h10_demo:
        return run_headless_h10_demo(args.export_h10_csv)
    return run_gui(
        smoke_test=args.smoke_test,
        auto_close_ms=args.auto_close_ms,
        screenshot=args.screenshot,
    )


if __name__ == "__main__":
    raise SystemExit(main())
