"""Stage 8A.3.1 remains offline, observational, and narrowly injected."""

from __future__ import annotations

import ast
import inspect
import subprocess
from pathlib import Path

import pytest

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    build_participants,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.output_policy import (
    deterministic_random_session_outputs,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.profiles import (
    base_profile_payloads,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial import config
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    ALGORITHM_VERSION,
    DOCUMENT_VERSION,
    PROFILE_VERSION,
    STATE_SCHEMA_VERSION,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.runner import (
    FatigueRecoverySigmaFactorialRunner,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = (
    ROOT
    / "src"
    / "symbiotic_sim_v2"
    / "experiments"
    / "fatigue_recovery_sigma_factorial"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize(
    "forbidden",
    (
        "openai",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "PySide6",
        "PyQt6",
        "PyQt5",
        "pyqtgraph",
    ),
)
def test_factorial_package_has_no_ai_network_or_qt_import(forbidden: str) -> None:
    for path in PACKAGE.glob("*.py"):
        assert forbidden not in _imports(path), path


@pytest.mark.parametrize(
    ("name", "expected"),
    (
        ("SHARED_RANDOM_COMPARATOR_VERSION", "shared_condition_independent_random_comparator_v0_1"),
        ("FACTORIAL_ANALYSIS_VERSION", "participant_paired_two_by_two_factorial_analysis_v0_1"),
        ("CONDITION_RECOMMENDATION_VERSION", "human_mvp_condition_comparison_v0_1"),
        ("FACTORIAL_REPORT_VERSION", "fatigue_recovery_sigma_factorial_report_v0_1"),
        ("FACTORIAL_MANIFEST_VERSION", "fatigue_recovery_sigma_factorial_manifest_v1"),
    ),
)
def test_factorial_contract_version(name: str, expected: str) -> None:
    assert getattr(config, name) == expected


def test_normative_version_tuple_is_unchanged() -> None:
    assert (
        DOCUMENT_VERSION,
        PROFILE_VERSION,
        ALGORITHM_VERSION,
        STATE_SCHEMA_VERSION,
    ) == (
        "v2.0",
        "symbiotic_signal_loop_reference_v1_0",
        "adaptive_random_search_confirmed_v1",
        "relation_memory_state_v2",
    )


def test_runner_reuses_stage8a3_projection_analysis_and_atomic_store() -> None:
    runner = (PACKAGE / "runner.py").read_text(encoding="utf-8")
    analysis = (PACKAGE / "analysis.py").read_text(encoding="utf-8")
    persistence = (PACKAGE / "persistence.py").read_text(encoding="utf-8")
    charts = (PACKAGE / "charts.py").read_text(encoding="utf-8")
    assert "project_validation_session" in runner
    assert "FatigueSigmaSingleConditionRunner" in runner
    assert "create_adaptive_relation_memory_closed_loop_simulation" not in runner
    assert "paired_arm_difference_rows" in analysis
    assert "prospective_rows" in analysis
    assert "ValidationStore" in persistence
    assert "ValidationCheckpoint" in persistence
    assert "participant_trajectory_svg" in charts
    assert "user_type_average_svg" in charts


def test_no_simulation_core_or_normative_file_is_changed() -> None:
    changed = subprocess.run(
        ("git", "diff", "--name-only", "HEAD"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    forbidden_prefixes = (
        "src/symbiotic_sim_v2/digital_life/",
        "src/symbiotic_sim_v2/garden/",
        "src/symbiotic_sim_v2/virtual_user/",
        "src/symbiotic_sim_v2/simulation/",
        "src/symbiotic_sim_v2/domain/",
    )
    assert not any(path.startswith(forbidden_prefixes) for path in changed)
    assert not any("symbiotic-digital-life-signal-loop-concept" in path for path in changed)


def test_condition_is_absent_from_physiology_seed_signature_and_body() -> None:
    signature = inspect.signature(FatigueRecoverySigmaFactorialRunner._physiology_seed)
    assert tuple(signature.parameters) == ("participant", "session_index")
    source = inspect.getsource(FatigueRecoverySigmaFactorialRunner._physiology_seed)
    assert "condition" not in source
    assert "arm" not in source


def test_participant_physiology_seed_is_shared_by_all_conditions() -> None:
    participants = build_participants(
        user_type_ids=("green_hue_dominant_broad_bpm",),
        participants_per_type=1,
        base_master_seed=20260806,
        profile_payloads=base_profile_payloads(),
    )
    participant = participants[0]
    values = {
        FatigueRecoverySigmaFactorialRunner._physiology_seed(participant, index)
        for _condition in range(4)
        for index in (0,)
    }
    assert len(values) == 1


def test_condition_is_absent_from_random_output_policy() -> None:
    parameters = {
        name.lower()
        for name in inspect.signature(
            deterministic_random_session_outputs
        ).parameters
    }
    assert "condition_id" not in parameters
    assert "recovery" not in parameters
    assert "sigma" not in parameters


def test_history_model_uses_only_prior_sessions() -> None:
    path = (
        ROOT
        / "src/symbiotic_sim_v2/experiments/adaptive_placebo_validation/analysis.py"
    )
    source = path.read_text(encoding="utf-8")
    assert "row.session_index < session_index" in source
    assert '"history_cutoff_session_index": session.session_index - 1' in source


def test_factorial_standard_has_no_yoked_arm() -> None:
    assert config.FACTORIAL_ARMS == (
        "autonomous_closed_loop",
        "pure_random_open_loop",
    )


@pytest.mark.parametrize(
    "section",
    (
        "1. 検証目的",
        "2. 2×2 factor定義",
        "3. 4条件",
        "4. 実行計画",
        "5. 全体結果",
        "6. user type別結果",
        "7. participant別結果",
        "8. v2 referenceとの比較",
        "9. sigma 0.5の主効果",
        "10. full recoveryの主効果",
        "11. interaction",
        "12. RMSSD利益",
        "13. lagged coupling",
        "14. selection enrichment",
        "15. participant positive rate",
        "16. flat control",
        "17. W ceiling",
        "18. holder / Hue / BPM trajectory",
        "19. type-specific risk",
        "20. 実人間MVP条件候補",
        "21. 不確実性",
        "22. reproduction command",
        "23. formal_spec_adoption=false",
        "24. simulation-only注意事項",
    ),
)
def test_report_source_has_required_section(section: str) -> None:
    assert section in (PACKAGE / "html_report.py").read_text(encoding="utf-8")


def test_report_source_is_self_contained() -> None:
    source = (PACKAGE / "html_report.py").read_text(encoding="utf-8").lower()
    for forbidden in ("https://", "http://", "cdn", "google fonts", "<script src"):
        assert forbidden not in source
