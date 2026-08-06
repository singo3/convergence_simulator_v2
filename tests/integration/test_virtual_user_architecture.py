"""Static architecture boundary tests for the Stage 2 component."""

from __future__ import annotations

import ast
from pathlib import Path

from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.virtual_user.component import VirtualUserComponent, VirtualUserSnapshot
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig


def virtual_user_sources() -> list[Path]:
    root = Path(__file__).parents[2] / "src" / "symbiotic_sim_v2" / "virtual_user"
    return sorted(root.glob("*.py"))


def imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_project_version_includes_completed_stage_08a3() -> None:
    assert __version__ == "0.14.0"


def test_virtual_user_core_does_not_import_qt() -> None:
    imports = set().union(*(imported_module_names(path) for path in virtual_user_sources()))
    assert all(not name.startswith("PySide6") for name in imports)
    assert all(not name.startswith("pyqtgraph") for name in imports)


def test_virtual_user_component_does_not_import_h10_or_garden() -> None:
    component_path = next(path for path in virtual_user_sources() if path.name == "component.py")
    imports = imported_module_names(component_path)
    assert all("h10" not in name.lower() for name in imports)
    assert all("garden" not in name.lower() for name in imports)


def test_component_and_snapshot_have_no_n_nd_or_w_state() -> None:
    component = VirtualUserComponent(VirtualUserConfig())
    component_state = set(vars(component))
    snapshot_fields = set(VirtualUserSnapshot.__dataclass_fields__)
    forbidden = {"n", "nd", "w", "rmssd", "rri_output"}
    assert component_state.isdisjoint(forbidden)
    assert snapshot_fields.isdisjoint(forbidden)


def test_no_old_simulator_import_or_reference_exists() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in virtual_user_sources())
    assert "convergence_simulator" not in source
