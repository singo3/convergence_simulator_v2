"""Command-line entry point for GUI, headless demo, and bounded GUI smoke runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage 1 deterministic time simulator")
    parser.add_argument(
        "--headless-demo",
        action="store_true",
        help="run the diagnostic scenario without importing or starting Qt",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="exercise GUI controls and close automatically",
    )
    parser.add_argument(
        "--auto-close-ms",
        type=int,
        default=1500,
        help="GUI smoke-test auto-close delay in milliseconds",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="save a GUI screenshot after smoke actions (or shortly after launch)",
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
    from symbiotic_sim_v2.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    available_fonts = set(QFontDatabase.families())
    for family in (".AppleSystemUIFont", "Noto Sans", "DejaVu Sans", "Arial"):
        if family in available_fonts:
            app.setFont(QFont(family))
            break
    engine = create_demo_engine()
    controller = SimulationController(engine)
    window = MainWindow(controller)
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
        )
        for delay_ms, action in actions:
            QTimer.singleShot(delay_ms, action)
        QTimer.singleShot(auto_close_ms, app.quit)

    if screenshot is not None:
        screenshot.parent.mkdir(parents=True, exist_ok=True)

        def save_screenshot() -> None:
            if not window.grab().save(str(screenshot)):
                raise RuntimeError(f"failed to save screenshot: {screenshot}")

        QTimer.singleShot(700 if smoke_test else 250, save_screenshot)

    return app.exec()


def main(argv: list[str] | None = None) -> int:
    """Parse CLI options without importing Qt on the headless path."""

    args = _build_parser().parse_args(argv)
    if args.headless_demo:
        return run_headless_demo()
    return run_gui(
        smoke_test=args.smoke_test,
        auto_close_ms=args.auto_close_ms,
        screenshot=args.screenshot,
    )


if __name__ == "__main__":
    raise SystemExit(main())
