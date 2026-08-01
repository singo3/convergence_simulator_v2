"""End-to-end assertions for the 20-second Stage 1 diagnostic scenario."""

from __future__ import annotations

import json
import subprocess
import sys

from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine


def test_demo_has_expected_events_and_final_time() -> None:
    engine = create_demo_engine()
    assert len(engine.planned_events()) == 26
    engine.run_until_end()
    events = engine.executed_events()
    assert len(events) == 26
    assert engine.clock.current_time_us == 20_000_000


def test_demo_markers_and_same_time_order() -> None:
    engine = create_demo_engine()
    engine.run_until_end()
    events = engine.executed_events()
    at_2_5 = [event.event_type for event in events if event.scheduled_time_us == 2_500_000]
    at_7_3 = [event.event_type for event in events if event.scheduled_time_us == 7_300_000]
    at_12_75 = [event.event_type for event in events if event.scheduled_time_us == 12_750_000]
    at_20 = [event.event_type for event in events if event.scheduled_time_us == 20_000_000]
    assert at_2_5 == ["demo_marker"]
    assert at_7_3 == ["demo_same_time_a", "demo_same_time_b"]
    assert at_12_75 == ["demo_marker"]
    assert at_20 == ["clock_tick", "simulation_complete"]


def test_headless_module_output_matches_engine_digest() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "symbiotic_sim_v2", "--headless-demo"],
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)
    engine = create_demo_engine()
    engine.run_until_end()
    assert output["executed_event_count"] == 26
    assert output["final_virtual_time_us"] == 20_000_000
    assert output["deterministic_digest"] == engine.deterministic_digest()


def test_core_source_does_not_import_qt() -> None:
    from pathlib import Path

    package_root = Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"
    core_files = [
        *package_root.joinpath("domain").glob("*.py"),
        *package_root.joinpath("simulation").glob("*.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in core_files)
    assert "PySide6" not in source
    assert "pyqtgraph" not in source.lower()
