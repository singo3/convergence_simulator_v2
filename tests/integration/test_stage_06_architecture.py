"""Static and runtime Stage 6 responsibility-boundary checks."""

from __future__ import annotations

import ast
from pathlib import Path

from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    create_light_feedback_simulation,
)


def package_root() -> Path:
    return Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"


def python_sources(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def all_imports(root: Path) -> set[str]:
    return set().union(*(imported_modules(path) for path in python_sources(root)))


def test_mapper_and_virtual_device_cores_have_no_qt_or_gui_dependency() -> None:
    roots = (
        package_root() / "garden" / "light_mapper",
        package_root() / "devices" / "virtual_light",
        package_root() / "runtime" / "light_simulation",
    )
    imports = set().union(*(all_imports(root) for root in roots))
    assert all(
        not module.startswith(("PySide6", "PyQt", "pyqtgraph", "symbiotic_sim_v2.gui"))
        for module in imports
    )


def test_mapper_uses_only_the_formal_qb_parser_not_upstream_components_or_life_state() -> None:
    root = package_root() / "garden" / "light_mapper"
    imports = all_imports(root)
    assert all(
        not module.startswith("symbiotic_sim_v2.digital_life") for module in imports
    )
    assert "symbiotic_sim_v2.garden.output_layer.component" not in imports
    assert "symbiotic_sim_v2.garden.output_layer.records" not in imports
    component_source = (root / "component.py").read_text(encoding="utf-8")
    assert "parse_garden_qualified_b_event" in component_source
    assert "event.payload[" not in component_source
    forbidden = {
        "GardenOutputComponent",
        "DigitalLifeComponent",
        "ConnectedDigitalLifeComponent",
        "p_intrinsic",
        "touch_order",
        "rmssd",
        "rri",
        "candidate",
        "trial",
        "adoption",
    }
    combined = "\n".join(path.read_text(encoding="utf-8") for path in python_sources(root))
    assert all(token not in combined for token in forbidden)


def test_virtual_device_depends_only_on_light_command_not_garden_or_life_components() -> None:
    root = package_root() / "devices" / "virtual_light"
    imports = all_imports(root)
    assert all(
        not module.startswith(
            (
                "symbiotic_sim_v2.digital_life",
                "symbiotic_sim_v2.garden.output_layer",
                "symbiotic_sim_v2.virtual_user",
                "symbiotic_sim_v2.runtime.multi_life",
            )
        )
        for module in imports
    )
    component_source = (root / "component.py").read_text(encoding="utf-8")
    assert "parse_light_command_event" in component_source
    assert "QTimer" not in component_source
    assert "perf_counter" not in component_source
    assert "time.time" not in component_source
    assert "state_at" in component_source


def test_stage6_is_a_new_wrapper_and_stage5b1_factory_has_no_light_handlers() -> None:
    stage6 = package_root() / "runtime" / "light_simulation" / "scenario.py"
    stage5b = package_root() / "runtime" / "multi_life" / "scenario.py"
    stage6_source = stage6.read_text(encoding="utf-8")
    stage5b_imports = imported_modules(stage5b)
    assert "create_three_digital_life_competition_simulation" in stage6_source
    assert "GARDEN_QUALIFIED_B_EVENT_TYPE" in stage6_source
    assert "LIGHT_COMMAND_EVENT_TYPE" in stage6_source
    assert all("light_mapper" not in module for module in stage5b_imports)
    assert all("virtual_light" not in module for module in stage5b_imports)


def test_fixed_grid_is_post_run_diagnostic_and_never_an_engine_event() -> None:
    simulation = create_light_feedback_simulation()
    simulation.engine.run_until_end()
    event_types = {event.event_type for event in simulation.engine.executed_events()}
    assert len(simulation.engine.executed_events()) == 3_287
    assert "light_waveform_sample" not in event_types
    assert "light_frame" not in event_types
    assert len(simulation.device.waveform_samples()) == 12_001
    assert len(simulation.engine.executed_events()) == 3_287


def test_stage6_has_no_virtual_user_light_response_or_stage5c_exploration() -> None:
    user_root = package_root() / "virtual_user"
    user_source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in python_sources(user_root)
    )
    assert "light_stimulus_state" not in user_source
    assert "handle_light" not in user_source
    assert not (user_root / "light_response.py").exists()

    stage6_roots = (
        package_root() / "garden" / "light_mapper",
        package_root() / "devices" / "virtual_light",
        package_root() / "runtime" / "light_simulation",
    )
    source = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for root in stage6_roots
        for path in python_sources(root)
    )
    for forbidden in (
        "k_trial",
        "p_explore",
        "epsilon_accept",
        "accepted_candidate",
        "exploration_decision",
        "adoption_result",
        "rollback",
        "virtual_user_light_response",
        "convergence_simulator",
    ):
        assert forbidden not in source


def test_formal_state_boundary_contains_no_gui_rgb_or_upstream_physiology() -> None:
    simulation = create_light_feedback_simulation()
    simulation.engine.run_until_end()
    event = next(
        event
        for event in simulation.engine.executed_events()
        if event.event_type == "light_stimulus_state"
    )
    fields = {field.casefold() for field in event.payload}
    assert fields.isdisjoint(
        {
            "rgb",
            "qcolor",
            "pixel",
            "rri",
            "rmssd",
            "n",
            "nd",
            "w",
            "p",
            "v",
            "tau",
            "e",
            "q",
            "k",
            "g",
            "touch_order",
            "evaluation_result",
        }
    )
