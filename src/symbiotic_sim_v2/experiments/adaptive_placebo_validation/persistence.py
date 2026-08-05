"""Checksummed jobs and an atomic Stage 8A.3 checkpoint over Stage 8A.2 I/O."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.checkpoint import (
    RunDirectoryLock,
    atomic_write_json,
    utc_now,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import sha256_canonical
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job_store import JobStore

from .config import VALIDATION_CHECKPOINT_VERSION


@dataclass(slots=True)
class ValidationCheckpoint:
    run_id: str
    planned_session_runs: int
    completed_session_runs: int = 0
    phase: str = "autonomous"
    completed_jobs: dict[str, dict[str, str]] = field(default_factory=dict)
    donor_sequence_checksums: dict[str, str] = field(default_factory=dict)
    yoke_maps_completed: tuple[str, ...] = ()
    analysis_complete: bool = False
    report_complete: bool = False
    cancel_requested: bool = False
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    schema_version: str = VALIDATION_CHECKPOINT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != VALIDATION_CHECKPOINT_VERSION:
            raise ValueError("validation checkpoint schema mismatch")
        if self.completed_session_runs > self.planned_session_runs:
            raise ValueError("completed session count exceeds plan")
        if len(set(self.yoke_maps_completed)) != len(self.yoke_maps_completed):
            raise ValueError("completed yoke-map scopes must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "planned_session_runs": self.planned_session_runs,
            "completed_session_runs": self.completed_session_runs,
            "phase": self.phase,
            "completed_jobs": dict(sorted(self.completed_jobs.items())),
            "donor_sequence_checksums": dict(
                sorted(self.donor_sequence_checksums.items())
            ),
            "yoke_maps_completed": list(sorted(self.yoke_maps_completed)),
            "analysis_complete": self.analysis_complete,
            "report_complete": self.report_complete,
            "cancel_requested": self.cancel_requested,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ValidationCheckpoint:
        expected = {
            "run_id",
            "planned_session_runs",
            "completed_session_runs",
            "phase",
            "completed_jobs",
            "donor_sequence_checksums",
            "yoke_maps_completed",
            "analysis_complete",
            "report_complete",
            "cancel_requested",
            "created_at",
            "updated_at",
            "schema_version",
        }
        if set(values) != expected:
            raise ValueError("validation checkpoint fields differ")
        normalized = dict(values)
        normalized["completed_jobs"] = dict(normalized["completed_jobs"])
        normalized["donor_sequence_checksums"] = dict(
            normalized["donor_sequence_checksums"]
        )
        normalized["yoke_maps_completed"] = tuple(
            normalized["yoke_maps_completed"]
        )
        return cls(**normalized)


class ValidationStore:
    def __init__(self, run_directory: Path) -> None:
        self.run_directory = run_directory
        self.completed_directory = run_directory / "completed_jobs"
        self.failed_directory = run_directory / "failed_jobs"
        self.donor_directory = run_directory / "donor_sequences"
        for directory in (
            self.completed_directory,
            self.failed_directory,
            self.donor_directory,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _filename(identity: str) -> str:
        return sha256_canonical(identity) + ".json"

    @staticmethod
    def _write_checked(path: Path, payload: Any) -> tuple[Path, str]:
        checksum = sha256_canonical(payload)
        atomic_write_json(path, {"payload": payload, "checksum": checksum})
        return path, checksum

    @staticmethod
    def read_checked(path: Path, expected_checksum: str | None = None) -> Any:
        return JobStore.read_checked(path, expected_checksum=expected_checksum)

    def write_completed(self, job_id: str, payload: Any) -> tuple[Path, str]:
        return self._write_checked(
            self.completed_directory / self._filename(job_id),
            payload,
        )

    def write_failed(self, job_id: str, payload: Any) -> tuple[Path, str]:
        return self._write_checked(
            self.failed_directory / self._filename(job_id),
            payload,
        )

    def write_donor_sequence(self, identity: str, payload: Any) -> tuple[Path, str]:
        return self._write_checked(
            self.donor_directory / self._filename(identity),
            payload,
        )

    def read_donor_sequence(self, identity: str, expected_checksum: str) -> Any:
        return self.read_checked(
            self.donor_directory / self._filename(identity),
            expected_checksum=expected_checksum,
        )

    def read_completed(
        self,
        checkpoint: ValidationCheckpoint,
        job_id: str,
    ) -> Any:
        record = checkpoint.completed_jobs[job_id]
        path = self.run_directory / record["path"]
        return self.read_checked(path, record["checksum"])


def load_checkpoint(path: Path) -> ValidationCheckpoint:
    return ValidationCheckpoint.from_dict(json.loads(path.read_text(encoding="utf-8")))


def write_checkpoint(path: Path, checkpoint: ValidationCheckpoint) -> None:
    checkpoint.updated_at = utc_now()
    atomic_write_json(path, checkpoint.to_dict())


__all__ = [
    "RunDirectoryLock",
    "ValidationCheckpoint",
    "ValidationStore",
    "load_checkpoint",
    "write_checkpoint",
]
