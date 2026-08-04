"""Canonical job ID, seed isolation, and reference cache tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    AutoSearchVersionMetadata,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import (
    AutoSearchJob,
    jobs_for_phase,
    reference_cache_key,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.plan import (
    ConditionPoint,
    SearchPhasePlan,
)


def _job(**overrides):
    values = {
        "phase": "coarse",
        "user_type_id": "green_hue_dominant_broad_bpm",
        "point": ConditionPoint(0.03, 1.0),
        "maximum_sessions": 24,
        "replicate_index": 0,
        "base_master_seed": 20260802,
        "arm": "experimental",
        "code_fingerprint": "a" * 64,
        "versions": AutoSearchVersionMetadata(),
    }
    values.update(overrides)
    return AutoSearchJob.create(**values)


def test_job_id_is_deterministic_sha256_of_canonical_body() -> None:
    first = _job()
    second = _job()
    assert first == second
    assert len(first.job_id) == 64
    assert AutoSearchJob(**first.to_dict()) == first


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("phase", "refine"),
        ("user_type_id", "flat_control"),
        ("point", ConditionPoint(0.08, 1.25)),
        ("maximum_sessions", 60),
        ("replicate_index", 1),
        ("arm", "reference"),
        ("code_fingerprint", "b" * 64),
    ),
)
def test_relevant_job_identity_fields_change_job_id(field, value) -> None:
    assert _job(**{field: value}).job_id != _job().job_id


def test_condition_does_not_change_paired_replicate_seed() -> None:
    first = _job(point=ConditionPoint(0.03, 0.5))
    second = _job(point=ConditionPoint(0.15, 1.5))
    assert first.replicate_master_seed == second.replicate_master_seed
    assert first.job_id != second.job_id


def test_replicate_index_changes_seed() -> None:
    assert (
        _job(replicate_index=0).replicate_master_seed
        != _job(replicate_index=1).replicate_master_seed
    )


def test_tampered_job_id_is_rejected() -> None:
    job = _job()
    with pytest.raises(ValueError, match="job ID"):
        replace(job, job_id="0" * 64)


def test_jobs_are_unique_and_sorted_by_job_id() -> None:
    phase = SearchPhasePlan(
        phase="coarse",
        phase_number=1,
        conditions=(ConditionPoint(0.03, 0.75), ConditionPoint(0.08, 1.25)),
        maximum_condition_count=2,
        maximum_sessions=4,
        replicate_count=2,
        user_type_ids=("green_hue_dominant_broad_bpm", "flat_control"),
    )
    jobs = jobs_for_phase(
        phase,
        base_master_seed=20260802,
        include_reference_arm=True,
        code_fingerprint="a" * 64,
        versions=AutoSearchVersionMetadata(),
    )
    assert len(jobs) == 12
    assert tuple(item.job_id for item in jobs) == tuple(sorted(item.job_id for item in jobs))
    assert len({item.job_id for item in jobs}) == len(jobs)


def test_reference_cache_key_ignores_condition_and_phase() -> None:
    first = _job(arm="reference", point=ConditionPoint(0.0, 1.0))
    second = _job(
        arm="reference",
        point=ConditionPoint(0.15, 1.5),
        phase="refine",
    )
    assert reference_cache_key(first) == reference_cache_key(second)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("user_type_id", "flat_control"),
        ("maximum_sessions", 60),
        ("replicate_index", 2),
        ("code_fingerprint", "b" * 64),
    ),
)
def test_reference_cache_key_changes_for_relevant_inputs(field, value) -> None:
    first = _job(arm="reference")
    second = _job(arm="reference", **{field: value})
    assert reference_cache_key(first) != reference_cache_key(second)


def test_reference_cache_key_rejects_experimental_job() -> None:
    with pytest.raises(ValueError, match="reference"):
        reference_cache_key(_job())
