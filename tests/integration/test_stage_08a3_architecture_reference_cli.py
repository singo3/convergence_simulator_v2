"""Stage 8A.3 architecture, independent vectors, CLI, and report contract."""

from __future__ import annotations

import ast
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from symbiotic_sim_v2.__main__ import main
from symbiotic_sim_v2.experiments.adaptive_placebo_validation import config
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.analysis import (
    circular_hue_distance,
    circular_mean_and_concentration,
    classify_participant_effect,
    counterfactual_percentile,
    deterministic_counterfactual_set,
    gaussian_kernel,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.output_policy import (
    deterministic_random_session_outputs,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "symbiotic_sim_v2" / "experiments" / "adaptive_placebo_validation"
VECTORS = ROOT / "docs" / "conformance" / "stage-08a3-reference-vectors.json"
GENERATOR = ROOT / "tools" / "generate_stage_08a3_reference_vectors.py"


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
def test_package_has_no_ai_network_or_qt_import(forbidden: str) -> None:
    for path in PACKAGE.glob("*.py"):
        assert forbidden not in _imports(path), path


@pytest.mark.parametrize(
    ("name", "expected"),
    (
        ("PROJECT_VERSION", "0.13.0"),
        ("VALIDATION_MODEL_VERSION", "adaptive_placebo_rmssd_validation_v0_1"),
        ("ARM_CONTRACT_VERSION", "adaptive_placebo_arm_contract_v0_1"),
        ("AUTONOMOUS_ARM_VERSION", "autonomous_closed_loop_arm_v0_1"),
        ("YOKED_ARM_VERSION", "response_decoupled_yoked_replay_v0_1"),
        ("RANDOM_ARM_VERSION", "pure_random_open_loop_v0_1"),
        ("VALIDATION_PARTICIPANT_VERSION", "fixed_validation_participant_v0_1"),
        ("YOKE_MAPPING_VERSION", "cyclic_same_type_yoke_mapping_v0_1"),
        ("RANDOM_OUTPUT_VERSION", "deterministic_random_light_sequence_v0_1"),
        ("BUNDLE_OUTCOME_SCHEMA_VERSION", "validation_bundle_outcome_v1"),
        ("SESSION_OUTCOME_SCHEMA_VERSION", "validation_session_outcome_v1"),
        ("HISTORY_RESPONSE_MODEL_VERSION", "past_sessions_only_response_model_v0_1"),
        ("LAGGED_COUPLING_VERSION", "rmssd_to_future_output_coupling_v0_1"),
        ("PROSPECTIVE_ENRICHMENT_VERSION", "prospective_selection_enrichment_v0_1"),
        ("PARTICIPANT_EFFECT_VERSION", "participant_adaptive_effect_v0_1"),
        ("VALIDATION_SUMMARY_VERSION", "adaptive_placebo_validation_summary_v1"),
        ("VALIDATION_REPORT_VERSION", "adaptive_placebo_validation_report_v0_1"),
        ("DOCUMENT_VERSION", "v2.0"),
        ("PROFILE_VERSION", "symbiotic_signal_loop_reference_v1_0"),
        ("ALGORITHM_VERSION", "adaptive_random_search_confirmed_v1"),
        ("STATE_SCHEMA_VERSION", "relation_memory_state_v2"),
    ),
)
def test_version_tuple_and_new_contract_versions(name: str, expected: str) -> None:
    assert getattr(config, name) == expected


@pytest.mark.parametrize(
    "required_key",
    (
        "cyclic_yoke_map",
        "random_output",
        "delta_rmssd",
        "past_only_history",
        "life_history_score",
        "bpm_kernel",
        "circular_hue_distance",
        "counterfactual",
        "lag1_same_life_correlation",
        "pattern_closeness",
        "rmssd_effect",
        "participant_bootstrap",
        "circular_hue",
        "participant_classification",
        "flat_null_fixture",
        "report_trajectory_fixture",
    ),
)
def test_independent_reference_vector_has_required_fixture(required_key: str) -> None:
    values = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert values["production_implementation_imported"] is False
    assert required_key in values


def test_reference_vector_generator_is_fresh_and_independent() -> None:
    source = GENERATOR.read_text(encoding="utf-8")
    assert "symbiotic_sim_v2" not in source
    assert subprocess.run(
        [str(ROOT / ".venv" / "bin" / "python"), str(GENERATOR), "--check"],
        cwd=ROOT,
        check=False,
    ).returncode == 0


def test_reference_random_output_matches_production() -> None:
    values = json.loads(VECTORS.read_text(encoding="utf-8"))["random_output"]
    for fixture in values["sessions"]:
        outputs = deterministic_random_session_outputs(
            validation_master_seed=values["master_seed"],
            participant_id=values["participant_id"],
            session_index=fixture["session_index"],
        )
        for actual, expected in zip(outputs, fixture["outputs"], strict=True):
            assert actual.displayed_life_id == expected["life_id"]
            assert actual.displayed_role == expected["role"]
            assert actual.hue_degree == expected["hue_degree"]
            assert actual.blink_bpm == expected["blink_bpm"]
            assert actual.output_seed == expected["output_seed"]


def test_reference_math_matches_production() -> None:
    values = json.loads(VECTORS.read_text(encoding="utf-8"))
    hue = values["circular_hue_distance"]
    assert circular_hue_distance(hue["first"], hue["second"]) == hue["distance"]
    counterfactual = values["counterfactual"]
    assert len(deterministic_counterfactual_set()) == counterfactual["candidate_count"]
    assert counterfactual_percentile(
        counterfactual["actual"], counterfactual["values"]
    ) == counterfactual["percentile"]
    assert gaussian_kernel(0.0, 15.0) == 1.0
    circular = values["circular_hue"]
    actual_mean, actual_concentration = circular_mean_and_concentration(
        circular["values"]
    )
    assert circular_hue_distance(actual_mean or 0.0, circular["mean_degree"]) < 1e-12
    assert actual_concentration == circular["concentration"]


@pytest.mark.parametrize(
    "label",
    (
        "clear_positive",
        "partial",
        "no_clear",
        "negative",
        "insufficient",
    ),
)
def test_reference_classification_labels_are_production_values(label: str) -> None:
    values = json.loads(VECTORS.read_text(encoding="utf-8"))[
        "participant_classification"
    ]
    expected = {
        "clear_positive": classify_participant_effect(
            late_advantage_ms=1.0,
            selection_enrichment_advantage=1.0,
            slope_advantage=1.0,
            permutation_p_like=0.1,
            valid_session_count=8,
        ),
        "partial": classify_participant_effect(
            late_advantage_ms=0.3,
            selection_enrichment_advantage=1.0,
            slope_advantage=1.0,
            permutation_p_like=0.8,
            valid_session_count=8,
        ),
        "no_clear": classify_participant_effect(
            late_advantage_ms=0.0,
            selection_enrichment_advantage=0.0,
            slope_advantage=0.0,
            permutation_p_like=0.8,
            valid_session_count=8,
        ),
        "negative": classify_participant_effect(
            late_advantage_ms=-1.0,
            selection_enrichment_advantage=-1.0,
            slope_advantage=-1.0,
            permutation_p_like=0.8,
            valid_session_count=8,
        ),
        "insufficient": classify_participant_effect(
            late_advantage_ms=1.0,
            selection_enrichment_advantage=1.0,
            slope_advantage=1.0,
            permutation_p_like=0.1,
            valid_session_count=3,
        ),
    }
    assert values[label] == expected[label]


@pytest.mark.parametrize(
    "option",
    (
        "--headless-adaptive-placebo-validation",
        "--validation-preset",
        "--conditions-json",
        "--validation-config",
        "--base-master-seed",
        "--participants-per-type",
        "--maximum-sessions",
        "--permutation-count",
        "--output-directory",
        "--retain-details",
        "--plan-only",
        "--resume",
    ),
)
def test_cli_help_lists_stage_08a3_options(capsys, option: str) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--help"])
    assert raised.value.code == 0
    assert option in capsys.readouterr().out


@pytest.mark.parametrize(
    ("preset", "planned"),
    (("smoke", 48), ("quick", 576), ("standard", 12_960), ("robust", 64_800)),
)
def test_cli_plan_only_exact_and_has_no_side_effect(
    capsys,
    tmp_path: Path,
    preset: str,
    planned: int,
) -> None:
    output = tmp_path / "not-created"
    assert main(
        [
            "--headless-adaptive-placebo-validation",
            "--validation-preset",
            preset,
            "--output-directory",
            str(output),
            "--plan-only",
        ]
    ) == 0
    projection = json.loads(capsys.readouterr().out)
    assert projection["total_planned_session_runs"] == planned
    assert projection["simulation_jobs_executed"] == 0
    assert not output.exists()


def test_validation_options_require_validation_mode() -> None:
    with pytest.raises(ValueError, match="Stage 8A.3"):
        main(["--validation-preset", "smoke"])


def test_placebo_output_functions_have_no_target_rmssd_n_w_q_k_e_parameters() -> None:
    from symbiotic_sim_v2.experiments.adaptive_placebo_validation.open_loop import (
        create_random_open_loop_session,
        create_yoked_replay_session,
    )

    forbidden = {"rmssd", "n", "w", "q", "k", "e", "condition"}
    for function in (
        create_yoked_replay_session,
        create_random_open_loop_session,
        deterministic_random_session_outputs,
    ):
        names = {name.lower() for name in inspect.signature(function).parameters}
        assert not (names & forbidden)


@pytest.mark.parametrize(
    "section",
    (
        "検証仮説",
        "arm定義",
        "condition",
        "仮想参加者cohort",
        "contemporaneousとlaggedの違い",
        "全体主要結果",
        "autonomous vs yoked",
        "autonomous vs random",
        "user type別結果",
        "participant別結果",
        "participant別BPM/Hue trajectory",
        "user type平均trajectory",
        "ΔRMSSD session曲線",
        "lagged coupling",
        "prospective enrichment",
        "prediction correlation",
        "permutation null",
        "participant effect classification",
        "flat control",
        "yoked donor map",
        "invalid / rejected data",
        "condition比較",
        "不確実性",
        "reproduction command",
        "simulation-only注意事項",
    ),
)
def test_report_source_has_required_section(section: str) -> None:
    source = (PACKAGE / "html_report.py").read_text(encoding="utf-8")
    assert section in source


def test_report_source_is_self_contained() -> None:
    source = (PACKAGE / "html_report.py").read_text(encoding="utf-8").lower()
    for forbidden in ("https://", "http://", "cdn", "google fonts", "<script src"):
        assert forbidden not in source


def test_runner_reuses_stage_08a1_and_stage_08a2_io() -> None:
    source = (PACKAGE / "runner.py").read_text(encoding="utf-8")
    assert "FatigueSigmaSingleConditionRunner" in source
    assert "RunDirectoryLock" in source
    assert "atomic_write_json" in source
    assert "create_adaptive_relation_memory_closed_loop_simulation" not in source
    assert "truth_response" not in source


def test_past_only_cutoff_is_explicit_in_analysis() -> None:
    source = (PACKAGE / "analysis.py").read_text(encoding="utf-8")
    assert "row.session_index < session_index" in source
    assert '"history_cutoff_session_index": session.session_index - 1' in source


@pytest.mark.parametrize(
    "filename",
    (
        "自律プラセボ検証_計画確認.command",
        "自律プラセボ検証_標準.command",
        "自律プラセボ検証_堅牢.command",
        "自律プラセボ検証_再開.command",
    ),
)
def test_macos_launcher_is_executable_local_and_guarded(filename: str) -> None:
    path = ROOT / filename
    source = path.read_text(encoding="utf-8")
    assert path.stat().st_mode & 0o111
    assert ".venv/bin/python" in source
    assert 'git branch --show-current' in source
    assert 'git status --porcelain' in source
    assert "--headless-adaptive-placebo-validation" in source
    assert "http" not in source.lower()
