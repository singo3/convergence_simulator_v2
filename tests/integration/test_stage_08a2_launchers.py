"""Static and shell-syntax checks for the local macOS launchers."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHERS = {
    "plan": REPO_ROOT / "自動条件探索_計画確認.command",
    "standard": REPO_ROOT / "自動条件探索_標準.command",
    "robust": REPO_ROOT / "自動条件探索_堅牢.command",
    "resume": REPO_ROOT / "自動条件探索_再開.command",
}


def _text(name: str) -> str:
    return LAUNCHERS[name].read_text(encoding="utf-8")


def test_launchers_exist_are_executable_and_have_valid_zsh_syntax() -> None:
    for path in LAUNCHERS.values():
        assert path.is_file()
        assert path.stat().st_mode & os.X_OK
        subprocess.run(
            ["/bin/zsh", "-n", str(path)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


def test_all_launchers_check_local_environment_and_never_open_browser() -> None:
    for name in LAUNCHERS:
        text = _text(name)
        assert ".venv/bin/python" in text
        assert "sys.version_info < (3, 12)" in text
        assert "git status --porcelain" in text
        assert '!= "main"' in text
        assert "open " not in text
        assert "credential" not in text.lower()


def test_plan_and_standard_launchers_use_the_requested_standard_commands() -> None:
    plan = _text("plan")
    standard = _text("standard")
    assert "--search-preset standard" in plan
    assert "--plan-only" in plan
    assert "--search-preset standard" in standard
    assert "--plan-only" in standard
    assert "STANDARD" in standard
    assert "2>&1 | tee" in standard
    assert "report/report.html" in standard


def test_robust_launcher_requires_explicit_confirmation() -> None:
    robust = _text("robust")
    assert "--search-preset robust" in robust
    assert "--plan-only" in robust
    assert '!= "ROBUST"' in robust
    assert "2>&1 | tee" in robust
    assert "report/report.html" in robust


def test_resume_launcher_validates_path_and_manifest_before_resume() -> None:
    resume = _text("resume")
    assert 'RUN_DIRECTORY="${1:-}"' in resume
    assert '[[ ! -d "$RUN_DIRECTORY" ]]' in resume
    assert "search_manifest.json" in resume
    assert "fatigue_sigma_auto_search_manifest_v1" in resume
    assert '--resume "$RUN_DIRECTORY"' in resume
    assert "2>&1 | tee" in resume
    assert "report/report.html" in resume
