"""Stage 8A.1 CLI, launcher routing, and project-version contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from symbiotic_sim_v2 import __main__ as command
from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.gui.fatigue_sigma_lab_backend import (
    CoreFatigueSigmaLabBackend,
)


def test_project_and_packaging_versions_include_stage_08a3() -> None:
    root = Path(__file__).parents[2]
    assert __version__ == "0.13.0"
    assert 'version = "0.13.0"' in (root / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert command.STAGE_8A_HEADLESS_PROJECT_VERSION == "0.10.0"


def test_single_cli_routes_every_stage_08a1_option(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    def fake(**values):
        captured.update(values)
        return 17

    monkeypatch.setattr(command, "run_headless_fatigue_sigma_lab_demo", fake)
    state = tmp_path / "in.json"
    final = tmp_path / "out.json"
    csv = tmp_path / "csv"
    assert (
        command.main(
            [
                "--headless-fatigue-sigma-lab-demo",
                "--stationary-user-type-v2",
                "bpm_common_100_hue_neutral",
                "--selected-session-fatigue-target",
                "0.08",
                "--sigma-multiplier",
                "1.25",
                "--maximum-sessions",
                "60",
                "--master-seed",
                "42",
                "--compare-reference-arm",
                "--initial-experiment-state-json",
                str(state),
                "--export-final-experiment-state-json",
                str(final),
                "--export-experiment-csv",
                str(csv),
            ]
        )
        == 17
    )
    assert captured == {
        "stationary_user_type_v2": "bpm_common_100_hue_neutral",
        "selected_session_fatigue_target": 0.08,
        "sigma_multiplier": 1.25,
        "maximum_sessions": 60,
        "master_seed": 42,
        "compare_reference_arm": True,
        "initial_state_json": state,
        "export_final_state_json": final,
        "export_csv": csv,
    }


def test_grid_cli_parses_lists_and_routes_paired_settings(monkeypatch) -> None:
    captured = {}

    def fake(**values):
        captured.update(values)
        return 19

    monkeypatch.setattr(command, "run_headless_fatigue_sigma_grid_demo", fake)
    assert (
        command.main(
            [
                "--headless-fatigue-sigma-grid-demo",
                "--stationary-user-type-v2",
                "three_life_bpm_equal",
                "--fatigue-targets",
                "0.03,0.15",
                "--sigma-multipliers",
                "0.5,1.5",
                "--maximum-sessions",
                "12",
                "--replicates",
                "3",
                "--master-seed",
                "7",
                "--experiment-preset",
                "detailed",
            ]
        )
        == 19
    )
    assert captured == {
        "stationary_user_type_v2": "three_life_bpm_equal",
        "fatigue_targets": (0.03, 0.15),
        "sigma_multipliers": (0.5, 1.5),
        "maximum_sessions": 12,
        "replicates": 3,
        "master_seed": 7,
        "experiment_preset": "detailed",
        "export_csv": None,
    }


def test_detailed_grid_preset_uses_sixty_sessions(monkeypatch, capsys) -> None:
    from symbiotic_sim_v2.experiments.fatigue_sigma import grid_runner

    captured = {}

    class Summary:
        experiment_manifest = {}

        @staticmethod
        def to_dict():
            return {"ok": True}

    class Runner:
        def __init__(self, config):
            captured["config"] = config

        @staticmethod
        def run():
            return Summary()

    monkeypatch.setattr(grid_runner, "FatigueSigmaGridRunner", Runner)
    assert (
        command.run_headless_fatigue_sigma_grid_demo(
            experiment_preset="detailed",
            fatigue_targets=(0.05,),
            sigma_multipliers=(1.0,),
            maximum_sessions=12,
            replicates=1,
        )
        == 0
    )
    assert captured["config"].maximum_sessions == 60
    assert json.loads(capsys.readouterr().out) == {"ok": True}


def test_single_and_grid_headless_json_policy_flags(capsys) -> None:
    assert (
        command.run_headless_fatigue_sigma_lab_demo(maximum_sessions=4)
        == 0
    )
    single = json.loads(capsys.readouterr().out)
    assert single["project_version"] == "0.11.0"
    assert single["sessions_completed"] == 4
    assert single["policy_flags"] == {
        "Monte_Carlo": False,
        "convergence_is_diagnostic_only": True,
        "epsilon_accept_modified": False,
        "exploration_continues_after_convergence": True,
        "formal_spec_adoption": False,
        "moving_preference": False,
        "p_explore_modified": False,
        "q_coefficients_modified": False,
        "stationary_preference": True,
        "unselected_full_recovery": True,
        "v2_reference_arm_available": True,
    }
    assert (
        command.run_headless_fatigue_sigma_grid_demo(
            fatigue_targets=(0.05,),
            sigma_multipliers=(1.0,),
            maximum_sessions=4,
            replicates=1,
        )
        == 0
    )
    grid = json.loads(capsys.readouterr().out)
    assert grid["total_planned_session_runs"] == 4
    assert grid["completed_conditions"] == 1
    assert grid["failed_conditions"] == 0
    assert grid["policy_flags"]["Monte_Carlo"] is False


def test_experiment_state_options_are_scoped_to_single_headless() -> None:
    with pytest.raises(ValueError, match="state options require"):
        command.main(
            [
                "--headless-fatigue-sigma-grid-demo",
                "--initial-experiment-state-json",
                "state.json",
            ]
        )


def test_gui_backend_rejects_implicit_bool_and_state_discard() -> None:
    settings = {
        "user_type_id": "green_hue_dominant_broad_bpm",
        "selected_session_fatigue_target": 0.05,
        "sigma_multiplier": 1.0,
        "maximum_sessions": 4,
        "master_seed": 20260802,
        "compare_reference_arm": False,
    }
    backend = CoreFatigueSigmaLabBackend()
    operation = backend.create_single_operation("next_session", settings)

    class Control:
        cancel_requested = False
        pause_requested = False

    result = operation(lambda _progress: None, Control())
    assert result.sessions_completed == 1
    with pytest.raises(RuntimeError, match="explicit reset"):
        backend.create_single_operation(
            "run_all",
            {**settings, "sigma_multiplier": 1.25},
        )(lambda _progress: None, Control())
    with pytest.raises(TypeError, match="must be boolean"):
        backend.create_single_operation(
            "run_all",
            {**settings, "compare_reference_arm": 1},
        )
