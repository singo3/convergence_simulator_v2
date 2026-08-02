"""Static responsibility-boundary tests for the Stage 3 device core."""

from __future__ import annotations

import ast
from pathlib import Path

from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.devices.polar_h10.component import (
    PolarH10Component,
    PolarH10Snapshot,
)
from symbiotic_sim_v2.devices.polar_h10.config import PolarH10Config
from symbiotic_sim_v2.devices.polar_h10.records import RriMeasurementRecord
from symbiotic_sim_v2.domain.event_priorities import (
    HEARTBEAT_EVENT_PRIORITY,
    RRI_MEASUREMENT_EVENT_PRIORITY,
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_sources import (
    POLAR_H10_EVENT_SOURCE,
    VIRTUAL_USER_EVENT_SOURCE,
)
from symbiotic_sim_v2.domain.event_types import (
    HEARTBEAT_EVENT_TYPE,
    RRI_MEASUREMENT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)


def project_package_root() -> Path:
    return Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"


def h10_sources() -> tuple[Path, ...]:
    return tuple(sorted((project_package_root() / "devices" / "polar_h10").glob("*.py")))


def imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def referenced_identifier_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)}
    names.update(node.attr.lower() for node in ast.walk(tree) if isinstance(node, ast.Attribute))
    return names


def test_project_version_is_stage3() -> None:
    assert __version__ == "0.3.0"


def test_device_core_has_no_qt_or_pyqtgraph_imports() -> None:
    imports = set().union(*(imported_module_names(path) for path in h10_sources()))
    assert all(not name.startswith("PySide6") for name in imports)
    assert all(not name.startswith("pyqtgraph") for name in imports)


def test_h10_component_imports_only_formal_events_not_virtual_user_internals() -> None:
    component_path = project_package_root() / "devices" / "polar_h10" / "component.py"
    imports = imported_module_names(component_path)
    assert all(not name.startswith("symbiotic_sim_v2.virtual_user") for name in imports)
    assert all("garden" not in name.lower() for name in imports)
    assert all("random" not in name.lower() for name in imports)
    source = component_path.read_text(encoding="utf-8")
    assert "VirtualUserComponent" not in source
    assert "HeartbeatRecord" not in source
    assert "true_rri" not in source.lower()


def test_only_the_development_diagnostics_adapter_imports_heartbeat_record() -> None:
    importing_files = {
        path.name
        for path in h10_sources()
        if "symbiotic_sim_v2.virtual_user.diagnostics" in imported_module_names(path)
    }
    assert importing_files == {"diagnostics.py"}


def test_component_records_snapshots_and_config_have_no_garden_or_hrv_state() -> None:
    component = PolarH10Component(PolarH10Config())
    component_fields = {name.removeprefix("_").lower() for name in vars(component)}
    snapshot_fields = {name.lower() for name in PolarH10Snapshot.__dataclass_fields__}
    record_fields = {name.lower() for name in RriMeasurementRecord.__dataclass_fields__}
    config_fields = {name.lower() for name in PolarH10Config.__dataclass_fields__}
    forbidden = {
        "rmssd",
        "n",
        "n_baseline",
        "n_baseline_session",
        "nd",
        "w",
        "artifact",
        "evaluation_quality",
        "baseline",
        "bundle",
        "session_signal",
        "root_seed",
        "noise",
        "latency",
        "packet_loss",
        "min_rri_ms",
        "max_rri_ms",
    }
    assert component_fields.isdisjoint(forbidden)
    assert snapshot_fields.isdisjoint(forbidden)
    assert record_fields.isdisjoint(forbidden)
    assert config_fields.isdisjoint(forbidden)

    core_files = (
        project_package_root() / "devices" / "polar_h10" / "config.py",
        project_package_root() / "devices" / "polar_h10" / "records.py",
        project_package_root() / "devices" / "polar_h10" / "component.py",
    )
    identifiers = set().union(*(referenced_identifier_names(path) for path in core_files))
    assert identifiers.isdisjoint({"rmssd", "n", "nd", "w", "artifact"})


def test_formal_event_names_sources_and_priorities_are_centralized_and_exact() -> None:
    assert HEARTBEAT_EVENT_TYPE == "heartbeat"
    assert RRI_MEASUREMENT_EVENT_TYPE == "rri_measurement"
    assert SIMULATION_COMPLETE_EVENT_TYPE == "simulation_complete"
    assert VIRTUAL_USER_EVENT_SOURCE == "virtual_user"
    assert POLAR_H10_EVENT_SOURCE == "polar_h10"
    assert HEARTBEAT_EVENT_PRIORITY == 40
    assert RRI_MEASUREMENT_EVENT_PRIORITY == 50
    assert SIMULATION_COMPLETE_EVENT_PRIORITY == 100
    assert (
        HEARTBEAT_EVENT_PRIORITY
        < RRI_MEASUREMENT_EVENT_PRIORITY
        < SIMULATION_COMPLETE_EVENT_PRIORITY
    )


def test_no_old_simulator_import_or_reference_exists_in_stage3_sources() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in h10_sources())
    assert "convergence_simulator" not in source


def test_garden_input_layer_has_not_been_implemented_in_stage3() -> None:
    package_root = project_package_root()
    assert not (package_root / "garden").exists()
    assert not any("garden" in path.name.lower() for path in package_root.rglob("*.py"))
