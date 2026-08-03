"""Simulation-only hidden-landscape alignment diagnostics."""

from __future__ import annotations

import math

from symbiotic_sim_v2.virtual_user.stationary_landscape import (
    StationaryUserTypeProfile,
    circular_hue_distance,
    evaluate_stationary_preference,
)

from .config import RollingConvergenceConfig
from .records import RollingConvergenceRecord
from .truth_records import TruthAlignmentRecord


def _nearest_peak(
    profile: StationaryUserTypeProfile,
    hue_degree: float,
    blink_bpm: float,
) -> tuple[str, float]:
    candidates = tuple(
        (
            peak.peak_id,
            math.hypot(
                circular_hue_distance(hue_degree, peak.preferred_hue_degree)
                / peak.hue_sigma_degree,
                (blink_bpm - peak.preferred_blink_bpm) / peak.blink_sigma_bpm,
            ),
        )
        for peak in profile.peaks
    )
    if not candidates:
        raise ValueError("nearest peak is undefined for a flat landscape")
    return min(candidates, key=lambda item: (item[1], item[0]))


def evaluate_truth_alignment(
    convergence: RollingConvergenceRecord,
    profile: StationaryUserTypeProfile,
    config: RollingConvergenceConfig,
) -> TruthAlignmentRecord:
    """Compare a primary medoid to hidden truth without feeding the primary path."""

    if not isinstance(convergence, RollingConvergenceRecord):
        raise TypeError("convergence must be a RollingConvergenceRecord")
    if not isinstance(profile, StationaryUserTypeProfile):
        raise TypeError("profile must be a StationaryUserTypeProfile")
    if not isinstance(config, RollingConvergenceConfig):
        raise TypeError("config must be a RollingConvergenceConfig")
    global_maximum = max((peak.peak_weight for peak in profile.peaks), default=0.0)
    if not profile.peaks:
        return TruthAlignmentRecord(
            evaluated_at_session_index=convergence.evaluated_at_session_index,
            local_time_us=convergence.local_time_us,
            global_time_us=convergence.global_time_us,
            primary_converged=convergence.currently_converged,
            truth_classification="no_preference_control",
            preference_match_at_medoid=None,
            global_maximum_preference_match=0.0,
            response_gap=None,
            nearest_peak_id=None,
            distance_to_nearest_peak_center=None,
            medoid_hue_degree=convergence.medoid_hue_degree,
            medoid_blink_bpm=convergence.medoid_blink_bpm,
        )
    if not convergence.currently_converged:
        return TruthAlignmentRecord(
            evaluated_at_session_index=convergence.evaluated_at_session_index,
            local_time_us=convergence.local_time_us,
            global_time_us=convergence.global_time_us,
            primary_converged=False,
            truth_classification="not_converged",
            preference_match_at_medoid=None,
            global_maximum_preference_match=global_maximum,
            response_gap=None,
            nearest_peak_id=None,
            distance_to_nearest_peak_center=None,
            medoid_hue_degree=None,
            medoid_blink_bpm=None,
        )
    if convergence.medoid_hue_degree is None or convergence.medoid_blink_bpm is None:
        raise RuntimeError("converged record lost its medoid pattern")
    preference = evaluate_stationary_preference(
        profile,
        active=True,
        hue_degree=convergence.medoid_hue_degree,
        blink_bpm=convergence.medoid_blink_bpm,
    )
    gap = max(0.0, global_maximum - preference.preference_match)
    nearest_peak_id, nearest_distance = _nearest_peak(
        profile,
        convergence.medoid_hue_degree,
        convergence.medoid_blink_bpm,
    )
    classification = (
        "correct_convergence"
        if gap <= config.truth_response_gap_threshold
        else "stable_suboptimal"
    )
    return TruthAlignmentRecord(
        evaluated_at_session_index=convergence.evaluated_at_session_index,
        local_time_us=convergence.local_time_us,
        global_time_us=convergence.global_time_us,
        primary_converged=True,
        truth_classification=classification,
        preference_match_at_medoid=preference.preference_match,
        global_maximum_preference_match=global_maximum,
        response_gap=gap,
        nearest_peak_id=nearest_peak_id,
        distance_to_nearest_peak_center=nearest_distance,
        medoid_hue_degree=convergence.medoid_hue_degree,
        medoid_blink_bpm=convergence.medoid_blink_bpm,
    )


__all__ = ["evaluate_truth_alignment"]
