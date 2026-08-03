"""Static Stage 8A runner responsibility boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


def runtime_sources() -> tuple[Path, ...]:
    root = (
        Path(__file__).parents[2]
        / "src"
        / "symbiotic_sim_v2"
        / "runtime"
        / "multi_session"
    )
    return tuple(sorted(root.glob("*.py")))


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_multi_session_runtime_is_gui_independent() -> None:
    modules = {
        module for path in runtime_sources() for module in imported_modules(path)
    }
    assert not any(
        module.startswith(("PySide6", "PyQt", "pyqtgraph", "symbiotic_sim_v2.gui"))
        for module in modules
    )


def test_runner_reuses_stage5c_factory_without_owning_search_or_cluster_math() -> None:
    runner_path = next(path for path in runtime_sources() if path.name == "runner.py")
    source = runner_path.read_text(encoding="utf-8")
    calls = called_names(runner_path)
    assert "create_adaptive_relation_memory_closed_loop_simulation" in source
    assert calls.isdisjoint(
        {
            "generate_candidate",
            "derive_search_direction",
            "apply_relation_memory_transition",
            "exploration_probability",
            "exploration_sigma",
            "select_dominant_cluster",
            "pattern_distance",
            "calculate_tau",
        }
    )
    assert "SimulationEngine(" not in source
    assert "GardenOutputComponent(" not in source
    assert "AdaptiveConnectedDigitalLifeComponent(" not in source


def test_hidden_truth_is_used_only_after_primary_convergence_record_exists() -> None:
    runner_path = next(path for path in runtime_sources() if path.name == "runner.py")
    tree = ast.parse(runner_path.read_text(encoding="utf-8"), filename=str(runner_path))
    truth_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "evaluate_truth_alignment"
    ]
    assert truth_calls
    assert all(
        isinstance(node.args[0], ast.Name)
        and node.args[0].id in {"record", "convergence"}
        for node in truth_calls
    )
