"""Versioned constants for the Stage 8A.1 experimental lab."""

from __future__ import annotations

PROJECT_VERSION = "0.11.0"

FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION = (
    "fatigue_exploration_convergence_lab_v0_1"
)
FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION = (
    "stage_08a1_fatigue_sigma_experiment_v0_1"
)
UNSELECTED_FULL_RECOVERY_POLICY_VERSION = (
    "unselected_full_recovery_at_session_end_v0_1"
)
GRADUAL_REFERENCE_ONLY_SESSION_END_POLICY_VERSION = (
    "gradual_reference_only_at_session_end_v0_1"
)
SELECTED_SESSION_FATIGUE_POLICY_VERSION = (
    "selected_session_saturating_fatigue_v0_1"
)
SCALED_REFERENCE_SIGMA_POLICY_VERSION = "scaled_reference_sigma_v0_1"
STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION = (
    "structured_convergence_diagnostics_v0_1"
)
PAIRED_REPLICATE_SEED_POLICY_VERSION = "paired_replicate_seed_policy_v0_1"
FATIGUE_SIGMA_CONDITION_SCHEMA_VERSION = "fatigue_sigma_condition_v1"
FATIGUE_SIGMA_REPLICATE_RESULT_SCHEMA_VERSION = (
    "fatigue_sigma_replicate_result_v1"
)
FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION = (
    "fatigue_sigma_session_outcome_v1"
)
FATIGUE_SIGMA_CONDITION_SUMMARY_SCHEMA_VERSION = (
    "fatigue_sigma_condition_summary_v1"
)
FATIGUE_SIGMA_GRID_SUMMARY_SCHEMA_VERSION = "fatigue_sigma_grid_summary_v1"
FATIGUE_SIGMA_EXPERIMENT_MANIFEST_SCHEMA_VERSION = (
    "fatigue_sigma_experiment_manifest_v1"
)
EXPERIMENTAL_MULTI_SESSION_STATE_SCHEMA_VERSION = (
    "fatigue_sigma_multi_session_state_v1"
)

BASE_PROFILE_VERSION = "symbiotic_signal_loop_reference_v1_0"
DOCUMENT_VERSION = "v2.0"
ALGORITHM_VERSION = "adaptive_random_search_confirmed_v1"
RELATION_MEMORY_STATE_SCHEMA_VERSION = "relation_memory_state_v2"

DEFAULT_USER_TYPE_V2 = "green_hue_dominant_broad_bpm"
DEFAULT_SELECTED_SESSION_FATIGUE_TARGET = 0.05
DEFAULT_UNSELECTED_SESSION_END_RECOVERY_FRACTION = 1.0
DEFAULT_SIGMA_MULTIPLIER = 1.0
DEFAULT_MAXIMUM_SESSIONS = 24
DEFAULT_MASTER_SEED = 20260802
DEFAULT_REPLICATE_COUNT = 5
MAXIMUM_TOTAL_SESSION_RUNS = 30_000

STANDARD_FATIGUE_TARGETS = (0.03, 0.05, 0.08, 0.10, 0.15)
STANDARD_SIGMA_MULTIPLIERS = (0.50, 0.75, 1.00, 1.25, 1.50)
QUICK_FATIGUE_TARGETS = (0.03, 0.08, 0.15)
QUICK_SIGMA_MULTIPLIERS = (0.50, 1.00, 1.50)

MODIFIED_FIELDS = (
    "selected fatigue accumulation target",
    "unselected session-end recovery policy",
    "exploration width multiplier",
)
UNCHANGED_REFERENCE_FIELDS = (
    "p_explore_min",
    "epsilon_accept",
    "q coefficients",
    "P mapping",
    "V mapping",
    "tau mapping",
    "RMSSD to N",
    "delta_N",
    "Bundle structure",
    "candidate confirmation rule",
)


__all__ = [name for name in globals() if name.isupper()]
