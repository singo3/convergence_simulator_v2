"""Canonical Stage 5C digests and observation-only CSV exports."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from .adaptive_component import AdaptiveConnectedDigitalLifeComponent
from .records import canonical_digest

INTRINSIC_PROFILES_CSV_FILENAME = (
    "stage_05c_relation_memory_intrinsic_profiles.csv"
)
RELATION_TRANSITIONS_CSV_FILENAME = "stage_05c_relation_memory_transitions.csv"
ADAPTIVE_SIGNALS_CSV_FILENAME = "stage_05c_adaptive_digital_life_signals.csv"
PERSISTENT_STATES_CSV_FILENAME = "stage_05c_relation_memory_persistent_states.csv"
SESSION_SUMMARY_CSV_FILENAME = "stage_05c_relation_memory_session_summary.csv"

INTRINSIC_PROFILES_CSV_FIELDS = (
    "digital_life_id",
    "curiosity",
    "sigma_min",
    "sigma_max",
    "epsilon_accept",
    "p_explore_min",
    "algorithm_version",
)
RELATION_TRANSITIONS_CSV_FIELDS = (
    "transition_index",
    "signal_index",
    "signal_time_us",
    "digital_life_id",
    "g",
    "bundle_index",
    "evaluation_id",
    "evaluation_quality",
    "evaluation_is_valid",
    "w",
    "phase_before",
    "phase_after",
    "exploration_decision",
    "curiosity",
    "sigma_min",
    "sigma_max",
    "sigma",
    "epsilon_accept",
    "p_explore_min",
    "p_explore",
    "u_explore",
    "direction_trial_index",
    "direction_u_f",
    "direction_u_t",
    "direction_norm",
    "direction_xi",
    "k_anchor_before",
    "k_current_before",
    "k_trial",
    "k_current_after",
    "k_anchor_after",
    "w_anchor_session_before",
    "w_anchor_session_after",
    "w_trial_1_before",
    "w_trial_1_after",
    "w_trial_2_before",
    "w_trial_2_after",
    "provisional_condition",
    "confirmation_condition_1",
    "confirmation_condition_2",
    "candidate_mean_w",
    "trial_count_before",
    "trial_count_after",
    "session_count_used",
    "session_count_after",
    "adoption_result",
    "rollback_reason",
    "candidate_effective_signal_index",
    "relation_update_effective_policy_version",
    "algorithm_version",
    "state_schema_version",
    "schema_version",
)
ADAPTIVE_SIGNALS_CSV_FIELDS = (
    "signal_index",
    "signal_time_us",
    "digital_life_id",
    "role",
    "s",
    "bundle_index",
    "phase",
    "evaluation_id",
    "evaluation_quality",
    "is_new_valid_evaluation",
    "g",
    "w",
    "k_anchor_before",
    "k_current_before",
    "k_presented",
    "b_presented",
    "relation_phase_before",
    "relation_phase_after",
    "k_current_after",
    "k_anchor_after",
    "candidate_effective_next_signal",
    "q_before",
    "q_after",
    "e_before",
    "e_after",
    "schema_version",
)
PERSISTENT_STATES_CSV_FIELDS = (
    "record_index",
    "state_position",
    "digital_life_id",
    "k_anchor",
    "q",
    "e",
    "trial_count",
    "session_count",
    "profile_version",
    "algorithm_version",
    "state_schema_version",
    "schema_version",
)
SESSION_SUMMARY_CSV_FIELDS = (
    "digital_life_id",
    "holder_status",
    "adaptation_phase",
    "exploration_decision",
    "w_anchor_session",
    "w_trial_1",
    "w_trial_2",
    "sigma",
    "p_explore",
    "u_explore",
    "epsilon_accept",
    "initial_k_anchor",
    "k_trial_audit",
    "candidate_generated",
    "adoption_result",
    "rollback_reason",
    "trial_count_before",
    "trial_count_after",
    "session_count_before",
    "session_count_after",
    "k_anchor_update_count",
    "k_current_transition_count",
    "final_k_anchor",
)


def _components(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> tuple[AdaptiveConnectedDigitalLifeComponent, ...]:
    if not isinstance(components, Mapping):
        raise TypeError("components must be a mapping")
    if any(
        key != component.config.digital_life_id
        for key, component in components.items()
        if isinstance(component, AdaptiveConnectedDigitalLifeComponent)
    ):
        raise ValueError("component IDs do not match their mapping keys")
    ordered = tuple(components[life_id] for life_id in sorted(components))
    if len(ordered) != 3 or any(
        not isinstance(component, AdaptiveConnectedDigitalLifeComponent)
        for component in ordered
    ):
        raise ValueError("Stage 5C diagnostics require exactly three adaptive lives")
    return ordered


def intrinsic_profile_rows(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> tuple[dict[str, object], ...]:
    return tuple(
        component.relation_memory_intrinsic_profile().to_dict()
        for component in _components(components)
    )


def relation_transition_rows(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> tuple[dict[str, object], ...]:
    records = [
        record
        for component in _components(components)
        for record in component.relation_memory_transition_records()
    ]
    records.sort(key=lambda record: (record.signal_index, record.digital_life_id))
    return tuple(record.to_dict() for record in records)


def adaptive_signal_rows(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> tuple[dict[str, object], ...]:
    records = [
        record
        for component in _components(components)
        for record in component.adaptive_signal_records()
    ]
    records.sort(key=lambda record: (record.signal_index, record.digital_life_id))
    return tuple(record.to_dict() for record in records)


def persistent_state_rows(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> tuple[dict[str, object], ...]:
    return tuple(
        record.to_dict()
        for component in _components(components)
        for record in component.persistent_state_records()
    )


def session_summary_rows(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for component in _components(components):
        session = component.relation_memory_session_state()
        initial = component.initial_persistent_state()
        final = component.final_persistent_state()
        if final is None:
            raise RuntimeError("session summary requires a normally finalized session")
        transitions = component.relation_memory_transition_records()
        candidate = next(
            (record.k_trial for record in transitions if record.k_trial is not None),
            None,
        )
        holder_status = any(record.g == 1 for record in component.adaptive_signal_records())
        rows.append(
            {
                "digital_life_id": component.config.digital_life_id,
                "holder_status": holder_status,
                "adaptation_phase": session.adaptation_phase,
                "exploration_decision": session.exploration_decision,
                "w_anchor_session": session.w_anchor_session,
                "w_trial_1": session.w_trial_1,
                "w_trial_2": session.w_trial_2,
                "sigma": session.sigma,
                "p_explore": session.p_explore,
                "u_explore": session.u_explore,
                "epsilon_accept": session.epsilon_accept,
                "initial_k_anchor": initial.k_anchor,
                "k_trial_audit": candidate,
                "candidate_generated": session.candidate_generated,
                "adoption_result": session.adoption_result,
                "rollback_reason": session.rollback_reason,
                "trial_count_before": initial.trial_count,
                "trial_count_after": final.trial_count,
                "session_count_before": initial.session_count,
                "session_count_after": final.session_count,
                "k_anchor_update_count": component.k_anchor_update_count(),
                "k_current_transition_count": component.k_current_transition_count(),
                "final_k_anchor": final.k_anchor,
            }
        )
    return tuple(rows)


def intrinsic_profile_digest(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> str:
    return canonical_digest(intrinsic_profile_rows(components))


def adaptive_signal_digest(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> str:
    return canonical_digest(adaptive_signal_rows(components))


def relation_memory_transition_digest(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> str:
    return canonical_digest(relation_transition_rows(components))


def final_persistent_state_digest(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> str:
    states = []
    for component in _components(components):
        state = component.final_persistent_state()
        if state is None:
            raise RuntimeError("final persistent digest requires normal session closing")
        states.append(state.to_dict())
    return canonical_digest(states)


def session_summary_digest(
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> str:
    return canonical_digest(session_summary_rows(components))


def export_relation_memory_diagnostics(
    destination: str | Path,
    components: Mapping[str, AdaptiveConnectedDigitalLifeComponent],
) -> tuple[Path, Path, Path, Path, Path]:
    """Write all five CSVs without changing simulation state or any digest."""

    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    return (
        _write_rows(
            root / INTRINSIC_PROFILES_CSV_FILENAME,
            INTRINSIC_PROFILES_CSV_FIELDS,
            intrinsic_profile_rows(components),
        ),
        _write_rows(
            root / RELATION_TRANSITIONS_CSV_FILENAME,
            RELATION_TRANSITIONS_CSV_FIELDS,
            relation_transition_rows(components),
        ),
        _write_rows(
            root / ADAPTIVE_SIGNALS_CSV_FILENAME,
            ADAPTIVE_SIGNALS_CSV_FIELDS,
            adaptive_signal_rows(components),
        ),
        _write_rows(
            root / PERSISTENT_STATES_CSV_FILENAME,
            PERSISTENT_STATES_CSV_FIELDS,
            persistent_state_rows(components),
        ),
        _write_rows(
            root / SESSION_SUMMARY_CSV_FILENAME,
            SESSION_SUMMARY_CSV_FIELDS,
            session_summary_rows(components),
        ),
    )


def _csv_cell(value: object) -> object:
    if isinstance(value, (tuple, list, dict)):
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    return value


def _write_rows(
    path: Path,
    fields: Sequence[str],
    rows: Iterable[Mapping[str, object]],
) -> Path:
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(
            {field: _csv_cell(row[field]) for field in fields} for row in rows
        )
    return path


__all__ = [
    "ADAPTIVE_SIGNALS_CSV_FIELDS",
    "ADAPTIVE_SIGNALS_CSV_FILENAME",
    "INTRINSIC_PROFILES_CSV_FIELDS",
    "INTRINSIC_PROFILES_CSV_FILENAME",
    "PERSISTENT_STATES_CSV_FIELDS",
    "PERSISTENT_STATES_CSV_FILENAME",
    "RELATION_TRANSITIONS_CSV_FIELDS",
    "RELATION_TRANSITIONS_CSV_FILENAME",
    "SESSION_SUMMARY_CSV_FIELDS",
    "SESSION_SUMMARY_CSV_FILENAME",
    "adaptive_signal_digest",
    "adaptive_signal_rows",
    "export_relation_memory_diagnostics",
    "final_persistent_state_digest",
    "intrinsic_profile_digest",
    "intrinsic_profile_rows",
    "persistent_state_rows",
    "relation_memory_transition_digest",
    "relation_transition_rows",
    "session_summary_digest",
    "session_summary_rows",
]
