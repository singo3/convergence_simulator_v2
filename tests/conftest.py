"""Shared test environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def stage08a2_real_smoke(tmp_path_factory):
    """One shared 32-session real smoke search for Stage 8A.2 integration tests."""

    from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search import (
        AutoSearchConfig,
        AutoSearchRunner,
    )
    from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.fingerprint import (
        CodeFingerprint,
    )

    repo_root = Path(__file__).resolve().parents[1]
    fingerprint = CodeFingerprint.capture(repo_root, allow_dirty=True)
    output = tmp_path_factory.mktemp("stage08a2-real-smoke")
    config = AutoSearchConfig.create(
        search_preset="smoke",
        output_directory=str(output),
    )
    progress: list[dict[str, object]] = []
    runner = AutoSearchRunner(
        config,
        repo_root=repo_root,
        code_fingerprint=fingerprint,
        progress_callback=progress.append,
    )
    summary = runner.run()
    return {
        "runner": runner,
        "summary": summary,
        "fingerprint": fingerprint,
        "progress": progress,
        "repo_root": repo_root,
    }


@pytest.fixture(scope="session")
def stage08a2_paired_result_template():
    """A real four-session detached result reused by fast orchestration fakes."""

    from symbiotic_sim_v2.experiments.fatigue_sigma.condition import (
        FatigueSigmaCondition,
    )
    from symbiotic_sim_v2.runtime.experimental_multi_session.runner import (
        FatigueSigmaSingleConditionRunner,
    )

    runner = FatigueSigmaSingleConditionRunner(
        FatigueSigmaCondition.create(
            user_type_id="flat_control",
            maximum_sessions=4,
        ),
        compare_reference_arm=True,
    )
    runner.run_all()
    return runner.result()


@pytest.fixture(scope="session")
def stage08a31_real_smoke(tmp_path_factory):
    """One shared 120-session Stage 8A.3.1 smoke for integration tests."""

    from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.config import (
        FactorialValidationConfig,
    )
    from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.persistence import (
        FactorialCodeFingerprint,
    )
    from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.runner import (
        FatigueRecoverySigmaFactorialRunner,
    )

    repo_root = Path(__file__).resolve().parents[1]
    fingerprint = FactorialCodeFingerprint.capture(repo_root, allow_dirty=True)
    output = tmp_path_factory.mktemp("stage08a31-real-smoke")
    config = FactorialValidationConfig.create(
        validation_preset="smoke",
        output_directory=str(output),
        retain_details="representative",
    )
    progress: list[dict[str, object]] = []
    runner = FatigueRecoverySigmaFactorialRunner(
        config,
        repo_root=repo_root,
        progress_callback=progress.append,
        code_fingerprint=fingerprint,
        allow_dirty_code=True,
    )
    summary = runner.run()
    return {
        "runner": runner,
        "summary": summary,
        "fingerprint": fingerprint,
        "progress": progress,
        "repo_root": repo_root,
    }
