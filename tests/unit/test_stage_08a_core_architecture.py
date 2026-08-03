"""Static Stage 8A core ownership and non-interference boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return modules


def test_stationary_landscape_and_convergence_core_have_no_qt_dependency() -> None:
    roots = (
        PACKAGE_ROOT / "virtual_user" / "stationary_landscape",
        PACKAGE_ROOT / "convergence",
    )
    imports = set().union(
        *(imported_modules(path) for root in roots for path in root.glob("*.py"))
    )
    assert all(
        not module.startswith(("PySide6", "PyQt", "pyqtgraph", "symbiotic_sim_v2.gui"))
        for module in imports
    )


def test_primary_convergence_path_imports_no_hidden_truth_or_runtime_core() -> None:
    root = PACKAGE_ROOT / "convergence"
    primary_names = (
        "config.py",
        "records.py",
        "pattern_distance.py",
        "clustering.py",
        "evaluator.py",
    )
    imports = set().union(
        *(imported_modules(root / name) for name in primary_names)
    )
    forbidden = (
        "symbiotic_sim_v2.virtual_user.stationary_landscape",
        "symbiotic_sim_v2.digital_life",
        "symbiotic_sim_v2.garden",
        "symbiotic_sim_v2.runtime",
    )
    assert all(not module.startswith(forbidden) for module in imports)
    source = "\n".join((root / name).read_text(encoding="utf-8") for name in primary_names)
    assert all(
        token not in source
        for token in (
            "preference_peak",
            "peak_weight",
            "hidden_optimum",
            "preference_match_at_medoid",
            "DigitalLifeComponent",
            "GardenOutputComponent",
        )
    )


def test_only_truth_alignment_module_reads_the_stationary_landscape() -> None:
    root = PACKAGE_ROOT / "convergence"
    consumers = {
        path.name
        for path in root.glob("*.py")
        if any(
            module.startswith("symbiotic_sim_v2.virtual_user.stationary_landscape")
            for module in imported_modules(path)
        )
    }
    assert consumers == {"truth_alignment.py"}
