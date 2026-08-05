"""Strict local code/spec fingerprint for Stage 8A.3 checkpoint resume."""

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
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    AUTO_SEARCH_MODEL_VERSION,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.config import (
    PROJECT_VERSION as STAGE_08A2_PROJECT_VERSION,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import sha256_canonical

from .config import (
    PROJECT_VERSION,
    VALIDATION_CODE_FINGERPRINT_VERSION,
    VALIDATION_MODEL_VERSION,
)

NORMATIVE_SPEC_PATH = Path(
    "/Users/sawadashingo/ONTELOPE/21_RICOH/共同研究/自律確認MVP/"
    "symbiotic-digital-life-signal-loop-concept_v2.0.md"
)
NORMATIVE_SPEC_SIZE = 65_759
NORMATIVE_SPEC_SHA256 = (
    "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"
)
VALIDATION_CODE_CHANGED = "VALIDATION_CODE_CHANGED"


class ValidationCodeFingerprintError(RuntimeError):
    """The normative spec or local code identity differs from the checkpoint."""


def _git(repo_root: Path, *arguments: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=text,
    )
    return completed.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _working_tree_digest(repo_root: Path, status: str) -> str:
    digest = hashlib.sha256()
    digest.update(status.encode("utf-8"))
    diff = _git(repo_root, "diff", "--binary", "HEAD", text=False)
    assert isinstance(diff, bytes)
    digest.update(diff)
    untracked = _git(
        repo_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
        text=False,
    )
    assert isinstance(untracked, bytes)
    for encoded_path in untracked.split(b"\0"):
        if not encoded_path:
            continue
        relative_path = encoded_path.decode("utf-8", errors="surrogateescape")
        path = repo_root / relative_path
        if path.is_file():
            digest.update(encoded_path)
            digest.update(path.read_bytes())
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ValidationCodeFingerprint:
    git_head_sha: str
    working_tree_clean: bool
    working_tree_digest: str
    project_version: str
    package_version: str
    stage_08a1_project_version: str
    stage_08a1_experiment_version: str
    stage_08a2_project_version: str
    stage_08a2_model_version: str
    validation_model_version: str
    normative_spec_sha256: str
    normative_spec_size: int
    python_version: str
    platform: str
    implementation: str
    schema_version: str = VALIDATION_CODE_FINGERPRINT_VERSION

    @property
    def digest(self) -> str:
        return sha256_canonical(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "fingerprint_digest": self.digest}

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> ValidationCodeFingerprint:
        payload = dict(values)
        expected = payload.pop("fingerprint_digest", None)
        result = cls(**payload)
        if expected is not None and expected != result.digest:
            raise ValidationCodeFingerprintError(
                f"{VALIDATION_CODE_CHANGED}: fingerprint digest mismatch"
            )
        return result

    @classmethod
    def capture(
        cls,
        repo_root: Path,
        *,
        allow_dirty: bool = False,
    ) -> ValidationCodeFingerprint:
        root = repo_root.resolve()
        status_value = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
        assert isinstance(status_value, str)
        clean = not status_value
        if not clean and not allow_dirty:
            raise ValidationCodeFingerprintError(
                f"{VALIDATION_CODE_CHANGED}: working tree is dirty"
            )
        if not NORMATIVE_SPEC_PATH.is_file():
            raise ValidationCodeFingerprintError("SPEC_MISSING")
        size = NORMATIVE_SPEC_PATH.stat().st_size
        sha = _sha256_file(NORMATIVE_SPEC_PATH)
        if size != NORMATIVE_SPEC_SIZE or sha != NORMATIVE_SPEC_SHA256:
            raise ValidationCodeFingerprintError("SPEC_CHANGED")
        head = _git(root, "rev-parse", "HEAD")
        assert isinstance(head, str)
        return cls(
            git_head_sha=head,
            working_tree_clean=clean,
            working_tree_digest=_working_tree_digest(root, status_value),
            project_version=PROJECT_VERSION,
            package_version=__version__,
            stage_08a1_project_version=STAGE_08A1_PROJECT_VERSION,
            stage_08a1_experiment_version=FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION,
            stage_08a2_project_version=STAGE_08A2_PROJECT_VERSION,
            stage_08a2_model_version=AUTO_SEARCH_MODEL_VERSION,
            validation_model_version=VALIDATION_MODEL_VERSION,
            normative_spec_sha256=sha,
            normative_spec_size=size,
            python_version=platform.python_version(),
            platform=platform.platform(),
            implementation=platform.python_implementation(),
        )

    def require_match(self, other: ValidationCodeFingerprint) -> None:
        if not isinstance(other, ValidationCodeFingerprint) or self != other:
            raise ValidationCodeFingerprintError(
                f"{VALIDATION_CODE_CHANGED}: resume fingerprint differs"
            )


__all__ = [
    "NORMATIVE_SPEC_PATH",
    "NORMATIVE_SPEC_SHA256",
    "NORMATIVE_SPEC_SIZE",
    "VALIDATION_CODE_CHANGED",
    "ValidationCodeFingerprint",
    "ValidationCodeFingerprintError",
]
