"""Versioned constants for the Stage 5C relation-memory core."""

from __future__ import annotations

from symbiotic_sim_v2.digital_life.config import (
    ALGORITHM_VERSION,
    PROFILE_VERSION,
    STATE_SCHEMA_VERSION,
)

ADAPTIVE_DIGITAL_LIFE_MODEL_VERSION = (
    "adaptive_relation_memory_connected_life_v0_1"
)

RELATION_MEMORY_INTRINSIC_PROFILE_SCHEMA_VERSION = (
    "relation_memory_intrinsic_profile_v1"
)
RELATION_MEMORY_PERSISTENT_STATE_RECORD_SCHEMA_VERSION = (
    "relation_memory_persistent_state_record_v1"
)
RELATION_MEMORY_SESSION_STATE_RECORD_SCHEMA_VERSION = (
    "relation_memory_session_state_record_v1"
)
RELATION_MEMORY_TRANSITION_RECORD_SCHEMA_VERSION = (
    "relation_memory_transition_record_v1"
)
ADAPTIVE_DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION = (
    "adaptive_digital_life_second_round_record_v1"
)
ADAPTIVE_DIGITAL_LIFE_SIGNAL_RECORD_SCHEMA_VERSION = (
    "adaptive_digital_life_signal_record_v1"
)

RELATION_UPDATE_EFFECTIVE_POLICY_VERSION = (
    "relation_update_effective_next_signal_v0_1"
)
BUNDLE1_REJECT_POLICY_VERSION = (
    "keep_same_trial_for_bundle2_but_require_two_valid_trial_evaluations_v0_1"
)
DIRECTION_FALLBACK_POLICY_VERSION = (
    "positive_f_axis_on_near_zero_direction_norm_v0_1"
)
DIRECTION_NEAR_ZERO_NORM_THRESHOLD = 1.0e-12

ADAPTATION_PHASES = frozenset(
    {
        "anchor_evaluation",
        "hold",
        "trial",
        "confirmation",
        "return_anchor",
        "trial_unconfirmed",
        "accepted",
        "rejected",
        "completed_non_holder",
        "completed_bundle0_rejected",
    }
)
EXPLORATION_DECISIONS = frozenset({"hold", "explore"})
ADOPTION_RESULTS = frozenset(
    {
        "pending",
        "hold",
        "accepted",
        "rejected_bundle1_threshold",
        "rejected_after_confirmation",
        "unconfirmed_evaluation_reject",
        "bundle0_evaluation_rejected",
        "non_holder_no_adaptation",
        "no_candidate",
        "rolled_back_at_session_end",
    }
)

PERSISTENT_STATE_SCOPE_BY_FIELD = {
    "k_anchor": "digital_life_core",
    "q": "digital_life_core",
    "e": "user_garden",
    "trial_count": "digital_life_core",
    "session_count": "digital_life_core",
}

__all__ = [
    "ADAPTATION_PHASES",
    "ADAPTIVE_DIGITAL_LIFE_MODEL_VERSION",
    "ADAPTIVE_DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION",
    "ADAPTIVE_DIGITAL_LIFE_SIGNAL_RECORD_SCHEMA_VERSION",
    "ADOPTION_RESULTS",
    "ALGORITHM_VERSION",
    "BUNDLE1_REJECT_POLICY_VERSION",
    "DIRECTION_FALLBACK_POLICY_VERSION",
    "DIRECTION_NEAR_ZERO_NORM_THRESHOLD",
    "EXPLORATION_DECISIONS",
    "PERSISTENT_STATE_SCOPE_BY_FIELD",
    "PROFILE_VERSION",
    "RELATION_MEMORY_INTRINSIC_PROFILE_SCHEMA_VERSION",
    "RELATION_MEMORY_PERSISTENT_STATE_RECORD_SCHEMA_VERSION",
    "RELATION_MEMORY_SESSION_STATE_RECORD_SCHEMA_VERSION",
    "RELATION_MEMORY_TRANSITION_RECORD_SCHEMA_VERSION",
    "RELATION_UPDATE_EFFECTIVE_POLICY_VERSION",
    "STATE_SCHEMA_VERSION",
]
