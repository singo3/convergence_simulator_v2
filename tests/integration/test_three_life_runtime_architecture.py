"""Static Stage 5B Runtime responsibility-boundary checks."""

from __future__ import annotations

import ast
from pathlib import Path


def runtime_root() -> Path:
    return (
        Path(__file__).parents[2]
        / "src"
        / "symbiotic_sim_v2"
        / "runtime"
        / "multi_life"
    )


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_runtime_core_has_no_qt_or_pyqtgraph_dependency() -> None:
    modules = set().union(
        *(imported_modules(path) for path in runtime_root().glob("*.py"))
    )
    assert all(not name.startswith(("PySide6", "PyQt", "pyqtgraph")) for name in modules)


def test_coordinator_does_not_read_tau_or_import_p_v_calculations() -> None:
    path = runtime_root() / "coordinator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    attributes = {
        node.attr.lower() for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    names = {node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)}
    modules = imported_modules(path)

    assert "tau" not in attributes
    assert {"calculate_p", "calculate_v", "calculate_tau", "winner", "rank"}.isdisjoint(
        names
    )
    assert all(not module.endswith(("intrinsic", "math")) for module in modules)


def test_coordinator_schedules_each_intent_in_canonical_id_loop() -> None:
    path = runtime_root() / "coordinator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    schedule_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "schedule_touch_intent"
    ]
    assert len(schedule_calls) == 1
    call = schedule_calls[0]
    assert isinstance(call.args[1], ast.Name)
    assert call.args[1].id == "intent"


def test_runtime_never_constructs_or_emits_qualified_b() -> None:
    path = runtime_root() / "coordinator.py"
    source = path.read_text(encoding="utf-8").lower()

    assert "garden_qualified_b" not in source
    assert "qualified_b_emission" not in source
