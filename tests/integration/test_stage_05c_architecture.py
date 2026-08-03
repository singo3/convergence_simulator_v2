"""Static ownership boundaries for Stage 5C relation-memory adaptation."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from symbiotic_sim_v2.runtime.adaptive_closed_loop.relation_memory_scenario import (
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.closed_loop.light_responsive_scenario import (
    create_light_responsive_closed_loop_simulation,
)


def package_root() -> Path:
    return Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(parsed(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def python_sources(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


def relation_pure_sources() -> tuple[Path, ...]:
    root = package_root() / "digital_life" / "relation_memory"
    return tuple(
        root / name
        for name in (
            "config.py",
            "reflect.py",
            "intrinsic.py",
            "direction.py",
            "candidate.py",
            "persistent_state.py",
            "session_state.py",
            "records.py",
            "transitions.py",
        )
    )


def test_pure_relation_core_has_no_gui_upstream_device_or_preference_dependency() -> None:
    imports = set().union(*(imported_modules(path) for path in relation_pure_sources()))
    forbidden_prefixes = (
        "PySide6",
        "PyQt",
        "pyqtgraph",
        "symbiotic_sim_v2.gui",
        "symbiotic_sim_v2.virtual_user",
        "symbiotic_sim_v2.devices",
        "symbiotic_sim_v2.garden",
        "symbiotic_sim_v2.runtime",
    )
    assert all(not module.startswith(forbidden_prefixes) for module in imports)

    combined = "\n".join(path.read_text(encoding="utf-8") for path in relation_pure_sources())
    assert all(
        token not in combined
        for token in (
            "VirtualUserComponent",
            "PolarH10Component",
            "GardenInputComponent",
            "GardenOutputComponent",
            "LightResponseConfig",
            "preferred_hue",
            "preferred_bpm",
            "digital_life_components",
            "other_life",
        )
    )


def test_adaptive_component_consumes_formal_events_not_component_internals() -> None:
    path = package_root() / "digital_life" / "relation_memory" / "adaptive_component.py"
    imports = imported_modules(path)
    assert "symbiotic_sim_v2.garden.output_layer.events" in imports
    assert all(
        not module.startswith(
            (
                "symbiotic_sim_v2.virtual_user",
                "symbiotic_sim_v2.devices.polar_h10",
                "symbiotic_sim_v2.garden.input_layer",
                "symbiotic_sim_v2.garden.output_layer.component",
                "symbiotic_sim_v2.garden.output_layer.records",
                "symbiotic_sim_v2.runtime",
            )
        )
        for module in imports
    )
    source = path.read_text(encoding="utf-8").casefold()
    assert all(
        token not in source
        for token in (
            "rmssd",
            "raw_rri",
            "preference_match",
            "preferred_hue",
            "preferred_blink",
            "other_life",
            "digital_life_components",
        )
    )


def test_candidate_algorithm_exists_only_inside_each_life_relation_core() -> None:
    runtime_roots = (
        package_root() / "runtime" / "adaptive_closed_loop",
        package_root() / "runtime" / "multi_life",
        package_root() / "garden" / "output_layer",
    )
    non_life_source = "\n".join(
        path.read_text(encoding="utf-8")
        for root in runtime_roots
        for path in python_sources(root)
    )
    assert all(
        token not in non_life_source
        for token in (
            "generate_candidate",
            "derive_search_direction",
            "apply_relation_memory_transition",
            "exploration_decision(",
            "reflect01(",
            "candidate_selector",
            "central_candidate",
        )
    )

    adaptive_path = (
        package_root()
        / "digital_life"
        / "relation_memory"
        / "adaptive_component.py"
    )
    assert "apply_relation_memory_transition" in adaptive_path.read_text(
        encoding="utf-8"
    )


def test_candidate_generation_reflects_only_f_t_without_rounding_or_cell_mapping() -> None:
    candidate_path = package_root() / "digital_life" / "relation_memory" / "candidate.py"
    tree = parsed(candidate_path)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    source = candidate_path.read_text(encoding="utf-8").casefold()
    assert "reflect01" in called_names
    assert "round" not in called_names
    assert "clip01" not in called_names
    assert "25" not in source
    assert "cell_index" not in source
    assert "grid_index" not in source


def test_stage5c_factory_layers_over_stage7_without_reassembling_the_engine() -> None:
    path = (
        package_root()
        / "runtime"
        / "adaptive_closed_loop"
        / "relation_memory_scenario.py"
    )
    source = path.read_text(encoding="utf-8")
    assert "_create_light_responsive_closed_loop_simulation" in source
    assert "SimulationEngine(" not in source
    assert "GardenInputComponent(" not in source
    assert "GardenOutputComponent(" not in source
    assert "GardenLightMapperComponent(" not in source
    assert "VirtualLightDeviceComponent(" not in source
    assert "LightResponsiveVirtualUserComponent(" not in source

    adaptive_parameters = set(
        inspect.signature(
            create_adaptive_relation_memory_closed_loop_simulation
        ).parameters
    )
    legacy_parameters = set(
        inspect.signature(create_light_responsive_closed_loop_simulation).parameters
    )
    assert "initial_persistent_states_by_life_id" in adaptive_parameters
    assert "initial_persistent_states_by_life_id" not in legacy_parameters
    assert "digital_life_component_factory" not in legacy_parameters


def test_stage5c_sources_have_no_future_search_runner_ml_or_old_simulator_import() -> None:
    roots = (
        package_root() / "digital_life" / "relation_memory",
        package_root() / "runtime" / "adaptive_closed_loop",
    )
    imports = set().union(
        *(imported_modules(path) for root in roots for path in python_sources(root))
    )
    assert all(
        not module.startswith(
            (
                "numpy",
                "sklearn",
                "tensorflow",
                "torch",
                "convergence_simulator",
            )
        )
        for module in imports
    )
    assert all("old_simulator" not in module for module in imports)

    adaptive_factory = (
        package_root()
        / "runtime"
        / "adaptive_closed_loop"
        / "relation_memory_scenario.py"
    ).read_text(encoding="utf-8").casefold()
    assert "monte_carlo" not in adaptive_factory
    assert "convergence" not in adaptive_factory
    assert "multi_session" not in adaptive_factory
