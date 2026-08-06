"""Participant-paired two-by-two main effects and interaction."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.analysis import (
    bootstrap_interval,
)

from .conditions import (
    FULL_RECOVERY_SIGMA100_CONDITION,
    PROVISIONAL_CONDITION,
    V2_RECOVERY_SIGMA050_CONDITION,
    V2_REFERENCE_CONDITION,
)
from .config import FACTORIAL_ANALYSIS_VERSION

FACTORIAL_OUTCOMES: Mapping[str, str] = {
    "late_delta_rmssd_advantage_ms": "late_delta_rmssd_advantage_ms",
    "late_minus_early_advantage_ms": "late_minus_early_advantage_ms",
    "slope_advantage": "slope_advantage",
    "selection_enrichment_advantage": ("full_pattern_selection_enrichment_advantage"),
    "lagged_coupling_advantage": "lagged_pattern_advantage",
    "holder_switch_rate": "autonomous_holder_switch_rate",
    "accepted_candidate_count": "accepted_candidate_count",
}


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("factorial outcome must be numeric or null")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("factorial outcome must be finite")
    return converted


def two_by_two_effects(
    *,
    a: object,
    b: object,
    c: object,
    d: object,
) -> dict[str, float | None]:
    values = tuple(_optional_number(item) for item in (a, b, c, d))
    if any(item is None for item in values):
        return {
            "sigma_effect_gradual_b_minus_a": None,
            "sigma_effect_full_d_minus_c": None,
            "recovery_effect_sigma100_c_minus_a": None,
            "recovery_effect_sigma050_d_minus_b": None,
            "interaction_sigma_by_recovery": None,
            "interaction_recovery_by_sigma": None,
            "interaction_identity_error": None,
        }
    a_value, b_value, c_value, d_value = (float(item) for item in values)
    sigma_gradual = b_value - a_value
    sigma_full = d_value - c_value
    recovery_sigma100 = c_value - a_value
    recovery_sigma050 = d_value - b_value
    interaction = sigma_full - sigma_gradual
    interaction_alt = recovery_sigma050 - recovery_sigma100
    return {
        "sigma_effect_gradual_b_minus_a": sigma_gradual,
        "sigma_effect_full_d_minus_c": sigma_full,
        "recovery_effect_sigma100_c_minus_a": recovery_sigma100,
        "recovery_effect_sigma050_d_minus_b": recovery_sigma050,
        "interaction_sigma_by_recovery": interaction,
        "interaction_recovery_by_sigma": interaction_alt,
        "interaction_identity_error": interaction - interaction_alt,
    }


def factorial_participant_effect_rows(
    participant_condition_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    grouped: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in participant_condition_rows:
        grouped[(str(row["participant_id"]), str(row["user_type_id"]))][
            str(row["condition_id"])
        ] = row
    result: list[dict[str, Any]] = []
    required = {
        V2_REFERENCE_CONDITION,
        V2_RECOVERY_SIGMA050_CONDITION,
        FULL_RECOVERY_SIGMA100_CONDITION,
        PROVISIONAL_CONDITION,
    }
    for (participant_id, user_type_id), conditions in sorted(grouped.items()):
        if set(conditions) != required:
            raise ValueError(f"participant {participant_id} does not have all four conditions")
        for outcome_name, field_name in FACTORIAL_OUTCOMES.items():
            effects = two_by_two_effects(
                a=conditions[V2_REFERENCE_CONDITION].get(field_name),
                b=conditions[V2_RECOVERY_SIGMA050_CONDITION].get(field_name),
                c=conditions[FULL_RECOVERY_SIGMA100_CONDITION].get(field_name),
                d=conditions[PROVISIONAL_CONDITION].get(field_name),
            )
            result.append(
                {
                    "participant_id": participant_id,
                    "user_type_id": user_type_id,
                    "outcome": outcome_name,
                    "a_v2_reference": conditions[V2_REFERENCE_CONDITION].get(field_name),
                    "b_v2_recovery_sigma050": conditions[V2_RECOVERY_SIGMA050_CONDITION].get(
                        field_name
                    ),
                    "c_full_recovery_sigma100": conditions[FULL_RECOVERY_SIGMA100_CONDITION].get(
                        field_name
                    ),
                    "d_provisional_f15_sigma050": conditions[PROVISIONAL_CONDITION].get(field_name),
                    **effects,
                    "analysis_version": FACTORIAL_ANALYSIS_VERSION,
                }
            )
    return tuple(result)


_EFFECT_FIELDS = (
    "sigma_effect_gradual_b_minus_a",
    "sigma_effect_full_d_minus_c",
    "recovery_effect_sigma100_c_minus_a",
    "recovery_effect_sigma050_d_minus_b",
    "interaction_sigma_by_recovery",
)


def _aggregate_effect_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    group_fields: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(str(row[field]) for field in group_fields)].append(row)
    result: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        base = dict(zip(group_fields, key, strict=True))
        output: dict[str, Any] = {
            **base,
            "participant_count": len({str(item["participant_id"]) for item in group}),
            "analysis_version": FACTORIAL_ANALYSIS_VERSION,
        }
        for field in _EFFECT_FIELDS:
            values = [float(item[field]) for item in group if item.get(field) is not None]
            lower, upper = bootstrap_interval(
                values,
                seed_parts=(*key, field, FACTORIAL_ANALYSIS_VERSION),
            )
            output[f"{field}_mean"] = None if not values else statistics.fmean(values)
            output[f"{field}_lower95"] = lower
            output[f"{field}_upper95"] = upper
            output[f"{field}_valid_participant_count"] = len(values)
        result.append(output)
    return tuple(result)


def factorial_user_type_effect_rows(
    participant_effects: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    return _aggregate_effect_rows(
        participant_effects,
        group_fields=("user_type_id", "outcome"),
    )


def factorial_overall_effect_rows(
    participant_effects: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    return _aggregate_effect_rows(participant_effects, group_fields=("outcome",))


__all__ = [
    "FACTORIAL_OUTCOMES",
    "factorial_overall_effect_rows",
    "factorial_participant_effect_rows",
    "factorial_user_type_effect_rows",
    "two_by_two_effects",
]
