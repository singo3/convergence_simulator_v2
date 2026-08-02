"""Static Stage 4 Garden input responsibility-boundary tests."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from symbiotic_sim_v2.garden.input_layer.normalization import normalize_rmssd_to_n


def package_root() -> Path:
    return Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"


def garden_core_sources() -> tuple[Path, ...]:
    root = package_root() / "garden" / "input_layer"
    core_names = (
        "config.py",
        "phases.py",
        "timing.py",
        "artifact_filter.py",
        "rmssd.py",
        "normalization.py",
        "records.py",
        "component.py",
        "diagnostics.py",
    )
    return tuple(root / name for name in core_names)


def imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_garden_input_core_has_no_qt_or_pyqtgraph_imports() -> None:
    imports = set().union(*(imported_module_names(path) for path in garden_core_sources()))

    assert all(not name.startswith(("PySide6", "PyQt", "pyqtgraph")) for name in imports)


def test_component_consumes_formal_rri_events_without_upstream_component_internals() -> None:
    component_path = package_root() / "garden" / "input_layer" / "component.py"
    source = component_path.read_text(encoding="utf-8")
    imports = imported_module_names(component_path)

    assert all(not name.startswith("symbiotic_sim_v2.virtual_user") for name in imports)
    assert all(not name.startswith("symbiotic_sim_v2.devices.polar_h10") for name in imports)
    assert "VirtualUserComponent" not in source
    assert "HeartbeatRecord" not in source
    assert "PolarH10Component" not in source
    assert "RriMeasurementRecord" not in source


def test_garden_input_core_has_no_digital_life_nd_or_w_implementation() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in garden_core_sources())
    garden_files = tuple((package_root() / "garden").rglob("*.py"))

    assert "DigitalLife" not in source
    assert all(path.stem.lower() not in {"digital_life", "nd", "w"} for path in garden_files)


def test_normalization_signature_has_no_baseline_or_reference_input() -> None:
    parameters = set(inspect.signature(normalize_rmssd_to_n).parameters)

    assert parameters == {"rmssd_ms", "rmssd_min_ms", "rmssd_max_ms"}
    assert all("baseline" not in name.lower() for name in parameters)


def test_no_old_convergence_simulator_import_exists_in_stage4_sources() -> None:
    imports = set().union(*(imported_module_names(path) for path in garden_core_sources()))

    assert all("convergence_simulator" not in name for name in imports)
