"""Atomic checkpoint, checksum, recovery, and lock tests."""

from __future__ import annotations

import json

import pytest

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.checkpoint import (
    AutoSearchCheckpoint,
    RunDirectoryLock,
    atomic_write_json,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    AutoSearchVersionMetadata,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import AutoSearchJob
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job_store import JobStore
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.plan import ConditionPoint


def _checkpoint() -> AutoSearchCheckpoint:
    return AutoSearchCheckpoint.create(
        run_id="run-1",
        current_phase="coarse",
        job_ids=("b", "a"),
        planned_session_runs=8,
        timestamp="2026-08-05T00:00:00+00:00",
    )


def _job() -> AutoSearchJob:
    return AutoSearchJob.create(
        phase="coarse",
        user_type_id="flat_control",
        point=ConditionPoint(0.03, 1.0),
        maximum_sessions=4,
        replicate_index=0,
        base_master_seed=1,
        arm="experimental",
        code_fingerprint="a" * 64,
        versions=AutoSearchVersionMetadata(),
    )


def test_initial_checkpoint_is_sorted_and_pending() -> None:
    checkpoint = _checkpoint()
    assert tuple(item.job_id for item in checkpoint.jobs) == ("a", "b")
    assert {item.status for item in checkpoint.jobs} == {"pending"}
    assert checkpoint.completed_session_runs == 0
    assert AutoSearchCheckpoint.from_dict(checkpoint.to_dict()) == checkpoint


@pytest.mark.parametrize(
    ("terminal", "path", "checksum"),
    (
        ("completed", "completed_jobs/a.json", "1" * 64),
        ("failed", "failed_jobs/a.json", "2" * 64),
        ("cancelled", None, None),
    ),
)
def test_running_transitions_to_terminal_states(terminal, path, checksum) -> None:
    running = _checkpoint().transition("a", "running")
    result = running.transition(
        "a",
        terminal,
        result_path=path,
        result_checksum=checksum,
        completed_session_delta=4 if terminal == "completed" else 0,
    )
    assert result.state_for("a").status == terminal
    assert result.state_for("a").attempts == 1
    assert result.completed_session_runs == (4 if terminal == "completed" else 0)


@pytest.mark.parametrize(
    ("source", "target"),
    (
        ("pending", "completed"),
        ("pending", "failed"),
        ("completed", "running"),
        ("failed", "completed"),
        ("cancelled", "completed"),
    ),
)
def test_invalid_checkpoint_transitions_are_rejected(source, target) -> None:
    checkpoint = _checkpoint()
    if source != "pending":
        checkpoint = checkpoint.transition("a", "running").transition("a", source)
    with pytest.raises(ValueError, match="invalid job transition"):
        checkpoint.transition("a", target)


def test_running_job_recovers_to_pending_without_losing_attempt_count() -> None:
    running = _checkpoint().transition("a", "running")
    recovered = running.recover_running()
    assert recovered.state_for("a").status == "pending"
    assert recovered.state_for("a").attempts == 1
    assert recovered.cancel_requested is False


def test_add_jobs_deduplicates_and_updates_budget() -> None:
    checkpoint = _checkpoint().add_jobs(("b", "c"), planned_session_runs=12)
    assert tuple(item.job_id for item in checkpoint.jobs) == ("a", "b", "c")
    assert checkpoint.planned_session_runs == 12


def test_atomic_json_write_leaves_no_temporary_file(tmp_path) -> None:
    path = tmp_path / "nested" / "checkpoint.json"
    atomic_write_json(path, {"value": 1})
    assert json.loads(path.read_text(encoding="utf-8")) == {"value": 1}
    assert not tuple(path.parent.glob("*.tmp"))


def test_run_lock_is_exclusive_and_existing_lock_is_not_deleted(tmp_path) -> None:
    first = RunDirectoryLock(tmp_path)
    second = RunDirectoryLock(tmp_path)
    first.acquire()
    with pytest.raises(RuntimeError, match="AUTO_SEARCH_LOCKED"):
        second.acquire()
    assert first.path.exists()
    first.release()
    assert not first.path.exists()


def test_preexisting_stale_lock_is_never_silently_removed(tmp_path) -> None:
    lock_path = tmp_path / ".auto_search.lock"
    lock_path.write_text('{"pid":999999,"created_at":"old"}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="old"):
        RunDirectoryLock(tmp_path).acquire()
    assert lock_path.exists()


def test_job_store_checksum_round_trip_and_corruption_detection(tmp_path) -> None:
    store = JobStore(tmp_path)
    job = _job()
    store.register_jobs((job,))
    path, checksum = store.write_completed(job, {"answer": 42})
    assert store.read_checked(path, expected_checksum=checksum) == {"answer": 42}
    wrapper = json.loads(path.read_text(encoding="utf-8"))
    wrapper["payload"]["answer"] = 43
    path.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        store.read_checked(path)


def test_reference_cache_validates_fingerprint_schema_and_checksum(tmp_path) -> None:
    store = JobStore(tmp_path)
    path, _checksum = store.write_reference(
        "cache",
        code_fingerprint="a" * 64,
        payload={"digest": "d"},
    )
    assert store.read_reference("cache", code_fingerprint="a" * 64) == {"digest": "d"}
    with pytest.raises(ValueError, match="fingerprint"):
        store.read_reference("cache", code_fingerprint="b" * 64)
    wrapper = json.loads(path.read_text(encoding="utf-8"))
    wrapper["checksum"] = "0" * 64
    path.write_text(json.dumps(wrapper), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        store.read_reference("cache", code_fingerprint="a" * 64)


def test_jobs_jsonl_load_rejects_tampered_identity(tmp_path) -> None:
    store = JobStore(tmp_path)
    store.register_jobs((_job(),))
    path = tmp_path / "jobs.jsonl"
    body = json.loads(path.read_text(encoding="utf-8"))
    body["sigma_multiplier"] = 1.25
    path.write_text(json.dumps(body) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="job ID"):
        JobStore(tmp_path).load_jobs()
