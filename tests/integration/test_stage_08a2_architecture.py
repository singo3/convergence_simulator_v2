"""Stage 8A.2 remains an offline Qt-free orchestration/diagnostic layer."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "symbiotic_sim_v2" / "experiments" / "fatigue_sigma_auto_search"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_auto_search_package_has_no_ai_network_or_qt_imports() -> None:
    forbidden = {
        "openai",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "PySide6",
        "PyQt6",
        "PyQt5",
        "pyqtgraph",
    }
    for path in PACKAGE.glob("*.py"):
        assert not (_imports(path) & forbidden), path


def test_subprocess_is_limited_to_local_git_fingerprint() -> None:
    users = []
    for path in PACKAGE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "subprocess" in source:
            users.append(path.name)
    assert users == ["fingerprint.py"]
    fingerprint = (PACKAGE / "fingerprint.py").read_text(encoding="utf-8")
    assert '("git", *arguments)' in fingerprint
    for forbidden in ("codex", "openai", "chatgpt", "curl", "wget"):
        assert f'("{forbidden}"' not in fingerprint.lower()


def test_auto_search_does_not_import_simulation_factories_or_core_components() -> None:
    runner = (PACKAGE / "runner.py").read_text(encoding="utf-8")
    assert "FatigueSigmaSingleConditionRunner" in runner
    assert "create_adaptive_relation_memory_closed_loop_simulation" not in runner
    assert "DigitalLifeComponent" not in runner
    assert "GardenOutput" not in runner
    assert "candidate_generated=" not in runner


def test_condition_is_not_mixed_into_paired_seed_derivation() -> None:
    job = (PACKAGE / "job.py").read_text(encoding="utf-8")
    call = "paired_replicate_master_seed(base_master_seed, replicate_index)"
    assert call in job
    assert "condition_key" not in call
    assert "sigma_multiplier" not in call
    assert "selected_session_fatigue_target" not in call


def test_truth_is_only_posthoc_report_data_not_a_runner_input() -> None:
    runner = (PACKAGE / "runner.py").read_text(encoding="utf-8")
    assert "truth_response" not in runner
    assert "hidden_preference" not in runner
    assert "convergence" not in runner.split("FatigueSigmaCondition.create", 1)[1].split(")", 1)[0]


def test_report_is_self_contained_and_has_no_cdn_tokens() -> None:
    report = (PACKAGE / "html_report.py").read_text(encoding="utf-8").lower()
    assert "cdn.jsdelivr" not in report
    assert "fonts.googleapis" not in report
    assert "<script src" not in report


def test_stage_08a2_does_not_change_stage_08a1_source_tree() -> None:
    assert PACKAGE.parent.name == "experiments"
    assert PACKAGE.name == "fatigue_sigma_auto_search"
    assert (PACKAGE.parent / "fatigue_sigma" / "grid_runner.py").is_file()
