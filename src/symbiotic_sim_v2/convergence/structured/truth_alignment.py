"""Simulation-only Stage 8A.1 hidden-truth alignment, isolated from primary paths."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    StationaryUserTypeProfileV2,
    evaluate_stationary_preference_v2,
    normalized_peak_distance,
)

from .config import StructuredConvergenceConfig
from .records import StructuredConvergenceRecord, StructuredSessionObservation

STRUCTURED_TRUTH_ALIGNMENT_VERSION = "structured_truth_alignment_v0_1"
TRUTH_CLASSIFICATIONS_V2 = frozenset(
    {
        "correct_structure",
        "partially_correct_structure",
        "stable_suboptimal_structure",
        "spurious_structure_in_flat_control",
        "not_converged",
        "not_applicable",
    }
)


@dataclass(frozen=True, slots=True)
class CommittedPreferenceMatch:
    session_index: int
    holder_id: str
    hue_degree: float
    blink_bpm: float
    preference_match: float
    winning_peak_id: str | None
    high_preference_hit: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PeakHitCount:
    peak_id: str
    hit_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class StructuredTruthAlignmentRecord:
    expected_structure: str
    observed_structure: str
    structure_mode_match: bool | None
    truth_classification: str
    recent_valid_session_indices: tuple[int, ...]
    recent_high_preference_hit_count: int
    recent_high_preference_hit_rate: float
    preference_match_at_committed_patterns: tuple[CommittedPreferenceMatch, ...]
    expected_dominant_life_match: bool | None
    expected_common_bpm_gap: float | None
    expected_attractor_coverage_count: int
    expected_attractor_coverage_rate: float | None
    peak_hit_count_by_peak: tuple[PeakHitCount, ...]
    weighted_secondary_attractor_present: bool | None
    flat_control_spurious_structure_flag: bool
    version: str = STRUCTURED_TRUTH_ALIGNMENT_VERSION

    def __post_init__(self) -> None:
        if self.truth_classification not in TRUTH_CLASSIFICATIONS_V2:
            raise ValueError("truth_classification is not recognized")
        if self.version != STRUCTURED_TRUTH_ALIGNMENT_VERSION:
            raise ValueError(f"version must be {STRUCTURED_TRUTH_ALIGNMENT_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _structure_mode_match(
    record: StructuredConvergenceRecord,
    profile: StationaryUserTypeProfileV2,
) -> bool | None:
    expected = profile.expected_structure
    if expected == "no_preference":
        return None
    if expected == "life_dominant":
        return record.life_dominant_converged
    if expected == "bpm_common":
        return record.bpm_common_converged
    if expected == "single_life_pattern":
        return record.life_dominant_converged and record.bpm_common_converged
    if expected == "life_specific_multi_attractor_equal":
        return record.three_attractor_converged
    if expected == "life_specific_multi_attractor_weighted":
        return record.multi_attractor_converged
    raise RuntimeError("validated profile carries an unknown expected structure")


def _flat_spurious(
    record: StructuredConvergenceRecord,
    config: StructuredConvergenceConfig,
) -> bool:
    mechanical = record.mechanical_rotation
    strong_rotation = bool(
        (
            mechanical.three_session_window_count >= config.mechanical_warning_minimum_windows
            and max(
                mechanical.three_distinct_life_window_rate,
                mechanical.immediate_return_rate,
            )
            >= config.mechanical_warning_rate_threshold
        )
        or (
            mechanical.four_session_window_count >= config.mechanical_warning_minimum_windows
            and mechanical.three_life_cycle_rate >= config.mechanical_warning_rate_threshold
        )
    )
    return bool(
        record.life_dominant_converged
        or record.bpm_common_converged
        or record.multi_attractor_converged
        or strong_rotation
    )


def evaluate_structured_truth_alignment(
    observations: tuple[StructuredSessionObservation, ...],
    record: StructuredConvergenceRecord,
    profile: StationaryUserTypeProfileV2,
    config: StructuredConvergenceConfig | None = None,
) -> StructuredTruthAlignmentRecord:
    """Read hidden peaks only after the observable diagnostic is complete."""

    selected_config = StructuredConvergenceConfig() if config is None else config
    if not isinstance(record, StructuredConvergenceRecord):
        raise TypeError("record must be a StructuredConvergenceRecord")
    if not isinstance(profile, StationaryUserTypeProfileV2):
        raise TypeError("profile must be a StationaryUserTypeProfileV2")
    if not isinstance(selected_config, StructuredConvergenceConfig):
        raise TypeError("config must be a StructuredConvergenceConfig")
    if any(not isinstance(item, StructuredSessionObservation) for item in observations):
        raise TypeError("observations must contain StructuredSessionObservation values")
    recent = tuple(item for item in observations if item.valid_for_convergence)[
        -selected_config.truth_recent_window_sessions :
    ]
    global_maximum = max((peak.peak_weight for peak in profile.peaks), default=0.0)
    matches: list[CommittedPreferenceMatch] = []
    for item in recent:
        assert item.holder_id is not None
        assert item.hue_degree is not None
        assert item.blink_bpm is not None
        preference = evaluate_stationary_preference_v2(
            profile,
            active=True,
            hue_degree=item.hue_degree,
            blink_bpm=item.blink_bpm,
        )
        matches.append(
            CommittedPreferenceMatch(
                session_index=item.session_index,
                holder_id=item.holder_id,
                hue_degree=item.hue_degree,
                blink_bpm=item.blink_bpm,
                preference_match=preference.preference_match,
                winning_peak_id=preference.winning_peak_id,
                high_preference_hit=(
                    bool(profile.peaks)
                    and global_maximum - preference.preference_match
                    <= selected_config.truth_response_gap_threshold
                ),
            )
        )
    peak_hits = tuple(
        PeakHitCount(
            peak_id=peak.peak_id,
            hit_count=sum(
                normalized_peak_distance(
                    peak,
                    hue_degree=item.hue_degree,
                    blink_bpm=item.blink_bpm,
                )
                <= selected_config.truth_peak_hit_radius
                for item in recent
            ),
        )
        for peak in profile.peaks
    )
    coverage_count = sum(item.hit_count > 0 for item in peak_hits)
    coverage_rate = None if not peak_hits else coverage_count / len(peak_hits)
    dominant_match = (
        None
        if profile.expected_dominant_life_id is None
        else record.life_dominance.dominant_life_id == profile.expected_dominant_life_id
    )
    expected_common_peak = next(
        (
            peak
            for peak in profile.peaks
            if profile.expected_structure == "bpm_common" and peak.bpm_axis_mode == "gaussian"
        ),
        None,
    )
    common_gap = (
        None
        if expected_common_peak is None or record.bpm_common.medoid_bpm is None
        else abs(
            record.bpm_common.medoid_bpm - expected_common_peak.preferred_blink_bpm  # type: ignore[operator]
        )
    )
    weighted_secondary = (
        None
        if profile.expected_structure != "life_specific_multi_attractor_weighted"
        else any(
            item.valid_attractor and item.life_id in {"life-red", "life-blue"}
            for item in record.multi_attractor.life_attractors
        )
    )
    mode_match = _structure_mode_match(record, profile)
    flat_spurious = profile.expected_structure == "no_preference" and _flat_spurious(
        record,
        selected_config,
    )
    has_structure = any(
        (
            record.life_dominant_converged,
            record.bpm_common_converged,
            record.multi_attractor_converged,
        )
    )
    expected_coverage = min(profile.expected_attractor_count or 0, len(profile.peaks))
    truth_constraints_match = bool(
        (dominant_match is not False)
        and coverage_count >= expected_coverage
        and (common_gap is None or common_gap <= selected_config.bpm_maximum_range)
        and (weighted_secondary is not False)
    )
    if profile.expected_structure == "no_preference":
        classification = "spurious_structure_in_flat_control" if flat_spurious else "not_applicable"
    elif not has_structure:
        classification = "not_converged"
    elif mode_match and truth_constraints_match:
        classification = "correct_structure"
    elif coverage_count > 0:
        classification = "partially_correct_structure"
    else:
        classification = "stable_suboptimal_structure"
    high_count = sum(item.high_preference_hit for item in matches)
    return StructuredTruthAlignmentRecord(
        expected_structure=profile.expected_structure,
        observed_structure=record.summary_classification,
        structure_mode_match=mode_match,
        truth_classification=classification,
        recent_valid_session_indices=tuple(item.session_index for item in recent),
        recent_high_preference_hit_count=high_count,
        recent_high_preference_hit_rate=0.0 if not matches else high_count / len(matches),
        preference_match_at_committed_patterns=tuple(matches),
        expected_dominant_life_match=dominant_match,
        expected_common_bpm_gap=common_gap,
        expected_attractor_coverage_count=coverage_count,
        expected_attractor_coverage_rate=coverage_rate,
        peak_hit_count_by_peak=peak_hits,
        weighted_secondary_attractor_present=weighted_secondary,
        flat_control_spurious_structure_flag=flat_spurious,
    )


__all__ = [
    "CommittedPreferenceMatch",
    "PeakHitCount",
    "STRUCTURED_TRUTH_ALIGNMENT_VERSION",
    "TRUTH_CLASSIFICATIONS_V2",
    "StructuredTruthAlignmentRecord",
    "evaluate_structured_truth_alignment",
]
