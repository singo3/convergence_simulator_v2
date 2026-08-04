"""Checksummed completed/failed job and reference-cache persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .checkpoint import atomic_write_json, atomic_write_text
from .config import REFERENCE_CACHE_SCHEMA_VERSION
from .job import AutoSearchJob, canonical_json, sha256_canonical


class JobStore:
    def __init__(self, run_directory: Path) -> None:
        self.run_directory = run_directory
        self.completed_directory = run_directory / "completed_jobs"
        self.failed_directory = run_directory / "failed_jobs"
        self.reference_directory = run_directory / "reference_cache"
        for path in (
            self.completed_directory,
            self.failed_directory,
            self.reference_directory,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, AutoSearchJob] = {}

    @property
    def jobs(self) -> tuple[AutoSearchJob, ...]:
        return tuple(self._jobs[key] for key in sorted(self._jobs))

    def register_jobs(self, jobs: tuple[AutoSearchJob, ...]) -> None:
        for job in jobs:
            existing = self._jobs.get(job.job_id)
            if existing is not None and existing != job:
                raise ValueError(f"job ID collision: {job.job_id}")
            self._jobs[job.job_id] = job
        lines = "".join(canonical_json(job.to_dict()) + "\n" for job in self.jobs)
        atomic_write_text(self.run_directory / "jobs.jsonl", lines)

    def load_jobs(self) -> tuple[AutoSearchJob, ...]:
        path = self.run_directory / "jobs.jsonl"
        loaded: list[AutoSearchJob] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                loaded.append(AutoSearchJob(**json.loads(line)))
        self.register_jobs(tuple(loaded))
        return self.jobs

    def _write_checked(self, path: Path, payload: dict[str, Any]) -> tuple[Path, str]:
        checksum = sha256_canonical(payload)
        atomic_write_json(path, {"payload": payload, "checksum": checksum})
        return path, checksum

    def write_completed(
        self,
        job: AutoSearchJob,
        payload: dict[str, Any],
    ) -> tuple[Path, str]:
        return self._write_checked(
            self.completed_directory / f"{job.job_id}.json",
            payload,
        )

    def write_failed(
        self,
        job: AutoSearchJob,
        payload: dict[str, Any],
    ) -> tuple[Path, str]:
        return self._write_checked(
            self.failed_directory / f"{job.job_id}.json",
            payload,
        )

    @staticmethod
    def read_checked(path: Path, *, expected_checksum: str | None = None) -> dict[str, Any]:
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if set(wrapper) != {"payload", "checksum"}:
            raise ValueError(f"invalid checksummed document: {path}")
        checksum = sha256_canonical(wrapper["payload"])
        if checksum != wrapper["checksum"]:
            raise ValueError(f"checksum mismatch: {path}")
        if expected_checksum is not None and checksum != expected_checksum:
            raise ValueError(f"checkpoint checksum mismatch: {path}")
        return wrapper["payload"]

    def write_reference(
        self,
        cache_key: str,
        *,
        code_fingerprint: str,
        payload: dict[str, Any],
    ) -> tuple[Path, str]:
        body = {
            "cache_key": cache_key,
            "code_fingerprint": code_fingerprint,
            "reference_result": payload,
            "schema_version": REFERENCE_CACHE_SCHEMA_VERSION,
        }
        return self._write_checked(self.reference_directory / f"{cache_key}.json", body)

    def read_reference(
        self,
        cache_key: str,
        *,
        code_fingerprint: str,
    ) -> dict[str, Any] | None:
        path = self.reference_directory / f"{cache_key}.json"
        if not path.exists():
            return None
        body = self.read_checked(path)
        if body.get("schema_version") != REFERENCE_CACHE_SCHEMA_VERSION:
            raise ValueError("reference cache schema mismatch")
        if body.get("code_fingerprint") != code_fingerprint:
            raise ValueError("reference cache code fingerprint mismatch")
        if body.get("cache_key") != cache_key:
            raise ValueError("reference cache key mismatch")
        return body["reference_result"]


__all__ = ["JobStore"]
