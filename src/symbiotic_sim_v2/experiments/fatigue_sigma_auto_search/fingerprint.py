"""Strict local code/spec fingerprint used for new runs and resume."""

from __future__ import annotations

import hashlib
import platform
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.config import (
    PROJECT_VERSION as STAGE_08A1_PROJECT_VERSION,
)

from .config import (
    AUTO_SEARCH_MODEL_VERSION,
    CODE_FINGERPRINT_VERSION,
    NORMATIVE_SPEC_PATH,
    NORMATIVE_SPEC_SHA256,
    NORMATIVE_SPEC_SIZE,
    PROJECT_VERSION,
)
from .job import sha256_canonical

AUTO_SEARCH_CODE_CHANGED = "AUTO_SEARCH_CODE_CHANGED"


class CodeFingerprintError(RuntimeError):
    """A stable-code precondition or resume fingerprint failed."""


def _git(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class CodeFingerprint:
    git_head_sha: str
    working_tree_clean: bool
    project_version: str
    package_version: str
    stage_08a1_project_version: str
    stage_08a1_experiment_version: str
    auto_search_version: str
    normative_spec_sha256: str
    normative_spec_size: int
    python_version: str
    platform: str
    implementation: str
    schema_version: str = CODE_FINGERPRINT_VERSION

    @property
    def digest(self) -> str:
        return sha256_canonical(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "fingerprint_digest": self.digest}

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> CodeFingerprint:
        payload = dict(values)
        expected_digest = payload.pop("fingerprint_digest", None)
        result = cls(**payload)
        if expected_digest is not None and expected_digest != result.digest:
            raise CodeFingerprintError(f"{AUTO_SEARCH_CODE_CHANGED}: digest mismatch")
        return result

    @classmethod
    def capture(
        cls,
        repo_root: Path,
        *,
        allow_dirty: bool = False,
    ) -> CodeFingerprint:
        repo_root = repo_root.resolve()
        status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
        clean = not status
        if not clean and not allow_dirty:
            raise CodeFingerprintError(f"{AUTO_SEARCH_CODE_CHANGED}: working tree is dirty")
        if not NORMATIVE_SPEC_PATH.is_file():
            raise CodeFingerprintError("SPEC_MISSING")
        size = NORMATIVE_SPEC_PATH.stat().st_size
        sha = _sha256_file(NORMATIVE_SPEC_PATH)
        if size != NORMATIVE_SPEC_SIZE or sha != NORMATIVE_SPEC_SHA256:
            raise CodeFingerprintError("SPEC_CHANGED")
        return cls(
            git_head_sha=_git(repo_root, "rev-parse", "HEAD"),
            working_tree_clean=clean,
            project_version=PROJECT_VERSION,
            package_version=__version__,
            stage_08a1_project_version=STAGE_08A1_PROJECT_VERSION,
            stage_08a1_experiment_version=(FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION),
            auto_search_version=AUTO_SEARCH_MODEL_VERSION,
            normative_spec_sha256=sha,
            normative_spec_size=size,
            python_version=platform.python_version(),
            platform=platform.platform(),
            implementation=platform.python_implementation(),
        )

    def require_match(self, other: CodeFingerprint) -> None:
        if not isinstance(other, CodeFingerprint) or self != other:
            raise CodeFingerprintError(f"{AUTO_SEARCH_CODE_CHANGED}: resume fingerprint differs")


__all__ = [
    "AUTO_SEARCH_CODE_CHANGED",
    "CodeFingerprint",
    "CodeFingerprintError",
]
