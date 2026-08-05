"""Past-only response, lagged coupling, paired effect, and aggregate analysis."""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role

from .config import (
    AUTONOMOUS_ARM,
    HISTORY_RESPONSE_MODEL_VERSION,
    LAGGED_COUPLING_VERSION,
    PARTICIPANT_CLASSIFICATION_POLICY_VERSION,
    PARTICIPANT_EFFECT_VERSION,
    PROSPECTIVE_ENRICHMENT_VERSION,
    RANDOM_ARM,
    VALIDATION_SUMMARY_VERSION,
    YOKED_ARM,
    ParticipantClassificationPolicy,
)
from .records import BundleOutcome, SessionOutcome

LIFE_IDS = tuple(
    digital_life_config_for_role(role).digital_life_id
    for role in ("red", "green", "blue")
)
PARTICIPANT_CLASSIFICATIONS = (
    "clear_positive_adaptation",
    "partial_adaptation_signal",
    "no_clear_effect",
    "negative_or_unstable",
    "insufficient_data",
)
CLASSIFICATION_POLICY_VERSION = PARTICIPANT_CLASSIFICATION_POLICY_VERSION
BOOTSTRAP_POLICY_VERSION = "deterministic_participant_or_session_bootstrap_v0_1"
PERMUTATION_POLICY_VERSION = "within_participant_session_label_permutation_v0_1"
CONTEMPORANEOUS_RESPONSE_VERSION = "contemporaneous_light_rmssd_association_v0_1"


def _finite_values(values: Iterable[float | None]) -> tuple[float, ...]:
    return tuple(
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    )


def _seed(*parts: object) -> int:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def circular_hue_distance(first_degree: float, second_degree: float) -> float:
    first = float(first_degree) % 360.0
    second = float(second_degree) % 360.0
    direct = abs(first - second)
    return min(direct, 360.0 - direct)


def circular_mean_and_concentration(
    values: Sequence[float],
) -> tuple[float | None, float]:
    if not values:
        return None, 0.0
    radians = [math.radians(float(value) % 360.0) for value in values]
    mean_cos = statistics.fmean(math.cos(value) for value in radians)
    mean_sin = statistics.fmean(math.sin(value) for value in radians)
    concentration = math.hypot(mean_cos, mean_sin)
    if concentration <= 1e-15:
        return None, 0.0
    return math.degrees(math.atan2(mean_sin, mean_cos)) % 360.0, concentration


def _rankdata(values: Sequence[float]) -> tuple[float, ...]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][1] == indexed[cursor][1]:
            end += 1
        average_rank = (cursor + 1 + end) / 2.0
        for original_index, _value in indexed[cursor:end]:
            ranks[original_index] = average_rank
        cursor = end
    return tuple(ranks)


def pearson_correlation(
    first: Sequence[float],
    second: Sequence[float],
) -> float | None:
    if len(first) != len(second):
        raise ValueError("correlation inputs must have the same length")
    if len(first) < 2:
        return None
    mean_first = statistics.fmean(first)
    mean_second = statistics.fmean(second)
    centered_first = [value - mean_first for value in first]
    centered_second = [value - mean_second for value in second]
    denominator = math.sqrt(
        sum(value * value for value in centered_first)
        * sum(value * value for value in centered_second)
    )
    if denominator <= 1e-15:
        return 0.0
    return sum(
        left * right
        for left, right in zip(centered_first, centered_second, strict=True)
    ) / denominator


def spearman_correlation(
    first: Sequence[float],
    second: Sequence[float],
) -> float | None:
    if len(first) != len(second):
        raise ValueError("correlation inputs must have the same length")
    if len(first) < 2:
        return None
    return pearson_correlation(_rankdata(first), _rankdata(second))


def circular_linear_correlation(
    angles_degree: Sequence[float],
    linear_values: Sequence[float],
) -> float | None:
    """Return a circular-linear association without treating Hue as linear."""

    if len(angles_degree) != len(linear_values):
        raise ValueError("circular-linear inputs must have the same length")
    if len(angles_degree) < 3:
        return None
    radians = [math.radians(value % 360.0) for value in angles_degree]
    cosine = [math.cos(value) for value in radians]
    sine = [math.sin(value) for value in radians]
    r_cos = pearson_correlation(linear_values, cosine)
    r_sin = pearson_correlation(linear_values, sine)
    r_cross = pearson_correlation(cosine, sine)
    if r_cos is None or r_sin is None or r_cross is None:
        return None
    denominator = 1.0 - r_cross * r_cross
    if denominator <= 1e-15:
        return 0.0
    squared = (
        r_cos * r_cos
        + r_sin * r_sin
        - 2.0 * r_cos * r_sin * r_cross
    ) / denominator
    return math.sqrt(max(0.0, min(1.0, squared)))


def linear_slope(values: Sequence[tuple[float, float]]) -> float | None:
    if len(values) < 2:
        return None
    xs = [item[0] for item in values]
    ys = [item[1] for item in values]
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(ys)
    denominator = sum((value - x_mean) ** 2 for value in xs)
    if denominator <= 1e-15:
        return 0.0
    return sum(
        (x - x_mean) * (y - y_mean)
        for x, y in zip(xs, ys, strict=True)
    ) / denominator


def gaussian_kernel(distance: float, bandwidth: float) -> float:
    if bandwidth <= 0.0:
        raise ValueError("kernel bandwidth must be positive")
    return math.exp(-0.5 * (float(distance) / float(bandwidth)) ** 2)


def _weighted_mean(values: Sequence[tuple[float, float]]) -> float | None:
    denominator = sum(weight for _value, weight in values)
    if denominator <= 1e-15:
        return None
    return sum(value * weight for value, weight in values) / denominator


def history_before_session(
    bundle_outcomes: Sequence[BundleOutcome],
    session_index: int,
) -> tuple[BundleOutcome, ...]:
    """Return valid rows strictly before the requested current session."""

    return tuple(
        row
        for row in bundle_outcomes
        if row.valid_for_analysis
        and row.session_index < session_index
        and row.delta_rmssd_ms is not None
    )


def contemporaneous_response_row(
    bundle_outcomes: Sequence[BundleOutcome],
) -> dict[str, Any]:
    """Summarize same-Bundle light↔ΔRMSSD separately from lagged adaptation."""

    eligible = tuple(
        row
        for row in bundle_outcomes
        if row.valid_for_analysis
        and row.delta_rmssd_ms is not None
        and row.displayed_life_id is not None
        and row.displayed_hue_degree is not None
        and row.displayed_blink_bpm is not None
    )
    deltas = [float(row.delta_rmssd_ms) for row in eligible]
    bpms = [float(row.displayed_blink_bpm) for row in eligible]
    hues = [float(row.displayed_hue_degree) for row in eligible]
    first = bundle_outcomes[0] if bundle_outcomes else None
    life_values = {
        life_id: [
            float(row.delta_rmssd_ms)
            for row in eligible
            if row.displayed_life_id == life_id
        ]
        for life_id in LIFE_IDS
    }
    return {
        "participant_id": None if first is None else first.participant_id,
        "user_type_id": None if first is None else first.user_type_id,
        "condition_id": None if first is None else first.condition_id,
        "arm": None if first is None else first.arm,
        "valid_bundle_count": len(eligible),
        "same_bundle_bpm_delta_rmssd_pearson": pearson_correlation(bpms, deltas),
        "same_bundle_bpm_delta_rmssd_spearman": spearman_correlation(bpms, deltas),
        "same_bundle_hue_delta_rmssd_circular_linear": (
            circular_linear_correlation(hues, deltas)
        ),
        **{
            f"{life_id.replace('-', '_')}_mean_delta_rmssd_ms": (
                None if not values else statistics.fmean(values)
            )
            for life_id, values in life_values.items()
        },
        "same_bundle_only": True,
        "evidence_of_target_rmssd_used_for_future_output": False,
        "schema_version": CONTEMPORANEOUS_RESPONSE_VERSION,
    }


def life_history_score(
    history: Sequence[BundleOutcome],
    life_id: str,
    *,
    minimum_history_count: int = 3,
) -> float | None:
    values = [
        row.delta_rmssd_ms
        for row in history
        if row.displayed_life_id == life_id and row.delta_rmssd_ms is not None
    ]
    if len(values) < minimum_history_count:
        return None
    return statistics.fmean(values)


def bpm_history_score(
    history: Sequence[BundleOutcome],
    blink_bpm: float,
    *,
    bandwidth: float = 15.0,
    minimum_history_count: int = 3,
) -> float | None:
    eligible = [
        row
        for row in history
        if row.delta_rmssd_ms is not None and row.displayed_blink_bpm is not None
    ]
    if len(eligible) < minimum_history_count:
        return None
    return _weighted_mean(
        [
            (
                float(row.delta_rmssd_ms),
                gaussian_kernel(float(row.displayed_blink_bpm) - blink_bpm, bandwidth),
            )
            for row in eligible
        ]
    )


def full_pattern_history_score(
    history: Sequence[BundleOutcome],
    *,
    life_id: str,
    hue_degree: float,
    blink_bpm: float,
    hue_bandwidth_degree: float = 5.0,
    bpm_bandwidth: float = 15.0,
    minimum_history_count: int = 3,
) -> float | None:
    eligible = [
        row
        for row in history
        if row.displayed_life_id == life_id
        and row.delta_rmssd_ms is not None
        and row.displayed_hue_degree is not None
        and row.displayed_blink_bpm is not None
    ]
    if len(eligible) < minimum_history_count:
        return None
    weighted: list[tuple[float, float]] = []
    for row in eligible:
        assert row.delta_rmssd_ms is not None
        assert row.displayed_hue_degree is not None
        assert row.displayed_blink_bpm is not None
        hue_weight = gaussian_kernel(
            circular_hue_distance(row.displayed_hue_degree, hue_degree),
            hue_bandwidth_degree,
        )
        bpm_weight = gaussian_kernel(row.displayed_blink_bpm - blink_bpm, bpm_bandwidth)
        weighted.append((row.delta_rmssd_ms, hue_weight * bpm_weight))
    return _weighted_mean(weighted)


def deterministic_counterfactual_set() -> tuple[dict[str, float | str], ...]:
    result: list[dict[str, float | str]] = []
    for role in ("red", "green", "blue"):
        config = digital_life_config_for_role(role)
        for hue_index in range(5):
            f = config.f_min + (config.f_max - config.f_min) * hue_index / 4.0
            for bpm_index in range(11):
                bpm = 10.0 + 155.0 * bpm_index / 10.0
                result.append(
                    {
                        "life_id": config.digital_life_id,
                        "hue_degree": 360.0 * f,
                        "blink_bpm": bpm,
                    }
                )
    if len(result) != 165:
        raise RuntimeError("counterfactual grid must contain exactly 165 candidates")
    return tuple(result)


def counterfactual_percentile(
    actual: float | None,
    counterfactual: Sequence[float | None],
) -> float | None:
    if actual is None:
        return None
    values = _finite_values(counterfactual)
    if not values:
        return None
    lower = sum(value < actual for value in values)
    equal = sum(value == actual for value in values)
    return 100.0 * (lower + 0.5 * equal) / len(values)


def prospective_rows(
    bundle_outcomes: Sequence[BundleOutcome],
    session_outcomes: Sequence[SessionOutcome],
    *,
    hue_bandwidth_degree: float = 5.0,
    bpm_bandwidth: float = 15.0,
    minimum_history_count: int = 3,
) -> tuple[dict[str, Any], ...]:
    counterfactual = deterministic_counterfactual_set()
    result: list[dict[str, Any]] = []
    for session in sorted(session_outcomes, key=lambda item: item.session_index):
        history = history_before_session(bundle_outcomes, session.session_index)
        life = session.representative_life_id
        hue = session.representative_hue_degree
        bpm = session.representative_blink_bpm
        if life is None or hue is None or bpm is None:
            actual_life = actual_bpm = actual_pattern = None
        else:
            actual_life = life_history_score(
                history,
                life,
                minimum_history_count=minimum_history_count,
            )
            actual_bpm = bpm_history_score(
                history,
                bpm,
                bandwidth=bpm_bandwidth,
                minimum_history_count=minimum_history_count,
            )
            actual_pattern = full_pattern_history_score(
                history,
                life_id=life,
                hue_degree=hue,
                blink_bpm=bpm,
                hue_bandwidth_degree=hue_bandwidth_degree,
                bpm_bandwidth=bpm_bandwidth,
                minimum_history_count=minimum_history_count,
            )
        life_scores = [
            life_history_score(
                history,
                str(candidate["life_id"]),
                minimum_history_count=minimum_history_count,
            )
            for candidate in counterfactual
        ]
        bpm_scores = [
            bpm_history_score(
                history,
                float(candidate["blink_bpm"]),
                bandwidth=bpm_bandwidth,
                minimum_history_count=minimum_history_count,
            )
            for candidate in counterfactual
        ]
        pattern_scores = [
            full_pattern_history_score(
                history,
                life_id=str(candidate["life_id"]),
                hue_degree=float(candidate["hue_degree"]),
                blink_bpm=float(candidate["blink_bpm"]),
                hue_bandwidth_degree=hue_bandwidth_degree,
                bpm_bandwidth=bpm_bandwidth,
                minimum_history_count=minimum_history_count,
            )
            for candidate in counterfactual
        ]
        finite_bpm = _finite_values(bpm_scores)
        finite_life = _finite_values(life_scores)
        finite_pattern = _finite_values(pattern_scores)
        other_life_scores = (
            []
            if life is None
            else [
                life_history_score(
                    history,
                    other,
                    minimum_history_count=minimum_history_count,
                )
                for other in LIFE_IDS
                if other != life
            ]
        )
        finite_other_life = _finite_values(other_life_scores)
        result.append(
            {
                "participant_id": session.participant_id,
                "user_type_id": session.user_type_id,
                "condition_id": session.condition_id,
                "arm": session.arm,
                "session_index": session.session_index,
                "history_cutoff_session_index": session.session_index - 1,
                "history_bundle_count": len(history),
                "actual_predicted_delta_rmssd_life": actual_life,
                "actual_predicted_delta_rmssd_bpm": actual_bpm,
                "actual_predicted_delta_rmssd_full_pattern": actual_pattern,
                "counterfactual_candidate_count": len(counterfactual),
                "life_selection_percentile": counterfactual_percentile(
                    actual_life, life_scores
                ),
                "bpm_selection_percentile": counterfactual_percentile(
                    actual_bpm, bpm_scores
                ),
                "full_pattern_selection_percentile": counterfactual_percentile(
                    actual_pattern, pattern_scores
                ),
                "life_counterfactual_mean_predicted_delta_rmssd_ms": (
                    None if not finite_life else statistics.fmean(finite_life)
                ),
                "life_counterfactual_median_predicted_delta_rmssd_ms": (
                    None if not finite_life else statistics.median(finite_life)
                ),
                "life_actual_minus_counterfactual_mean_ms": (
                    None
                    if actual_life is None or not finite_life
                    else actual_life - statistics.fmean(finite_life)
                ),
                "bpm_counterfactual_mean_predicted_delta_rmssd_ms": (
                    None if not finite_bpm else statistics.fmean(finite_bpm)
                ),
                "bpm_counterfactual_median_predicted_delta_rmssd_ms": (
                    None if not finite_bpm else statistics.median(finite_bpm)
                ),
                "bpm_actual_minus_counterfactual_mean_ms": (
                    None
                    if actual_bpm is None or not finite_bpm
                    else actual_bpm - statistics.fmean(finite_bpm)
                ),
                "full_pattern_counterfactual_mean_predicted_delta_rmssd_ms": (
                    None if not finite_pattern else statistics.fmean(finite_pattern)
                ),
                "full_pattern_counterfactual_median_predicted_delta_rmssd_ms": (
                    None
                    if not finite_pattern
                    else statistics.median(finite_pattern)
                ),
                "full_pattern_actual_minus_counterfactual_mean_ms": (
                    None
                    if actual_pattern is None or not finite_pattern
                    else actual_pattern - statistics.fmean(finite_pattern)
                ),
                "life_selection_enrichment": (
                    None
                    if actual_life is None or len(finite_other_life) != 2
                    else actual_life - statistics.fmean(finite_other_life)
                ),
                "bpm_selection_enrichment": (
                    None
                    if actual_bpm is None or not finite_bpm
                    else actual_bpm - statistics.fmean(finite_bpm)
                ),
                "full_pattern_selection_enrichment": (
                    None
                    if actual_pattern is None or not finite_pattern
                    else actual_pattern - statistics.fmean(finite_pattern)
                ),
                "observed_future_delta_rmssd_ms": (
                    session.mean_valid_bundle_delta_rmssd_ms
                ),
                "history_model_version": HISTORY_RESPONSE_MODEL_VERSION,
                "schema_version": PROSPECTIVE_ENRICHMENT_VERSION,
            }
        )
    return tuple(result)


def pattern_closeness(first: SessionOutcome, second: SessionOutcome) -> float | None:
    if (
        first.representative_life_id is None
        or second.representative_life_id is None
        or first.representative_hue_degree is None
        or second.representative_hue_degree is None
        or first.representative_blink_bpm is None
        or second.representative_blink_bpm is None
    ):
        return None
    if first.representative_life_id != second.representative_life_id:
        return 0.0
    normalized_distance = (
        circular_hue_distance(
            first.representative_hue_degree,
            second.representative_hue_degree,
        )
        / 5.0
        + abs(first.representative_blink_bpm - second.representative_blink_bpm)
        / 15.0
    )
    return 1.0 / (1.0 + normalized_distance)


def lagged_coupling_row(
    sessions: Sequence[SessionOutcome],
    prospective: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    ordered = tuple(sorted(sessions, key=lambda item: item.session_index))
    response: list[float] = []
    same_life: list[float] = []
    closeness: list[float] = []
    revisit: list[float] = []
    for index, current in enumerate(ordered[:-1]):
        next_session = ordered[index + 1]
        delta = current.mean_valid_bundle_delta_rmssd_ms
        close = pattern_closeness(current, next_session)
        if delta is None or close is None:
            continue
        response.append(delta)
        same_life.append(
            float(current.representative_life_id == next_session.representative_life_id)
        )
        closeness.append(close)
        later = ordered[index + 1 : index + 3]
        revisit.append(
            float(
                any(
                    current.representative_life_id == item.representative_life_id
                    and (pattern_closeness(current, item) or 0.0) >= 0.5
                    for item in later
                )
            )
        )
    enrichments = _finite_values(
        row.get("full_pattern_selection_enrichment") for row in prospective
    )
    percentiles = _finite_values(
        row.get("full_pattern_selection_percentile") for row in prospective
    )
    first = ordered[0] if ordered else None
    return {
        "participant_id": None if first is None else first.participant_id,
        "user_type_id": None if first is None else first.user_type_id,
        "condition_id": None if first is None else first.condition_id,
        "arm": None if first is None else first.arm,
        "lag_pair_count": len(response),
        "lag1_response_vs_same_life": spearman_correlation(response, same_life),
        "lag1_response_vs_pattern_closeness": spearman_correlation(
            response, closeness
        ),
        "response_vs_revisit_within_2": spearman_correlation(response, revisit),
        "mean_full_pattern_selection_enrichment": (
            None if not enrichments else statistics.fmean(enrichments)
        ),
        "mean_selection_percentile": (
            None if not percentiles else statistics.fmean(percentiles)
        ),
        "schema_version": LAGGED_COUPLING_VERSION,
    }


def prediction_metrics_row(
    sessions: Sequence[SessionOutcome],
    prospective: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_index = {item.session_index: item for item in sessions}
    pairs = [
        (
            float(row["actual_predicted_delta_rmssd_full_pattern"]),
            float(row["observed_future_delta_rmssd_ms"]),
        )
        for row in prospective
        if row.get("actual_predicted_delta_rmssd_full_pattern") is not None
        and row.get("observed_future_delta_rmssd_ms") is not None
        and int(row["session_index"]) in by_index
    ]
    predicted = [item[0] for item in pairs]
    observed = [item[1] for item in pairs]
    errors = [left - right for left, right in pairs]
    first = sessions[0] if sessions else None
    return {
        "participant_id": None if first is None else first.participant_id,
        "user_type_id": None if first is None else first.user_type_id,
        "condition_id": None if first is None else first.condition_id,
        "arm": None if first is None else first.arm,
        "valid_prediction_count": len(pairs),
        "pearson_correlation": pearson_correlation(predicted, observed),
        "spearman_correlation": spearman_correlation(predicted, observed),
        "mae": None if not errors else statistics.fmean(abs(value) for value in errors),
        "signed_bias": None if not errors else statistics.fmean(errors),
        "history_model_version": HISTORY_RESPONSE_MODEL_VERSION,
    }


def _thirds(values: Sequence[float]) -> tuple[tuple[float, ...], ...]:
    if not values:
        return (), (), ()
    length = len(values)
    first_end = max(1, math.ceil(length / 3))
    second_end = max(first_end + 1, math.ceil(2 * length / 3))
    second_end = min(second_end, length)
    return (
        tuple(values[:first_end]),
        tuple(values[first_end:second_end]),
        tuple(values[second_end:]),
    )


def rmssd_benefit_row(sessions: Sequence[SessionOutcome]) -> dict[str, Any]:
    valid = [
        item
        for item in sorted(sessions, key=lambda row: row.session_index)
        if item.mean_valid_bundle_delta_rmssd_ms is not None
    ]
    values = [float(item.mean_valid_bundle_delta_rmssd_ms) for item in valid]
    early, middle, late = _thirds(values)
    rolling = [
        statistics.fmean(values[max(0, index - 2) : index + 1])
        for index in range(len(values))
    ]
    total_bundles = 3 * len(sessions)
    valid_bundles = sum(item.valid_bundle_count for item in sessions)
    first = sessions[0] if sessions else None
    return {
        "participant_id": None if first is None else first.participant_id,
        "user_type_id": None if first is None else first.user_type_id,
        "condition_id": None if first is None else first.condition_id,
        "arm": None if first is None else first.arm,
        "all_session_mean_delta_rmssd_ms": (
            None if not values else statistics.fmean(values)
        ),
        "early_session_mean_delta_rmssd_ms": (
            None if not early else statistics.fmean(early)
        ),
        "middle_session_mean_delta_rmssd_ms": (
            None if not middle else statistics.fmean(middle)
        ),
        "late_session_mean_delta_rmssd_ms": (
            None if not late else statistics.fmean(late)
        ),
        "late_minus_early_ms": (
            None
            if not early or not late
            else statistics.fmean(late) - statistics.fmean(early)
        ),
        "delta_rmssd_session_slope": linear_slope(
            [
                (float(item.session_index), float(item.mean_valid_bundle_delta_rmssd_ms))
                for item in valid
            ]
        ),
        "maximum_rolling_mean_delta_rmssd_ms": None if not rolling else max(rolling),
        "valid_session_count": len(valid),
        "valid_bundle_count": valid_bundles,
        "reject_rate": (
            0.0 if total_bundles == 0 else 1.0 - valid_bundles / total_bundles
        ),
    }


def _difference(left: object, right: object) -> float | None:
    if left is None or right is None:
        return None
    return float(left) - float(right)


def paired_arm_difference_rows(
    benefit_rows: Sequence[Mapping[str, Any]],
    lagged_rows: Sequence[Mapping[str, Any]],
    sessions: Sequence[SessionOutcome] = (),
) -> tuple[dict[str, Any], ...]:
    benefit_by_key = {
        (str(row["participant_id"]), str(row["condition_id"]), str(row["arm"])): row
        for row in benefit_rows
    }
    lagged_by_key = {
        (str(row["participant_id"]), str(row["condition_id"]), str(row["arm"])): row
        for row in lagged_rows
    }
    participant_conditions = sorted(
        {(key[0], key[1]) for key in benefit_by_key if key[2] == AUTONOMOUS_ARM}
    )
    session_groups: dict[tuple[str, str, str], dict[int, float]] = defaultdict(dict)
    session_pairing_requested = bool(sessions)
    for session in sessions:
        if session.mean_valid_bundle_delta_rmssd_ms is not None:
            session_groups[
                (session.participant_id, session.condition_id, session.arm)
            ][session.session_index] = float(
                session.mean_valid_bundle_delta_rmssd_ms
            )
    result: list[dict[str, Any]] = []
    for participant_id, condition_id in participant_conditions:
        auto = benefit_by_key[(participant_id, condition_id, AUTONOMOUS_ARM)]
        auto_lagged = lagged_by_key.get((participant_id, condition_id, AUTONOMOUS_ARM), {})
        for comparator in (YOKED_ARM, RANDOM_ARM):
            other = benefit_by_key.get((participant_id, condition_id, comparator))
            if other is None:
                continue
            other_lagged = lagged_by_key.get((participant_id, condition_id, comparator), {})
            auto_sessions = session_groups.get(
                (participant_id, condition_id, AUTONOMOUS_ARM),
                {},
            )
            other_sessions = session_groups.get(
                (participant_id, condition_id, comparator),
                {},
            )
            paired_indices = sorted(set(auto_sessions) & set(other_sessions))
            paired_differences = [
                auto_sessions[index] - other_sessions[index]
                for index in paired_indices
            ]
            paired_early, _paired_middle, paired_late = _thirds(
                paired_differences
            )
            paired_late_advantage = (
                None
                if not paired_late
                else statistics.fmean(paired_late)
            )
            paired_learning_gain = (
                None
                if not paired_early or not paired_late
                else statistics.fmean(paired_late)
                - statistics.fmean(paired_early)
            )
            paired_slope_advantage = linear_slope(
                [
                    (float(index), auto_sessions[index] - other_sessions[index])
                    for index in paired_indices
                ]
            )
            late_advantage = (
                paired_late_advantage
                if paired_indices
                else None
                if session_pairing_requested
                else _difference(
                    auto["late_session_mean_delta_rmssd_ms"],
                    other["late_session_mean_delta_rmssd_ms"],
                )
            )
            learning_gain = (
                paired_learning_gain
                if paired_indices
                else None
                if session_pairing_requested
                else _difference(
                    auto["late_minus_early_ms"],
                    other["late_minus_early_ms"],
                )
            )
            slope_advantage = (
                paired_slope_advantage
                if paired_indices
                else None
                if session_pairing_requested
                else _difference(
                    auto["delta_rmssd_session_slope"],
                    other["delta_rmssd_session_slope"],
                )
            )
            result.append(
                {
                    "participant_id": participant_id,
                    "user_type_id": auto["user_type_id"],
                    "condition_id": condition_id,
                    "comparator_arm": comparator,
                    "late_delta_rmssd_advantage_ms": late_advantage,
                    "learning_gain_advantage_ms": learning_gain,
                    "slope_advantage": slope_advantage,
                    "selection_enrichment_advantage": _difference(
                        auto_lagged.get("mean_full_pattern_selection_enrichment"),
                        other_lagged.get("mean_full_pattern_selection_enrichment"),
                    ),
                    "lagged_same_life_advantage": _difference(
                        auto_lagged.get("lag1_response_vs_same_life"),
                        other_lagged.get("lag1_response_vs_same_life"),
                    ),
                    "lagged_pattern_advantage": _difference(
                        auto_lagged.get("lag1_response_vs_pattern_closeness"),
                        other_lagged.get("lag1_response_vs_pattern_closeness"),
                    ),
                    "schema_version": VALIDATION_SUMMARY_VERSION,
                    "paired_valid_session_count": len(paired_indices),
                }
            )
    return tuple(result)


def permutation_null_row(
    sessions: Sequence[SessionOutcome],
    *,
    permutation_count: int,
) -> dict[str, Any]:
    ordered = tuple(sorted(sessions, key=lambda item: item.session_index))
    responses: list[float] = []
    same_life: list[float] = []
    for current, future in zip(ordered[:-1], ordered[1:], strict=True):
        if (
            current.mean_valid_bundle_delta_rmssd_ms is None
            or current.representative_life_id is None
            or future.representative_life_id is None
        ):
            continue
        responses.append(float(current.mean_valid_bundle_delta_rmssd_ms))
        same_life.append(
            float(current.representative_life_id == future.representative_life_id)
        )
    observed = spearman_correlation(responses, same_life)
    null: list[float] = []
    first = sessions[0] if sessions else None
    if observed is not None:
        generator = random.Random(
            _seed(
                "stage8a3-permutation",
                None if first is None else first.participant_id,
                None if first is None else first.condition_id,
                None if first is None else first.arm,
            )
        )
        for _index in range(permutation_count):
            shuffled = responses.copy()
            generator.shuffle(shuffled)
            statistic = spearman_correlation(shuffled, same_life)
            if statistic is not None:
                null.append(statistic)
    if observed is None or not null:
        percentile = p_like = null_mean = null_std = None
    else:
        percentile = counterfactual_percentile(observed, null)
        p_like = (sum(abs(value) >= abs(observed) for value in null) + 1) / (
            len(null) + 1
        )
        null_mean = statistics.fmean(null)
        null_std = statistics.pstdev(null)
    return {
        "participant_id": None if first is None else first.participant_id,
        "user_type_id": None if first is None else first.user_type_id,
        "condition_id": None if first is None else first.condition_id,
        "arm": None if first is None else first.arm,
        "statistic": "lag1_response_vs_same_life",
        "observed_statistic": observed,
        "null_mean": null_mean,
        "null_standard_deviation": null_std,
        "empirical_percentile": percentile,
        "two_sided_empirical_p_like": p_like,
        "permutation_count": permutation_count,
        "policy_version": PERMUTATION_POLICY_VERSION,
    }


def bootstrap_interval(
    values: Sequence[float],
    *,
    seed_parts: Sequence[object],
    replicate_count: int = 1_000,
) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    generator = random.Random(_seed("stage8a3-bootstrap", *seed_parts))
    means = sorted(
        statistics.fmean(generator.choice(values) for _index in range(len(values)))
        for _replicate in range(replicate_count)
    )
    lower_index = max(0, math.floor(0.025 * (len(means) - 1)))
    upper_index = min(len(means) - 1, math.ceil(0.975 * (len(means) - 1)))
    return means[lower_index], means[upper_index]


def bootstrap_median_interval(
    values: Sequence[float],
    *,
    seed_parts: Sequence[object],
    replicate_count: int = 1_000,
) -> tuple[float | None, float | None]:
    """Return a deterministic participant bootstrap interval for a median."""

    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    generator = random.Random(_seed("stage8a3-bootstrap-median", *seed_parts))
    medians = sorted(
        statistics.median(
            generator.choice(values) for _index in range(len(values))
        )
        for _replicate in range(replicate_count)
    )
    lower_index = max(0, math.floor(0.025 * (len(medians) - 1)))
    upper_index = min(len(medians) - 1, math.ceil(0.975 * (len(medians) - 1)))
    return medians[lower_index], medians[upper_index]


def session_block_bootstrap_interval(
    autonomous_sessions: Sequence[SessionOutcome],
    yoked_sessions: Sequence[SessionOutcome],
    *,
    seed_parts: Sequence[object],
    block_length: int = 2,
    replicate_count: int = 1_000,
) -> tuple[float | None, float | None]:
    """Bootstrap paired late-session effects with contiguous session blocks."""

    auto = {
        item.session_index: item.mean_valid_bundle_delta_rmssd_ms
        for item in autonomous_sessions
        if item.mean_valid_bundle_delta_rmssd_ms is not None
    }
    yoke = {
        item.session_index: item.mean_valid_bundle_delta_rmssd_ms
        for item in yoked_sessions
        if item.mean_valid_bundle_delta_rmssd_ms is not None
    }
    paired = [
        float(auto[index]) - float(yoke[index])
        for index in sorted(set(auto) & set(yoke))
    ]
    if not paired:
        return None, None
    late_count = max(1, math.ceil(len(paired) / 3))
    values = paired[-late_count:]
    if len(values) == 1:
        return values[0], values[0]
    selected_block = min(max(1, block_length), len(values))
    generator = random.Random(
        _seed("stage8a3-session-block-bootstrap", *seed_parts)
    )
    means: list[float] = []
    for _replicate in range(replicate_count):
        sample: list[float] = []
        while len(sample) < len(values):
            start = generator.randrange(len(values))
            sample.extend(
                values[(start + offset) % len(values)]
                for offset in range(selected_block)
            )
        means.append(statistics.fmean(sample[: len(values)]))
    means.sort()
    lower_index = max(0, math.floor(0.025 * (len(means) - 1)))
    upper_index = min(len(means) - 1, math.ceil(0.975 * (len(means) - 1)))
    return means[lower_index], means[upper_index]


def classify_participant_effect(
    *,
    late_advantage_ms: float | None,
    selection_enrichment_advantage: float | None,
    slope_advantage: float | None,
    permutation_p_like: float | None,
    valid_session_count: int,
    policy: ParticipantClassificationPolicy | None = None,
) -> str:
    selected_policy = policy or ParticipantClassificationPolicy()
    if (
        valid_session_count < selected_policy.minimum_valid_sessions
        or late_advantage_ms is None
    ):
        return "insufficient_data"
    positives = sum(
        (
            late_advantage_ms > selected_policy.late_positive_threshold_ms,
            selection_enrichment_advantage is not None
            and selection_enrichment_advantage
            > selected_policy.selection_enrichment_threshold,
            slope_advantage is not None
            and slope_advantage > selected_policy.slope_threshold,
            permutation_p_like is not None
            and permutation_p_like <= selected_policy.permutation_p_like_threshold,
        )
    )
    if (
        positives >= selected_policy.clear_positive_indicator_count
        and late_advantage_ms > selected_policy.late_positive_threshold_ms
    ):
        return "clear_positive_adaptation"
    if positives >= selected_policy.partial_indicator_count:
        return "partial_adaptation_signal"
    if late_advantage_ms < selected_policy.late_negative_threshold_ms and (
        slope_advantage is None
        or slope_advantage < selected_policy.slope_threshold
    ):
        return "negative_or_unstable"
    return "no_clear_effect"


def participant_effect_rows(
    paired_rows: Sequence[Mapping[str, Any]],
    benefit_rows: Sequence[Mapping[str, Any]],
    permutation_rows: Sequence[Mapping[str, Any]],
    sessions: Sequence[SessionOutcome] = (),
    classification_policy: ParticipantClassificationPolicy | None = None,
) -> tuple[dict[str, Any], ...]:
    paired = {
        (str(row["participant_id"]), str(row["condition_id"]), str(row["comparator_arm"])): row
        for row in paired_rows
    }
    benefits = {
        (str(row["participant_id"]), str(row["condition_id"]), str(row["arm"])): row
        for row in benefit_rows
    }
    permutations = {
        (str(row["participant_id"]), str(row["condition_id"]), str(row["arm"])): row
        for row in permutation_rows
    }
    result: list[dict[str, Any]] = []
    keys = sorted(key for key in paired if key[2] == YOKED_ARM)
    for participant_id, condition_id, _comparator in keys:
        row = paired[(participant_id, condition_id, YOKED_ARM)]
        auto_benefit = benefits[(participant_id, condition_id, AUTONOMOUS_ARM)]
        permutation = permutations.get(
            (participant_id, condition_id, AUTONOMOUS_ARM), {}
        )
        classification = classify_participant_effect(
            late_advantage_ms=row.get("late_delta_rmssd_advantage_ms"),
            selection_enrichment_advantage=row.get(
                "selection_enrichment_advantage"
            ),
            slope_advantage=row.get("slope_advantage"),
            permutation_p_like=permutation.get("two_sided_empirical_p_like"),
            valid_session_count=int(
                row.get(
                    "paired_valid_session_count",
                    auto_benefit["valid_session_count"],
                )
            ),
            policy=classification_policy,
        )
        late_value = row.get("late_delta_rmssd_advantage_ms")
        lower, upper = session_block_bootstrap_interval(
            tuple(
                item
                for item in sessions
                if item.participant_id == participant_id
                and item.condition_id == condition_id
                and item.arm == AUTONOMOUS_ARM
            ),
            tuple(
                item
                for item in sessions
                if item.participant_id == participant_id
                and item.condition_id == condition_id
                and item.arm == YOKED_ARM
            ),
            seed_parts=(participant_id, condition_id, "participant-effect"),
        )
        result.append(
            {
                "participant_id": participant_id,
                "user_type_id": row["user_type_id"],
                "condition_id": condition_id,
                "autonomous_minus_yoked_late_delta_rmssd_ms": late_value,
                "autonomous_minus_yoked_selection_enrichment": row.get(
                    "selection_enrichment_advantage"
                ),
                "autonomous_minus_yoked_slope": row.get("slope_advantage"),
                "permutation_p_like": permutation.get(
                    "two_sided_empirical_p_like"
                ),
                "valid_session_count": row.get(
                    "paired_valid_session_count",
                    auto_benefit["valid_session_count"],
                ),
                "effect_interval_lower95": lower,
                "effect_interval_upper95": upper,
                "classification": classification,
                "classification_is_primary": False,
                "classification_policy_version": CLASSIFICATION_POLICY_VERSION,
                "bootstrap_policy_version": BOOTSTRAP_POLICY_VERSION,
                "schema_version": PARTICIPANT_EFFECT_VERSION,
            }
        )
    return tuple(result)


def participant_level_summary_rows(
    participant_effects: Sequence[Mapping[str, Any]],
    paired_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    paired_by_key = {
        (str(row["participant_id"]), str(row["condition_id"]), str(row["comparator_arm"])): row
        for row in paired_rows
    }
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in participant_effects:
        groups[(str(row["condition_id"]), str(row["user_type_id"]))].append(row)
    result: list[dict[str, Any]] = []
    for (condition_id, user_type_id), rows in sorted(groups.items()):
        effects = _finite_values(
            row.get("autonomous_minus_yoked_late_delta_rmssd_ms") for row in rows
        )
        random_effects = _finite_values(
            paired_by_key.get(
                (str(row["participant_id"]), condition_id, RANDOM_ARM), {}
            ).get("late_delta_rmssd_advantage_ms")
            for row in rows
        )
        paired_metrics: dict[tuple[str, str], list[float]] = {}
        for comparator in (YOKED_ARM, RANDOM_ARM):
            for field in (
                "learning_gain_advantage_ms",
                "slope_advantage",
                "selection_enrichment_advantage",
                "lagged_same_life_advantage",
                "lagged_pattern_advantage",
            ):
                paired_metrics[(comparator, field)] = _finite_values(
                    paired_by_key.get(
                        (str(row["participant_id"]), condition_id, comparator),
                        {},
                    ).get(field)
                    for row in rows
                )
        lower, upper = bootstrap_interval(
            effects,
            seed_parts=(condition_id, user_type_id, "user-type"),
        )
        counts = Counter(str(row["classification"]) for row in rows)
        valid_count = len(effects)
        aggregate_metrics = {
            (
                "mean_autonomous_minus_"
                + ("yoked" if comparator == YOKED_ARM else "random")
                + f"_{field}"
            ): (
                None
                if not paired_metrics[(comparator, field)]
                else statistics.fmean(paired_metrics[(comparator, field)])
            )
            for comparator in (YOKED_ARM, RANDOM_ARM)
            for field in (
                "learning_gain_advantage_ms",
                "slope_advantage",
                "selection_enrichment_advantage",
                "lagged_same_life_advantage",
                "lagged_pattern_advantage",
            )
        }
        result.append(
            {
                "condition_id": condition_id,
                "user_type_id": user_type_id,
                "participant_count": len(rows),
                "valid_participant_count": valid_count,
                "mean_autonomous_minus_yoked_late_delta_rmssd_ms": (
                    None if not effects else statistics.fmean(effects)
                ),
                "median_autonomous_minus_yoked_late_delta_rmssd_ms": (
                    None if not effects else statistics.median(effects)
                ),
                "lower95": lower,
                "upper95": upper,
                "mean_autonomous_minus_random_late_delta_rmssd_ms": (
                    None if not random_effects else statistics.fmean(random_effects)
                ),
                **aggregate_metrics,
                **{
                    f"{classification}_count": counts[classification]
                    for classification in PARTICIPANT_CLASSIFICATIONS
                },
                **{
                    f"{classification}_rate": (
                        0.0 if not rows else counts[classification] / len(rows)
                    )
                    for classification in PARTICIPANT_CLASSIFICATIONS
                },
                "participant_is_aggregation_unit": True,
                "schema_version": VALIDATION_SUMMARY_VERSION,
            }
        )
    return tuple(result)


def overall_summary_rows(
    participant_effects: Sequence[Mapping[str, Any]],
    paired_rows: Sequence[Mapping[str, Any]] = (),
) -> tuple[dict[str, Any], ...]:
    paired_by_key = {
        (str(row["participant_id"]), str(row["condition_id"]), str(row["comparator_arm"])): row
        for row in paired_rows
    }
    by_condition: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in participant_effects:
        by_condition[str(row["condition_id"])].append(row)
    result: list[dict[str, Any]] = []
    for condition_id, rows in sorted(by_condition.items()):
        effects = _finite_values(
            row.get("autonomous_minus_yoked_late_delta_rmssd_ms") for row in rows
        )
        lower, upper = bootstrap_interval(
            effects,
            seed_parts=(condition_id, "overall"),
        )
        counts = Counter(str(row["classification"]) for row in rows)
        paired_metrics: dict[tuple[str, str], list[float]] = {}
        for comparator in (YOKED_ARM, RANDOM_ARM):
            for field in (
                "late_delta_rmssd_advantage_ms",
                "learning_gain_advantage_ms",
                "slope_advantage",
                "selection_enrichment_advantage",
                "lagged_same_life_advantage",
                "lagged_pattern_advantage",
            ):
                paired_metrics[(comparator, field)] = _finite_values(
                    paired_by_key.get(
                        (str(row["participant_id"]), condition_id, comparator),
                        {},
                    ).get(field)
                    for row in rows
                )
        aggregate_metrics = {
            (
                "mean_autonomous_minus_"
                + ("yoked" if comparator == YOKED_ARM else "random")
                + f"_{field}"
            ): (
                None
                if not paired_metrics[(comparator, field)]
                else statistics.fmean(paired_metrics[(comparator, field)])
            )
            for comparator in (YOKED_ARM, RANDOM_ARM)
            for field in (
                "late_delta_rmssd_advantage_ms",
                "learning_gain_advantage_ms",
                "slope_advantage",
                "selection_enrichment_advantage",
                "lagged_same_life_advantage",
                "lagged_pattern_advantage",
            )
        }
        result.append(
            {
                "condition_id": condition_id,
                "participant_count": len(rows),
                "valid_participant_count": len(effects),
                "mean_autonomous_minus_yoked_late_delta_rmssd_ms": (
                    None if not effects else statistics.fmean(effects)
                ),
                "median_autonomous_minus_yoked_late_delta_rmssd_ms": (
                    None if not effects else statistics.median(effects)
                ),
                "lower95": lower,
                "upper95": upper,
                **aggregate_metrics,
                "classification_counts": dict(sorted(counts.items())),
                "no_clear_effect_is_valid_outcome": True,
                "participant_is_aggregation_unit": True,
                "schema_version": VALIDATION_SUMMARY_VERSION,
            }
        )
    return tuple(result)


def user_type_trajectory_rows(
    sessions: Sequence[SessionOutcome],
) -> tuple[dict[str, Any], ...]:
    groups: dict[tuple[str, str, str, int], list[SessionOutcome]] = defaultdict(list)
    for row in sessions:
        groups[(row.condition_id, row.user_type_id, row.arm, row.session_index)].append(row)
    result: list[dict[str, Any]] = []
    for (condition_id, user_type_id, arm, session_index), rows in sorted(groups.items()):
        bpms = _finite_values(row.representative_blink_bpm for row in rows)
        life_counts = Counter(
            row.representative_life_id
            for row in rows
            if row.representative_life_id
        )
        modal_life = None if not life_counts else sorted(
            life_counts,
            key=lambda item: (-life_counts[item], item),
        )[0]
        modal_hues = [
            float(row.representative_hue_degree)
            for row in rows
            if row.representative_life_id == modal_life
            and row.representative_hue_degree is not None
        ]
        hue_mean, concentration = circular_mean_and_concentration(modal_hues)
        all_hues = [
            float(row.representative_hue_degree)
            for row in rows
            if row.representative_hue_degree is not None
        ]
        all_hue_mean, all_hue_concentration = circular_mean_and_concentration(
            all_hues
        )
        sorted_bpms = sorted(bpms)
        q1 = None if not sorted_bpms else sorted_bpms[(len(sorted_bpms) - 1) // 4]
        q3 = None if not sorted_bpms else sorted_bpms[(3 * (len(sorted_bpms) - 1)) // 4]
        lower, upper = bootstrap_median_interval(
            bpms,
            seed_parts=(condition_id, user_type_id, arm, session_index, "bpm"),
        )
        result.append(
            {
                "condition_id": condition_id,
                "user_type_id": user_type_id,
                "arm": arm,
                "session_index": session_index,
                "participant_count": len(rows),
                "median_bpm": None if not bpms else statistics.median(bpms),
                "bpm_q1": q1,
                "bpm_q3": q3,
                "bpm_lower95": lower,
                "bpm_upper95": upper,
                "modal_life_id": modal_life,
                "modal_life_share": (
                    0.0 if modal_life is None else life_counts[modal_life] / len(rows)
                ),
                "life_red_share": life_counts["life-red"] / len(rows),
                "life_green_share": life_counts["life-green"] / len(rows),
                "life_blue_share": life_counts["life-blue"] / len(rows),
                "modal_life_circular_mean_hue_degree": hue_mean,
                "modal_life_circular_concentration": concentration,
                "circular_mean_hue_degree": all_hue_mean,
                "circular_concentration": all_hue_concentration,
                "low_concentration": concentration < 0.25,
            }
        )
    return tuple(result)


def analyze_validation_records(
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    *,
    permutation_count: int,
    hue_bandwidth_degree: float,
    bpm_bandwidth: float,
    minimum_history_count: int,
    classification_policy: ParticipantClassificationPolicy | None = None,
) -> dict[str, tuple[dict[str, Any], ...]]:
    groups: dict[tuple[str, str, str], list[SessionOutcome]] = defaultdict(list)
    bundle_groups: dict[tuple[str, str, str], list[BundleOutcome]] = defaultdict(list)
    for row in sessions:
        groups[(row.participant_id, row.condition_id, row.arm)].append(row)
    for row in bundles:
        bundle_groups[(row.participant_id, row.condition_id, row.arm)].append(row)
    prospective_all: list[dict[str, Any]] = []
    contemporaneous_all: list[dict[str, Any]] = []
    lagged_all: list[dict[str, Any]] = []
    prediction_all: list[dict[str, Any]] = []
    benefit_all: list[dict[str, Any]] = []
    permutation_all: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        contemporaneous_all.append(
            contemporaneous_response_row(bundle_groups.get(key, ()))
        )
        prospective = prospective_rows(
            bundle_groups.get(key, ()),
            group,
            hue_bandwidth_degree=hue_bandwidth_degree,
            bpm_bandwidth=bpm_bandwidth,
            minimum_history_count=minimum_history_count,
        )
        prospective_all.extend(prospective)
        lagged_all.append(lagged_coupling_row(group, prospective))
        prediction_all.append(prediction_metrics_row(group, prospective))
        benefit_all.append(rmssd_benefit_row(group))
        permutation_all.append(
            permutation_null_row(group, permutation_count=permutation_count)
        )
    paired = paired_arm_difference_rows(benefit_all, lagged_all, sessions)
    effects = participant_effect_rows(
        paired,
        benefit_all,
        permutation_all,
        sessions,
        classification_policy=classification_policy,
    )
    user_types = participant_level_summary_rows(effects, paired)
    overall = overall_summary_rows(effects, paired)
    return {
        "contemporaneous": tuple(contemporaneous_all),
        "prospective": tuple(prospective_all),
        "lagged": tuple(lagged_all),
        "prediction": tuple(prediction_all),
        "benefits": tuple(benefit_all),
        "paired": paired,
        "permutation": tuple(permutation_all),
        "participant_effects": effects,
        "user_type_summary": user_types,
        "overall_summary": overall,
        "user_type_trajectory": user_type_trajectory_rows(sessions),
    }


__all__ = [
    "BOOTSTRAP_POLICY_VERSION",
    "CLASSIFICATION_POLICY_VERSION",
    "PARTICIPANT_CLASSIFICATIONS",
    "PERMUTATION_POLICY_VERSION",
    "analyze_validation_records",
    "bootstrap_interval",
    "bootstrap_median_interval",
    "bpm_history_score",
    "circular_hue_distance",
    "circular_linear_correlation",
    "circular_mean_and_concentration",
    "classify_participant_effect",
    "counterfactual_percentile",
    "contemporaneous_response_row",
    "deterministic_counterfactual_set",
    "full_pattern_history_score",
    "gaussian_kernel",
    "history_before_session",
    "lagged_coupling_row",
    "life_history_score",
    "linear_slope",
    "paired_arm_difference_rows",
    "pattern_closeness",
    "pearson_correlation",
    "permutation_null_row",
    "prediction_metrics_row",
    "prospective_rows",
    "rmssd_benefit_row",
    "session_block_bootstrap_interval",
    "spearman_correlation",
    "user_type_trajectory_rows",
]
