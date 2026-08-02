"""Static Stage 5B responsibility and excluded-future-stage checks."""

from __future__ import annotations

import ast
from pathlib import Path


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


def test_runtime_and_garden_output_cores_have_no_gui_dependency() -> None:
    roots = (
        package_root() / "runtime" / "multi_life",
        package_root() / "garden" / "output_layer",
    )
    imports = set().union(
        *(imported_modules(path) for root in roots for path in python_sources(root))
    )
    assert all(
        not module.startswith(("PySide6", "PyQt", "pyqtgraph"))
        for module in imports
    )


def test_garden_output_has_no_digital_life_or_private_decision_inputs() -> None:
    root = package_root() / "garden" / "output_layer"
    sources = python_sources(root)
    imports = set().union(*(imported_modules(path) for path in sources))
    assert all(not module.startswith("symbiotic_sim_v2.digital_life") for module in imports)

    identifiers: set[str] = set()
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        identifiers.update(
            node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)
        )
        identifiers.update(
            node.attr.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
        )
    assert identifiers.isdisjoint(
        {
            "p",
            "v",
            "tau",
            "nd",
            "w",
            "e",
            "q",
            "k",
            "calculate_g",
            "calculate_e_next",
            "calculate_q_next",
        }
    )


def test_garden_output_core_has_no_role_or_fixed_fixture_identity() -> None:
    root = package_root() / "garden" / "output_layer"
    core_paths = tuple(
        root / filename
        for filename in ("component.py", "config.py", "events.py", "records.py")
    )
    trees = tuple(ast.parse(path.read_text(encoding="utf-8")) for path in core_paths)
    identifiers = {
        value
        for tree in trees
        for node in ast.walk(tree)
        for value in (
            (node.id if isinstance(node, ast.Name) else None),
            (node.attr if isinstance(node, ast.Attribute) else None),
        )
        if value is not None
    }
    string_literals = {
        node.value
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert "_ROLE_BY_ID" not in identifiers
    assert "role" not in identifiers
    assert {"life-red", "life-green", "life-blue"}.isdisjoint(string_literals)


def test_connected_life_has_no_other_life_collection_or_runtime_dependency() -> None:
    path = package_root() / "digital_life" / "connected_component.py"
    imports = imported_modules(path)
    source = path.read_text(encoding="utf-8")
    assert all(not module.startswith("symbiotic_sim_v2.runtime") for module in imports)
    assert "digital_life_components" not in source
    assert "other_life" not in source


def test_stage5b_core_has_no_exploration_light_mapping_or_old_simulator() -> None:
    roots = (
        package_root() / "runtime" / "multi_life",
        package_root() / "garden" / "output_layer",
        package_root() / "digital_life" / "connected_component.py",
        package_root() / "digital_life" / "second_round.py",
        package_root() / "digital_life" / "touch_intent.py",
    )
    paths = tuple(
        path
        for root in roots
        for path in (python_sources(root) if root.is_dir() else (root,))
    )
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in paths)
    for forbidden in (
        "convergence_simulator",
        "accepted_candidate",
        "k_trial",
        "trial_count",
        "exploration_decision",
        "adoption_result",
        "hue_degree",
        "blink_bpm",
        "light_waveform",
        "light_mapper",
        "virtual_user_light_response",
    ):
        assert forbidden not in source


def test_stage6_device_and_light_response_modules_do_not_exist_yet() -> None:
    root = package_root()
    forbidden_paths = (
        root / "devices" / "light",
        root / "garden" / "light_mapper.py",
        root / "virtual_user" / "light_response.py",
    )
    assert all(not path.exists() for path in forbidden_paths)
