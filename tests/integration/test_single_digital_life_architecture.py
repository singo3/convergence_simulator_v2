"""Static responsibility-boundary tests for the Stage 5A Digital Life core."""

from __future__ import annotations

import ast
from pathlib import Path

from symbiotic_sim_v2.digital_life.config import DigitalLifeConfig
from symbiotic_sim_v2.digital_life.records import (
    DigitalLifeEvaluationUpdateRecord,
    DigitalLifeFirstRoundRecord,
    DigitalLifeSnapshot,
)
from symbiotic_sim_v2.digital_life.state import DigitalLifeState


def package_root() -> Path:
    return Path(__file__).parents[2] / "src" / "symbiotic_sim_v2"


def digital_life_root() -> Path:
    return package_root() / "digital_life"


def digital_life_sources() -> tuple[Path, ...]:
    return tuple(sorted(digital_life_root().glob("*.py")))


def runtime_core_sources() -> tuple[Path, ...]:
    names = (
        "config.py",
        "hash01.py",
        "intrinsic.py",
        "state.py",
        "records.py",
        "component.py",
        "diagnostics.py",
    )
    return tuple(digital_life_root() / name for name in names)


def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def imported_module_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(parsed(path)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def imported_names_from(path: Path, module: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(parsed(path)):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


def referenced_identifier_names(path: Path) -> set[str]:
    names = {node.id.lower() for node in ast.walk(parsed(path)) if isinstance(node, ast.Name)}
    names.update(
        node.attr.lower() for node in ast.walk(parsed(path)) if isinstance(node, ast.Attribute)
    )
    return names


def called_function_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(parsed(path)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def assigned_attribute_names(path: Path, method_names: set[str]) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(parsed(path)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name not in method_names:
            continue
        for child in ast.walk(node):
            targets: list[ast.expr] = []
            if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                if isinstance(child, ast.Assign):
                    targets.extend(child.targets)
                else:
                    targets.append(child.target)
            for target in targets:
                for target_node in ast.walk(target):
                    if isinstance(target_node, ast.Attribute):
                        names.add(target_node.attr)
    return names


def call_keyword_values(path: Path, call_name: str, keyword_name: str) -> list[ast.expr]:
    values: list[ast.expr] = []
    for node in ast.walk(parsed(path)):
        if not isinstance(node, ast.Call):
            continue
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        if name != call_name:
            continue
        values.extend(
            keyword.value for keyword in node.keywords if keyword.arg == keyword_name
        )
    return values


def dataclass_field_names(*classes: type[object]) -> set[str]:
    return {
        field_name.lower()
        for cls in classes
        for field_name in cls.__dataclass_fields__  # type: ignore[attr-defined]
    }


def test_digital_life_core_has_no_qt_or_pyqtgraph_imports() -> None:
    imports = set().union(*(imported_module_names(path) for path in digital_life_sources()))

    assert all(not name.startswith(("PySide6", "PyQt", "pyqtgraph")) for name in imports)


def test_component_consumes_only_formal_garden_events_not_upstream_internals() -> None:
    component = digital_life_root() / "component.py"
    imports = imported_module_names(component)
    source = component.read_text(encoding="utf-8")

    forbidden_prefixes = (
        "symbiotic_sim_v2.garden.input_layer",
        "symbiotic_sim_v2.virtual_user",
        "symbiotic_sim_v2.devices.polar_h10",
    )
    assert all(not name.startswith(forbidden_prefixes) for name in imports)
    assert imported_names_from(
        component, "symbiotic_sim_v2.domain.event_types"
    ) == {
        "GARDEN_EVALUATION_FINALIZED_EVENT_TYPE",
        "GARDEN_INPUT_SIGNAL_EVENT_TYPE",
    }
    assert all(
        name not in source
        for name in (
            "GardenInputComponent",
            "GardenRriRecord",
            "GardenEvaluationRecord",
            "GardenInputSignalRecord",
            "VirtualUserComponent",
            "HeartbeatRecord",
            "PolarH10Component",
            "RriMeasurementRecord",
        )
    )


def test_component_has_no_raw_rri_rmssd_or_artifact_dependency() -> None:
    component = digital_life_root() / "component.py"
    identifiers = referenced_identifier_names(component)
    imports = imported_module_names(component)

    assert identifiers.isdisjoint(
        {
            "rri",
            "raw_rri",
            "raw_rri_us",
            "rmssd",
            "rmssd_ms",
            "artifact",
            "artifact_rate",
        }
    )
    assert all(
        fragment not in module.lower()
        for module in imports
        for fragment in ("rri", "rmssd", "artifact")
    )


def test_live_component_does_not_import_or_call_e_q_update_functions() -> None:
    component = digital_life_root() / "component.py"

    assert imported_names_from(component, "symbiotic_sim_v2.digital_life.math") == {
        "calculate_nd",
        "calculate_p",
        "calculate_tau",
        "calculate_v",
        "evaluate_w",
        "intrinsic_b_mapping",
    }
    assert called_function_names(component).isdisjoint(
        {"calculate_e_next", "calculate_q_next", "w_plus", "w_minus"}
    )


def test_live_handlers_do_not_update_e_q_k_g_or_later_stage_state() -> None:
    component = digital_life_root() / "component.py"
    writes = assigned_attribute_names(
        component,
        {"handle_evaluation_finalized", "handle_garden_input_signal"},
    )

    assert writes.isdisjoint(
        {
            "e",
            "q",
            "k_anchor",
            "k_current",
            "g_status",
            "second_round_connected",
            "touch_dispatched_count",
        }
    )


def test_component_does_not_schedule_touch_or_any_other_event() -> None:
    component = digital_life_root() / "component.py"
    calls = called_function_names(component)
    handler_names = {
        node.name
        for node in ast.walk(parsed(component))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("handle_")
    }

    assert calls.isdisjoint({"schedule", "schedule_at", "schedule_after"})
    assert handler_names == {
        "handle_evaluation_finalized",
        "handle_garden_input_signal",
    }
    assert all("touch" not in name.lower() for name in calls)


def test_touch_g_and_second_round_fields_remain_explicit_diagnostic_placeholders() -> None:
    component = digital_life_root() / "component.py"
    touch_values = call_keyword_values(
        component,
        "DigitalLifeFirstRoundRecord",
        "touch_dispatched",
    )
    connected_values = call_keyword_values(
        component,
        "DigitalLifeFirstRoundRecord",
        "second_round_connected",
    )
    initial_touch_counts = call_keyword_values(
        component,
        "DigitalLifeState",
        "touch_dispatched_count",
    )
    initial_g_statuses = call_keyword_values(component, "DigitalLifeState", "g_status")

    assert len(touch_values) == 1
    assert isinstance(touch_values[0], ast.Constant) and touch_values[0].value is False
    assert len(connected_values) == 1
    assert isinstance(connected_values[0], ast.Constant) and connected_values[0].value is False
    assert len(initial_touch_counts) == 1
    assert isinstance(initial_touch_counts[0], ast.Constant)
    assert initial_touch_counts[0].value == 0
    assert len(initial_g_statuses) == 1
    assert isinstance(initial_g_statuses[0], ast.Name)
    assert initial_g_statuses[0].id == "G_STATUS_NOT_CONNECTED"


def test_no_touch_g_or_stage5b_event_type_has_been_added() -> None:
    event_types = package_root() / "domain" / "event_types.py"
    values = {
        node.value.value.lower()
        for node in ast.walk(parsed(event_types))
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    forbidden_fragments = {
        "touch",
        "garden_output",
        "qualification",
        "holder",
        "second_round",
        "exploration",
        "adoption",
    }

    assert all(
        fragment not in value for value in values for fragment in forbidden_fragments
    )


def test_runtime_state_and_records_have_no_stage5b_state() -> None:
    fields = dataclass_field_names(
        DigitalLifeConfig,
        DigitalLifeState,
        DigitalLifeFirstRoundRecord,
        DigitalLifeEvaluationUpdateRecord,
        DigitalLifeSnapshot,
    )
    forbidden = {
        "g",
        "holder",
        "qualification_id",
        "qualification_winner",
        "k_trial",
        "w_anchor_session",
        "w_trial_1",
        "w_trial_2",
        "exploration_decision",
        "adoption_result",
        "accepted_candidate",
        "trial_count",
        "session_count",
        "sigma",
        "p_explore",
        "epsilon_accept",
    }

    assert fields.isdisjoint(forbidden)


def test_no_garden_output_or_stage5b_module_has_been_added() -> None:
    assert not (package_root() / "garden" / "output_layer").exists()
    forbidden_stems = {
        "adoption",
        "exploration",
        "garden_output",
        "holder",
        "qualification",
        "second_round",
        "touch",
        "trial",
    }

    assert {path.stem.lower() for path in digital_life_sources()}.isdisjoint(
        forbidden_stems
    )


def test_no_old_simulator_import_or_reference_exists_in_stage5a_core() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in runtime_core_sources())
    imports = set().union(*(imported_module_names(path) for path in runtime_core_sources()))

    assert "convergence_simulator" not in source
    assert all("convergence_simulator" not in name for name in imports)
