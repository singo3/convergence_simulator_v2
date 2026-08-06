"""Stage 8A.3.1 CLI plans and local macOS launchers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from symbiotic_sim_v2.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
LAUNCHERS = (
    "疲労回復探索幅_追加検証_計画確認.command",
    "疲労回復探索幅_追加検証_標準.command",
    "疲労回復探索幅_追加検証_堅牢.command",
    "疲労回復探索幅_追加検証_再開.command",
)


@pytest.mark.parametrize(
    "option",
    (
        "--headless-fatigue-recovery-sigma-factorial-validation",
        "--validation-preset",
        "--base-master-seed",
        "--participants-per-type",
        "--maximum-sessions",
        "--output-directory",
        "--retain-details",
        "--plan-only",
        "--resume",
    ),
)
def test_cli_help_lists_factorial_option(capsys, option: str) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--help"])
    assert raised.value.code == 0
    assert option in capsys.readouterr().out


@pytest.mark.parametrize(
    ("preset", "autonomous", "random", "logical", "actual"),
    (
        ("smoke", 96, 24, 192, 120),
        ("standard", 8_640, 2_160, 17_280, 10_800),
        ("robust", 43_200, 10_800, 86_400, 54_000),
    ),
)
def test_plan_only_reports_physical_and_logical_counts_without_state(
    capsys,
    tmp_path: Path,
    preset: str,
    autonomous: int,
    random: int,
    logical: int,
    actual: int,
) -> None:
    output = tmp_path / "not-created"
    assert main(
        [
            "--headless-fatigue-recovery-sigma-factorial-validation",
            "--validation-preset",
            preset,
            "--output-directory",
            str(output),
            "--plan-only",
        ]
    ) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["autonomous_sessions"] == autonomous
    assert plan["shared_random_sessions"] == random
    assert plan["logical_comparison_sessions"] == logical
    assert plan["actual_simulation_sessions"] == actual
    assert plan["simulation_jobs_executed"] == 0
    assert plan["yoked_arm_included"] is False
    assert plan["formal_spec_adoption"] is False
    assert not output.exists()


def test_quick_is_not_a_factorial_preset() -> None:
    with pytest.raises(ValueError, match="unknown factorial validation preset"):
        main(
            [
                "--headless-fatigue-recovery-sigma-factorial-validation",
                "--validation-preset",
                "quick",
                "--plan-only",
            ]
        )


def test_stage8a3_custom_condition_file_is_rejected(tmp_path: Path) -> None:
    custom = tmp_path / "conditions.json"
    custom.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="fixed A/B/C/D"):
        main(
            [
                "--headless-fatigue-recovery-sigma-factorial-validation",
                "--conditions-json",
                str(custom),
                "--plan-only",
            ]
        )


def test_factorial_options_require_factorial_or_stage8a3_mode() -> None:
    with pytest.raises(ValueError, match="validation options require"):
        main(["--validation-preset", "standard"])


@pytest.mark.parametrize("filename", LAUNCHERS)
def test_launcher_is_executable_local_and_guarded(filename: str) -> None:
    path = ROOT / filename
    source = path.read_text(encoding="utf-8")
    assert path.stat().st_mode & 0o111
    assert ".venv/bin/python" in source
    assert "--headless-fatigue-recovery-sigma-factorial-validation" in source
    assert "git branch --show-current" in source
    assert "git status --porcelain" in source
    assert "http" not in source.lower()


def test_standard_and_robust_launchers_show_exact_actual_session_counts() -> None:
    standard = (ROOT / LAUNCHERS[1]).read_text(encoding="utf-8")
    robust = (ROOT / LAUNCHERS[2]).read_text(encoding="utf-8")
    assert "10,800" in standard
    assert "54,000" in robust


def test_resume_launcher_checks_factorial_manifest_schema() -> None:
    source = (ROOT / LAUNCHERS[3]).read_text(encoding="utf-8")
    assert "fatigue_recovery_sigma_factorial_manifest_v1" in source
