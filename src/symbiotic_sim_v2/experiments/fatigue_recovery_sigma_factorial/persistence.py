"""Stage 8A.3.1 identity over the reused atomic Stage 8A.3 persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from symbiotic_sim_v2 import __version__
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.fingerprint import (
    ValidationCodeFingerprint,
    ValidationCodeFingerprintError,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.persistence import (
    RunDirectoryLock,
    ValidationCheckpoint,
    ValidationStore,
    load_checkpoint,
    write_checkpoint,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import sha256_canonical

from .conditions import PROJECT_VERSION, VALIDATION_MODEL_VERSION
from .config import FACTORIAL_CODE_FINGERPRINT_VERSION

FACTORIAL_CODE_CHANGED = "FACTORIAL_VALIDATION_CODE_CHANGED"


@dataclass(frozen=True, slots=True)
class FactorialCodeFingerprint:
    reused_stage08a3_fingerprint: dict[str, Any]
    project_version: str
    package_version: str
    validation_model_version: str
    schema_version: str = FACTORIAL_CODE_FINGERPRINT_VERSION

    def __post_init__(self) -> None:
        ValidationCodeFingerprint.from_dict(dict(self.reused_stage08a3_fingerprint))
        expected = {
            "project_version": PROJECT_VERSION,
            "package_version": PROJECT_VERSION,
            "validation_model_version": VALIDATION_MODEL_VERSION,
            "schema_version": FACTORIAL_CODE_FINGERPRINT_VERSION,
        }
        for name, value in expected.items():
            if getattr(self, name) != value:
                raise ValidationCodeFingerprintError(
                    f"{FACTORIAL_CODE_CHANGED}: {name} must be {value}"
                )

    @property
    def digest(self) -> str:
        return sha256_canonical(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "fingerprint_digest": self.digest}

    @classmethod
    def capture(
        cls,
        repo_root: Path,
        *,
        allow_dirty: bool = False,
    ) -> FactorialCodeFingerprint:
        base = ValidationCodeFingerprint.capture(repo_root, allow_dirty=allow_dirty)
        return cls(
            reused_stage08a3_fingerprint=base.to_dict(),
            project_version=PROJECT_VERSION,
            package_version=__version__,
            validation_model_version=VALIDATION_MODEL_VERSION,
        )

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> FactorialCodeFingerprint:
        payload = dict(values)
        expected_digest = payload.pop("fingerprint_digest", None)
        expected_fields = {field.name for field in fields(cls)}
        if set(payload) != expected_fields:
            raise ValidationCodeFingerprintError(
                f"{FACTORIAL_CODE_CHANGED}: fingerprint fields differ"
            )
        result = cls(**payload)
        if expected_digest is not None and expected_digest != result.digest:
            raise ValidationCodeFingerprintError(
                f"{FACTORIAL_CODE_CHANGED}: fingerprint digest mismatch"
            )
        return result

    def require_match(self, other: FactorialCodeFingerprint) -> None:
        if not isinstance(other, FactorialCodeFingerprint) or self != other:
            raise ValidationCodeFingerprintError(
                f"{FACTORIAL_CODE_CHANGED}: resume fingerprint differs"
            )


__all__ = [
    "FACTORIAL_CODE_CHANGED",
    "FactorialCodeFingerprint",
    "RunDirectoryLock",
    "ValidationCheckpoint",
    "ValidationCodeFingerprintError",
    "ValidationStore",
    "load_checkpoint",
    "write_checkpoint",
]
