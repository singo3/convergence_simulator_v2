"""Explicit non-scoring summary classification for independent structure flags."""

from __future__ import annotations


def classify_structured_convergence(
    *,
    sufficient_sessions: bool,
    life_dominant: bool,
    bpm_common: bool,
    multi_attractor: bool,
    bpm_common_cross_life: bool = True,
) -> str:
    for name, value in {
        "sufficient_sessions": sufficient_sessions,
        "life_dominant": life_dominant,
        "bpm_common": bpm_common,
        "multi_attractor": multi_attractor,
        "bpm_common_cross_life": bpm_common_cross_life,
    }.items():
        if not isinstance(value, bool):
            raise TypeError(f"{name} must be boolean")
    if not sufficient_sessions and not multi_attractor:
        return "insufficient_sessions"
    # The explicit life+BPM combination is the single-pattern case. A distinct
    # per-life multi-attractor structure makes any simultaneous flags mixed.
    if multi_attractor and (life_dominant or bpm_common):
        return "mixed_structured_convergence"
    if life_dominant and bpm_common:
        return "single_life_pattern_convergence"
    if multi_attractor:
        return "life_specific_multi_attractor_convergence"
    if life_dominant:
        return "life_dominant_convergence"
    if bpm_common and bpm_common_cross_life:
        return "bpm_common_convergence"
    return "diffuse_or_unresolved"


__all__ = ["classify_structured_convergence"]
