"""Command entry point for Stage 1/2 headless demos and the Stage 2 GUI."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine
from symbiotic_sim_v2.virtual_user.config import VIRTUAL_USER_MODEL_VERSION, VirtualUserConfig
from symbiotic_sim_v2.virtual_user.diagnostics import (
    export_heartbeat_diagnostics_csv,
    full_run_rmssd_ms,
    rolling_rmssd_ms,
)
from symbiotic_sim_v2.virtual_user.scenario import create_virtual_user_simulation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Symbiotic simulator Stage 2")
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
    from symbiotic_sim_v2.gui.virtual_user_window import VirtualUserMainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    available_fonts = set(QFontDatabase.families())
    for family in (".AppleSystemUIFont", "Noto Sans", "DejaVu Sans", "Arial"):
        if family in available_fonts:
            app.setFont(QFont(family))
            break
    simulation = create_virtual_user_simulation()
    controller = SimulationController(simulation.engine)
    window = VirtualUserMainWindow(controller, simulation)
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
            (650, lambda: window.tabs.setCurrentIndex(1)),
            (750, lambda: window.tabs.setCurrentIndex(0)),
        )
        for delay_ms, action in actions:
            QTimer.singleShot(delay_ms, action)
        QTimer.singleShot(auto_close_ms, app.quit)

    if screenshot is not None:
        screenshot.parent.mkdir(parents=True, exist_ok=True)

        def save_screenshot() -> None:
            if not window.grab().save(str(screenshot)):
                raise RuntimeError(f"failed to save screenshot: {screenshot}")

        QTimer.singleShot(900 if smoke_test else 250, save_screenshot)

    return app.exec()


def main(argv: list[str] | None = None) -> int:
    """Parse CLI options without importing Qt on the headless path."""

    args = _build_parser().parse_args(argv)
    if args.headless_demo or args.headless_time_demo:
        return run_headless_demo()
    if args.headless_virtual_user_demo:
        return run_headless_virtual_user_demo(args.export_virtual_user_csv)
    if args.export_virtual_user_csv is not None:
        raise ValueError("--export-virtual-user-csv requires --headless-virtual-user-demo")
    return run_gui(
        smoke_test=args.smoke_test,
        auto_close_ms=args.auto_close_ms,
        screenshot=args.screenshot,
    )


if __name__ == "__main__":
    raise SystemExit(main())
