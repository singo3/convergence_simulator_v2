"""Static ownership boundaries for fatigue recovery and scaled candidate search."""

from __future__ import annotations

import ast
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

from symbiotic_sim_v2.digital_life.relation_memory.transitions import (
    apply_relation_memory_transition,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    create_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.experimental_multi_session.component_factory import (
    create_experimental_adaptive_relation_memory_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.multi_life.coordinator import (
    MultiLifeRuntimeCoordinator,
)

PACKAGE_ROOT = Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"


@pytest.mark.parametrize(
    "statement",
    (
        "from symbiotic_sim_v2.runtime.experimental_multi_session import "
        "FatigueSigmaSingleConditionRunner",
        "from symbiotic_sim_v2.runtime.experimental_multi_session.component_factory "
        "import create_experimental_adaptive_relation_memory_closed_loop_simulation",
        "from symbiotic_sim_v2.experiments.fatigue_sigma import "
        "FatigueSigmaGridRunner, export_grid_csv",
    ),
)
def test_public_import_paths_are_safe_in_a_fresh_process(statement: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", statement],
        cwd=PACKAGE_ROOT.parents[1],
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_policy_and_experimental_component_cores_are_qt_free() -> None:
    paths = (
        PACKAGE_ROOT / "experiments" / "fatigue_sigma" / "fatigue_policy.py",
        PACKAGE_ROOT / "experiments" / "fatigue_sigma" / "sigma_policy.py",
        PACKAGE_ROOT
        / "runtime"
        / "experimental_multi_session"
        / "experimental_component.py",
    )
    modules = set().union(*(imported_modules(path) for path in paths))
    assert not any(
        module.startswith(("PySide6", "PyQt", "pyqtgraph", "symbiotic_sim_v2.gui"))
        for module in modules
    )


def test_existing_factory_and_transition_signatures_are_unchanged() -> None:
    assert tuple(
        inspect.signature(
            create_adaptive_relation_memory_closed_loop_simulation
        ).parameters
    ) == (
        "virtual_user_config",
        "polar_h10_config",
        "garden_input_config",
        "digital_life_configs",
        "runtime_config",
        "garden_output_config",
        "garden_light_mapper_config",
        "virtual_light_device_config",
        "light_response_config",
        "initial_persistent_states_by_life_id",
    )
    assert tuple(inspect.signature(apply_relation_memory_transition).parameters) == (
        "persistent_state",
        "session_state",
        "transition_input",
    )
    assert {
        "fatigue_policy",
        "sigma_policy",
    } <= set(
        inspect.signature(
            create_experimental_adaptive_relation_memory_closed_loop_simulation
        ).parameters
    )


def test_closing_policy_hook_is_after_all_second_rounds_and_before_release_schedule() -> None:
    source = inspect.getsource(MultiLifeRuntimeCoordinator.handle_interoceptive_feedback)
    pending_check = source.index("has_pending_second_round")
    policy_hook = source.index("finalize_session_end_state_policy")
    release_schedule = source.index("engine.schedule_at")
    assert pending_check < policy_hook < release_schedule


def test_runtime_orchestration_never_performs_e_or_sigma_math() -> None:
    coordinator = (
        PACKAGE_ROOT / "runtime" / "multi_life" / "coordinator.py"
    ).read_text(encoding="utf-8")
    factory = (
        PACKAGE_ROOT
        / "runtime"
        / "experimental_multi_session"
        / "component_factory.py"
    ).read_text(encoding="utf-8")
    assert "calculate_e_next" not in coordinator
    assert "selected_session_eta" not in coordinator
    assert "exploration_sigma" not in coordinator
    assert "generate_candidate" not in coordinator
    assert "SimulationEngine(" not in factory
    assert "GardenOutputComponent(" not in factory


def test_recovery_mutation_lives_in_the_component_not_a_runner_or_factory() -> None:
    component = (
        PACKAGE_ROOT
        / "runtime"
        / "experimental_multi_session"
        / "experimental_component.py"
    ).read_text(encoding="utf-8")
    factory = (
        PACKAGE_ROOT
        / "runtime"
        / "experimental_multi_session"
        / "component_factory.py"
    ).read_text(encoding="utf-8")
    assert "replace(pending, e=decision.e_after_policy)" in component
    assert "e=decision.e_after_policy" not in factory
    assert "condition_id" not in component
    assert "condition_hash" not in component


def test_experimental_policy_sources_do_not_import_hidden_truth_or_old_simulator() -> None:
    paths = tuple(
        (PACKAGE_ROOT / "experiments" / "fatigue_sigma").glob("*policy.py")
    ) + tuple(
        (PACKAGE_ROOT / "runtime" / "experimental_multi_session").glob("*.py")
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "truth_alignment" not in source
    assert "hidden_peak" not in source
    assert "convergence_simulator" not in source
