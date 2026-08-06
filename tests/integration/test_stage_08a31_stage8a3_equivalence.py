"""A and D are golden-equivalent to the existing Stage 8A.3 routes."""

from __future__ import annotations

from pathlib import Path

import pytest

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    PROVISIONAL_CONDITION as STAGE08A3_PROVISIONAL,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    V2_REFERENCE_CONDITION as STAGE08A3_REFERENCE,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    ValidationConfig,
    validation_condition,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.fingerprint import (
    ValidationCodeFingerprint,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.runner import (
    AdaptivePlaceboValidationRunner,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.conditions import (
    PROVISIONAL_CONDITION,
    V2_REFERENCE_CONDITION,
    factorial_condition,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.config import (
    FactorialValidationConfig,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.persistence import (
    FactorialCodeFingerprint,
)
from symbiotic_sim_v2.experiments.fatigue_recovery_sigma_factorial.runner import (
    FatigueRecoverySigmaFactorialRunner,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def golden_equivalence(tmp_path_factory):
    base = tmp_path_factory.mktemp("stage08a31-golden")
    old_config = ValidationConfig.create(
        validation_preset="smoke",
        output_directory=str(base / "old"),
    )
    new_config = FactorialValidationConfig.create(
        validation_preset="smoke",
        output_directory=str(base / "new"),
    )
    old = AdaptivePlaceboValidationRunner(
        old_config,
        repo_root=ROOT,
        code_fingerprint=ValidationCodeFingerprint.capture(ROOT, allow_dirty=True),
        allow_dirty_code=True,
    )
    new = FatigueRecoverySigmaFactorialRunner(
        new_config,
        repo_root=ROOT,
        code_fingerprint=FactorialCodeFingerprint.capture(ROOT, allow_dirty=True),
        allow_dirty_code=True,
    )
    participant = next(
        item
        for item in old._participants
        if item.user_type_id == "green_hue_dominant_broad_bpm"
        and item.participant_index == 0
    )
    new_participant = next(
        item for item in new._participants if item.participant_id == participant.participant_id
    )
    output = {}
    for new_id, old_id in (
        (V2_REFERENCE_CONDITION, STAGE08A3_REFERENCE),
        (PROVISIONAL_CONDITION, STAGE08A3_PROVISIONAL),
    ):
        old_runner = old._condition_runner(participant, validation_condition(old_id))
        new_runner = new._condition_runner(new_participant, factorial_condition(new_id))
        while old_runner.can_run_next_session:
            old_runner.run_next_session()
        while new_runner.can_run_next_session:
            new_runner.run_next_session()
        old_outcomes = old_runner.session_outcomes()
        new_outcomes = new_runner.session_outcomes()
        output[new_id] = (old_outcomes, new_outcomes)
    repeated = new._condition_runner(
        new_participant,
        factorial_condition(PROVISIONAL_CONDITION),
    )
    while repeated.can_run_next_session:
        repeated.run_next_session()
    output["deterministic_repeat"] = repeated.session_outcomes()
    return output


@pytest.mark.parametrize("condition_id", (V2_REFERENCE_CONDITION, PROVISIONAL_CONDITION))
def test_single_session_outcome_is_exact_stage8a3_golden(
    golden_equivalence,
    condition_id: str,
) -> None:
    old, new = golden_equivalence[condition_id]
    assert old[0].to_dict() == new[0].to_dict()
    assert old[0].session_digest == new[0].session_digest


@pytest.mark.parametrize("condition_id", (V2_REFERENCE_CONDITION, PROVISIONAL_CONDITION))
def test_four_session_handoff_is_exact_stage8a3_golden(
    golden_equivalence,
    condition_id: str,
) -> None:
    old, new = golden_equivalence[condition_id]
    assert [item.to_dict() for item in old] == [item.to_dict() for item in new]
    assert (
        old[-1].final_persistent_state_by_life
        == new[-1].final_persistent_state_by_life
    )


def test_reference_and_provisional_ids_remain_stage8a3_ids() -> None:
    assert V2_REFERENCE_CONDITION == STAGE08A3_REFERENCE
    assert PROVISIONAL_CONDITION == STAGE08A3_PROVISIONAL


def test_factorial_autonomous_rerun_is_deterministic(golden_equivalence) -> None:
    original = golden_equivalence[PROVISIONAL_CONDITION][1]
    repeated = golden_equivalence["deterministic_repeat"]
    assert [item.to_dict() for item in original] == [
        item.to_dict() for item in repeated
    ]
