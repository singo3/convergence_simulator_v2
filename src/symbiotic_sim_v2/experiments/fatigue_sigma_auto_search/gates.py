"""Transparent coarse and balanced robust candidate gates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .config import CandidateGateConfig


@dataclass(frozen=True, slots=True)
class GateResult:
    candidate_id: str
    passed: bool
    blockers: tuple[str, ...]
    gate_kind: str
    gate_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "passed": self.passed,
            "blockers": list(self.blockers),
            "gate_kind": self.gate_kind,
            "gate_version": self.gate_version,
        }


def _maximum(
    summary: Mapping[str, Any],
    field: str,
    threshold: float,
    blockers: list[str],
) -> None:
    value = summary.get(field)
    if value is None:
        blockers.append(f"{field}:missing")
    elif float(value) > threshold:
        blockers.append(f"{field}:{value}>{threshold}")


def _minimum(
    summary: Mapping[str, Any],
    field: str,
    threshold: float,
    blockers: list[str],
    *,
    exclusive: bool = False,
) -> None:
    value = summary.get(field)
    if value is None:
        blockers.append(f"{field}:missing")
    elif float(value) <= threshold if exclusive else float(value) < threshold:
        operator = "<=" if exclusive else "<"
        blockers.append(f"{field}:{value}{operator}{threshold}")


def evaluate_candidate_gate(
    summary: Mapping[str, Any],
    config: CandidateGateConfig,
    *,
    coarse: bool = False,
) -> GateResult:
    blockers: list[str] = []
    if coarse:
        _maximum(
            summary,
            "failed_replicate_rate",
            config.coarse_failed_replicate_rate_max,
            blockers,
        )
        _minimum(
            summary,
            "valid_session_rate",
            config.coarse_valid_session_rate_min,
            blockers,
        )
        _maximum(
            summary,
            "flat_spurious_structure_rate",
            config.coarse_flat_spurious_structure_rate_max,
            blockers,
        )
        _maximum(
            summary,
            "W_ceiling_blocked_rate",
            config.coarse_w_ceiling_blocked_rate_max,
            blockers,
        )
        _minimum(
            summary,
            "mean_nonflat_correct_structure_rate",
            config.coarse_mean_nonflat_correct_structure_rate_min_exclusive,
            blockers,
            exclusive=True,
        )
        kind = "coarse"
        version = config.coarse_version
    else:
        _maximum(
            summary,
            "failed_replicate_rate",
            config.failed_replicate_rate_max,
            blockers,
        )
        _minimum(
            summary,
            "valid_session_rate",
            config.valid_session_rate_min,
            blockers,
        )
        _maximum(
            summary,
            "flat_spurious_structure_rate",
            config.flat_spurious_structure_rate_max,
            blockers,
        )
        _maximum(
            summary,
            "flat_mechanical_rotation_warning_rate",
            config.flat_mechanical_rotation_warning_rate_max,
            blockers,
        )
        _maximum(
            summary,
            "W_ceiling_blocked_rate",
            config.w_ceiling_blocked_rate_max,
            blockers,
        )
        _minimum(
            summary,
            "worst_nonflat_correct_structure_rate",
            config.worst_nonflat_correct_structure_rate_min,
            blockers,
        )
        _maximum(
            summary,
            "mean_nonflat_diffuse_rate",
            config.mean_nonflat_diffuse_rate_max,
            blockers,
        )
        kind = "balanced_robust"
        version = config.version
    return GateResult(
        candidate_id=str(summary["candidate_id"]),
        passed=not blockers,
        blockers=tuple(blockers),
        gate_kind=kind,
        gate_version=version,
    )


def evaluate_all_gates(
    summaries: tuple[Mapping[str, Any], ...],
    config: CandidateGateConfig,
    *,
    coarse: bool = False,
) -> dict[str, GateResult]:
    return {
        str(item["candidate_id"]): evaluate_candidate_gate(
            item,
            config,
            coarse=coarse,
        )
        for item in summaries
    }


__all__ = ["GateResult", "evaluate_all_gates", "evaluate_candidate_gate"]
