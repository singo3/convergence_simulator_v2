"""Stationary maximum-weighted-peak evaluator with no session context."""

from __future__ import annotations

import math

from .config import StationaryUserTypeProfile
from .peak import evaluate_peak_match
from .records import StationaryPeakMatch, StationaryPreferenceMatch


def _physical_number(name: str, value: object, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    if not minimum <= converted <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return converted


def evaluate_stationary_preference(
    profile: StationaryUserTypeProfile,
    *,
    active: bool,
    hue_degree: object | None,
    blink_bpm: object | None,
) -> StationaryPreferenceMatch:
    """Evaluate only physical light against one run-stationary landscape."""

    if not isinstance(profile, StationaryUserTypeProfile):
        raise TypeError("profile must be a StationaryUserTypeProfile")
    if not isinstance(active, bool):
        raise TypeError("active must be boolean")
    if not active:
        if hue_degree is not None or blink_bpm is not None:
            raise ValueError("inactive preference input cannot carry Hue or BPM")
        return StationaryPreferenceMatch(
            active=False,
            hue_degree=None,
            blink_bpm=None,
            preference_match=0.0,
            winning_peak_id=None,
            winning_hue_match=None,
            winning_bpm_match=None,
            peak_matches=(),
            landscape_version=profile.landscape_version,
            combination_version=profile.multi_peak_combination_version,
        )
    if hue_degree is None or blink_bpm is None:
        raise ValueError("active preference input requires Hue and BPM")
    hue = _physical_number("hue_degree", hue_degree, 0.0, 360.0)
    bpm = _physical_number("blink_bpm", blink_bpm, 10.0, 165.0)
    matches = tuple(
        StationaryPeakMatch(
            peak_id=peak.peak_id,
            hue_distance_degree=values[0],
            hue_match=values[1],
            blink_bpm_distance=values[2],
            bpm_match=values[3],
            weighted_match=values[4],
        )
        for peak in profile.peaks
        for values in (evaluate_peak_match(peak, hue_degree=hue, blink_bpm=bpm),)
    )
    if not matches:
        return StationaryPreferenceMatch(
            active=True,
            hue_degree=hue,
            blink_bpm=bpm,
            preference_match=0.0,
            winning_peak_id=None,
            winning_hue_match=None,
            winning_bpm_match=None,
            peak_matches=(),
            landscape_version=profile.landscape_version,
            combination_version=profile.multi_peak_combination_version,
        )
    winner = min(matches, key=lambda match: (-match.weighted_match, match.peak_id))
    return StationaryPreferenceMatch(
        active=True,
        hue_degree=hue,
        blink_bpm=bpm,
        preference_match=winner.weighted_match,
        winning_peak_id=winner.peak_id,
        winning_hue_match=winner.hue_match,
        winning_bpm_match=winner.bpm_match,
        peak_matches=matches,
        landscape_version=profile.landscape_version,
        combination_version=profile.multi_peak_combination_version,
    )


__all__ = ["evaluate_stationary_preference"]
