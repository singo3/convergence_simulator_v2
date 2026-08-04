"""Stage 8A.2 CLI planning, help, validation, and dispatch tests."""

from __future__ import annotations

import json

import pytest

from symbiotic_sim_v2.__main__ import main


@pytest.mark.parametrize(
    ("preset", "planned"),
    (("smoke", 32), ("quick", 1_296), ("standard", 32_400), ("robust", 122_400)),
)
def test_cli_plan_only_has_exact_budget_and_no_execution(capsys, preset, planned) -> None:
    assert (
        main(
            [
                "--headless-fatigue-sigma-auto-search",
                "--search-preset",
                preset,
                "--plan-only",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["total_planned_session_runs"] == planned
    assert result["simulation_jobs_executed"] == 0
    assert result["state_changed"] is False


def test_cli_plan_only_does_not_create_output_directory(tmp_path, capsys) -> None:
    target = tmp_path / "must-not-exist"
    assert (
        main(
            [
                "--headless-fatigue-sigma-auto-search",
                "--search-preset",
                "smoke",
                "--output-directory",
                str(target),
                "--plan-only",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert not target.exists()


def test_cli_budget_error_is_not_silently_clipped() -> None:
    with pytest.raises(ValueError, match="exceed"):
        main(
            [
                "--headless-fatigue-sigma-auto-search",
                "--search-preset",
                "standard",
                "--maximum-total-session-runs",
                "32399",
                "--plan-only",
            ]
        )


def test_cli_resume_requires_existing_directory(tmp_path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        main(
            [
                "--headless-fatigue-sigma-auto-search",
                "--resume",
                str(tmp_path / "missing"),
            ]
        )


def test_cli_resume_rejects_silently_ignored_new_run_options(tmp_path) -> None:
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    with pytest.raises(ValueError, match="cannot be combined"):
        main(
            [
                "--headless-fatigue-sigma-auto-search",
                "--resume",
                str(run_directory),
                "--search-preset",
                "smoke",
            ]
        )


def test_cli_search_options_require_auto_search_mode() -> None:
    with pytest.raises(ValueError, match="require"):
        main(["--search-preset", "smoke", "--plan-only"])


def test_cli_help_lists_all_requested_options(capsys) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--help"])
    assert raised.value.code == 0
    output = capsys.readouterr().out
    for option in (
        "--headless-fatigue-sigma-auto-search",
        "--search-preset",
        "--output-directory",
        "--base-master-seed",
        "--include-reference-arm",
        "--no-reference-arm",
        "--stop-after-phase",
        "--maximum-total-session-runs",
        "--candidate-gate-config",
        "--search-config",
        "--retain-full-details",
        "--plan-only",
        "--resume",
    ):
        assert option in output
