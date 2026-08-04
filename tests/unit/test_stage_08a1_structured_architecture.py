"""Static non-interference boundaries for new Stage 8A.1 diagnostic cores."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from symbiotic_sim_v2.convergence.structured import evaluate_life_dominance
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    evaluate_stationary_preference_v2,
)

PACKAGE_ROOT = Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    result.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    return result


def test_v2_landscape_and_structured_convergence_are_qt_free() -> None:
    roots = (
        PACKAGE_ROOT / "virtual_user" / "stationary_landscape_v2",
        PACKAGE_ROOT / "convergence" / "structured",
    )
    imports = set().union(*(imported_modules(path) for root in roots for path in root.glob("*.py")))
    assert all(
        not module.startswith(("PySide6", "PyQt", "pyqtgraph", "symbiotic_sim_v2.gui"))
        for module in imports
    )


def test_observable_structured_path_imports_no_hidden_truth_or_system_core() -> None:
    root = PACKAGE_ROOT / "convergence" / "structured"
    primary_names = (
        "config.py",
        "records.py",
        "life_dominance.py",
        "bpm_common.py",
        "multi_attractor.py",
        "mechanical_rotation.py",
        "classification.py",
        "evaluator.py",
    )
    imports = set().union(*(imported_modules(root / name) for name in primary_names))
    forbidden = (
        "symbiotic_sim_v2.virtual_user.stationary_landscape_v2",
        "symbiotic_sim_v2.digital_life",
        "symbiotic_sim_v2.garden",
        "symbiotic_sim_v2.runtime",
    )
    assert all(not module.startswith(forbidden) for module in imports)
    assert {
        path.name
        for path in root.glob("*.py")
        if any(
            module.startswith("symbiotic_sim_v2.virtual_user.stationary_landscape_v2")
            for module in imported_modules(path)
        )
    } == {"truth_alignment.py"}


def test_primary_signatures_have_no_hidden_preference_or_core_mutation_inputs() -> None:
    life_parameters = set(inspect.signature(evaluate_life_dominance).parameters)
    assert life_parameters == {
        "valid_observations",
        "config",
        "first_confirmed_session_index",
    }
    preference_parameters = set(inspect.signature(evaluate_stationary_preference_v2).parameters)
    assert preference_parameters == {"profile", "active", "hue_degree", "blink_bpm"}
    forbidden = {"preference_peak", "expected_structure", "digital_life", "garden", "runtime"}
    assert life_parameters.isdisjoint(forbidden)
