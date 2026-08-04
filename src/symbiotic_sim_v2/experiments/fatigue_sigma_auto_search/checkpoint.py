"""Atomic checkpoint state transitions and non-destructive run locking."""

from __future__ import annotations

import os
import platform
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import CHECKPOINT_SCHEMA_VERSION
from .job import canonical_json

JOB_STATUSES = ("pending", "running", "completed", "failed", "cancelled")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(path: Path, content: str) -> None:
    atomic_write_bytes(path, content.encode("utf-8"))


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, canonical_json(payload) + "\n")


@dataclass(frozen=True, slots=True)
class JobCheckpoint:
    job_id: str
    status: str = "pending"
    attempts: int = 0
    result_path: str | None = None
    result_checksum: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in JOB_STATUSES:
            raise ValueError(f"unknown job status: {self.status}")
        if isinstance(self.attempts, bool) or not isinstance(self.attempts, int):
            raise TypeError("attempts must be an integer")
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "attempts": self.attempts,
            "result_path": self.result_path,
            "result_checksum": self.result_checksum,
            "error": self.error,
        }


@dataclass(frozen=True, slots=True)
class AutoSearchCheckpoint:
    run_id: str
    current_phase: str
    jobs: tuple[JobCheckpoint, ...]
    completed_session_runs: int
    planned_session_runs: int
    cancel_requested: bool
    created_at: str
    updated_at: str
    schema_version: str = CHECKPOINT_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        run_id: str,
        current_phase: str,
        job_ids: tuple[str, ...],
        planned_session_runs: int,
        timestamp: str | None = None,
    ) -> AutoSearchCheckpoint:
        now = timestamp or utc_now()
        return cls(
            run_id=run_id,
            current_phase=current_phase,
            jobs=tuple(JobCheckpoint(job_id) for job_id in sorted(job_ids)),
            completed_session_runs=0,
            planned_session_runs=planned_session_runs,
            cancel_requested=False,
            created_at=now,
            updated_at=now,
        )

    def __post_init__(self) -> None:
        if self.schema_version != CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("checkpoint schema mismatch")
        ids = tuple(item.job_id for item in self.jobs)
        if tuple(sorted(ids)) != ids or len(set(ids)) != len(ids):
            raise ValueError("checkpoint jobs must be uniquely sorted")

    def state_for(self, job_id: str) -> JobCheckpoint:
        try:
            return next(item for item in self.jobs if item.job_id == job_id)
        except StopIteration as exc:
            raise KeyError(job_id) from exc

    def add_jobs(
        self,
        job_ids: tuple[str, ...],
        *,
        planned_session_runs: int,
    ) -> AutoSearchCheckpoint:
        existing = {item.job_id: item for item in self.jobs}
        for job_id in job_ids:
            existing.setdefault(job_id, JobCheckpoint(job_id))
        return replace(
            self,
            jobs=tuple(existing[key] for key in sorted(existing)),
            planned_session_runs=planned_session_runs,
            updated_at=utc_now(),
        )

    def transition(
        self,
        job_id: str,
        status: str,
        *,
        result_path: str | None = None,
        result_checksum: str | None = None,
        error: str | None = None,
        completed_session_delta: int = 0,
    ) -> AutoSearchCheckpoint:
        if status not in JOB_STATUSES:
            raise ValueError(f"unknown job status: {status}")
        current = self.state_for(job_id)
        allowed = {
            "pending": {"running", "cancelled"},
            "running": {"pending", "completed", "failed", "cancelled"},
            "failed": {"pending"},
            "cancelled": {"pending"},
            "completed": set(),
        }
        if status not in allowed[current.status]:
            raise ValueError(f"invalid job transition {current.status}->{status}")
        updated = JobCheckpoint(
            job_id=job_id,
            status=status,
            attempts=current.attempts + (status == "running"),
            result_path=result_path,
            result_checksum=result_checksum,
            error=error,
        )
        jobs = tuple(updated if item.job_id == job_id else item for item in self.jobs)
        return replace(
            self,
            jobs=jobs,
            completed_session_runs=(self.completed_session_runs + completed_session_delta),
            updated_at=utc_now(),
        )

    def recover_running(self) -> AutoSearchCheckpoint:
        jobs = tuple(
            replace(item, status="pending", result_path=None, result_checksum=None)
            if item.status == "running"
            else item
            for item in self.jobs
        )
        return replace(self, jobs=jobs, cancel_requested=False, updated_at=utc_now())

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "current_phase": self.current_phase,
            "jobs": [item.to_dict() for item in self.jobs],
            "completed_session_runs": self.completed_session_runs,
            "planned_session_runs": self.planned_session_runs,
            "cancel_requested": self.cancel_requested,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> AutoSearchCheckpoint:
        expected = {
            "run_id",
            "current_phase",
            "jobs",
            "completed_session_runs",
            "planned_session_runs",
            "cancel_requested",
            "created_at",
            "updated_at",
            "schema_version",
        }
        if set(values) != expected:
            raise ValueError("checkpoint fields differ")
        jobs = values["jobs"]
        if not isinstance(jobs, list):
            raise TypeError("checkpoint jobs must be a list")
        return cls(
            **{key: value for key, value in values.items() if key != "jobs"},
            jobs=tuple(JobCheckpoint(**item) for item in jobs),
        )


class RunDirectoryLock:
    """Exclusive lock; an existing lock is diagnostic evidence, never removed."""

    def __init__(self, run_directory: Path) -> None:
        self.path = run_directory / ".auto_search.lock"
        self._owned = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical_json(
            {
                "pid": os.getpid(),
                "host": platform.node(),
                "created_at": utc_now(),
            }
        ).encode("utf-8")
        try:
            descriptor = os.open(
                self.path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError as exc:
            existing = self.path.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(
                "AUTO_SEARCH_LOCKED: existing lock was not removed: " + existing
            ) from exc
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        self._owned = True

    def release(self) -> None:
        if self._owned:
            self.path.unlink(missing_ok=False)
            self._owned = False

    def __enter__(self) -> RunDirectoryLock:
        self.acquire()
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()


__all__ = [
    "AutoSearchCheckpoint",
    "JobCheckpoint",
    "RunDirectoryLock",
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_text",
    "utc_now",
]
