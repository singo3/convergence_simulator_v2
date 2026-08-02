"""Static responsibility-boundary checks for the Stage 7 response core."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from symbiotic_sim_v2.virtual_user.light_response import physiology, preference
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
)


def project_root() -> Path:
    return Path(__file__).parents[2]


def core_sources() -> tuple[Path, ...]:
    return tuple(
        sorted(
            (project_root() / "src" / "symbiotic_sim_v2" / "virtual_user" / "light_response").glob(
                "*.py"
            )
        )
    )


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_response_core_has_no_gui_or_upstream_system_logic_dependencies() -> None:
    sources = core_sources()
    assert sources
    modules = {module for path in sources for module in imported_modules(path)}
    assert not any(module.startswith(("PySide6", "pyqtgraph")) for module in modules)
    assert not any("garden.output_layer" in module for module in modules)
    assert not any("digital_life" in module for module in modules)
    assert not any(module.endswith("devices.virtual_light.component") for module in modules)
    assert not any(module.endswith("devices.virtual_light.records") for module in modules)

    combined = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    prohibited_logic = (
        "candidate",
        "k_trial",
        "adoption",
        "convergence",
        "W_anchor_session",
    )
    assert all(term not in combined for term in prohibited_logic)


def test_projection_and_pure_function_signatures_exclude_provenance() -> None:
    projection_fields = set(PhysicalLightStimulus.__dataclass_fields__)
    forbidden = {
        "qualification_holder_id",
        "source_b",
        "source_signal_index",
        "digital_life_id",
        "role",
        "q",
        "k",
        "e",
        "w",
        "g",
    }
    assert projection_fields.isdisjoint(forbidden)

    functions = (
        preference.circular_hue_distance,
        preference.evaluate_light_preference,
        preference.response_target_for,
        physiology.effective_physiology,
        physiology.calculate_light_responsive_next_rri,
    )
    for function in functions:
        parameters = set(inspect.signature(function).parameters)
        assert parameters.isdisjoint(forbidden)


def test_response_core_mentions_no_direct_rmssd_n_nd_or_w_update() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in core_sources())
    forbidden_fragments = (
        "calculate_rmssd",
        "update_rmssd",
        "calculate_n(",
        "update_n(",
        "update_nd(",
        "update_w(",
        "moving_preference",
    )
    assert all(fragment not in combined for fragment in forbidden_fragments)


def test_existing_domain_and_simulation_layers_remain_qt_free() -> None:
    root = project_root() / "src" / "symbiotic_sim_v2"
    sources = tuple((root / "domain").glob("*.py")) + tuple(
        (root / "simulation").glob("*.py")
    )
    modules = {module for path in sources for module in imported_modules(path)}
    assert not any(module.startswith(("PySide6", "pyqtgraph")) for module in modules)
