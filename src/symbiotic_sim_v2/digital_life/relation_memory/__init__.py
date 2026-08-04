"""GUI-independent Stage 5C confirmed relation-memory search core."""

from .adaptive_component import AdaptiveConnectedDigitalLifeComponent
from .candidate import generate_candidate
from .config import (
    ADAPTATION_PHASES,
    ADAPTIVE_DIGITAL_LIFE_MODEL_VERSION,
    ADAPTIVE_DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION,
    ADAPTIVE_DIGITAL_LIFE_SIGNAL_RECORD_SCHEMA_VERSION,
    ADOPTION_RESULTS,
    BUNDLE1_REJECT_POLICY_VERSION,
    DIRECTION_FALLBACK_POLICY_VERSION,
    EXPLORATION_DECISIONS,
    PERSISTENT_STATE_SCOPE_BY_FIELD,
    RELATION_MEMORY_INTRINSIC_PROFILE_SCHEMA_VERSION,
    RELATION_MEMORY_PERSISTENT_STATE_RECORD_SCHEMA_VERSION,
    RELATION_MEMORY_SESSION_STATE_RECORD_SCHEMA_VERSION,
    RELATION_MEMORY_TRANSITION_RECORD_SCHEMA_VERSION,
    RELATION_UPDATE_EFFECTIVE_POLICY_VERSION,
)
from .direction import RelationMemorySearchDirection, derive_search_direction
from .intrinsic import (
    RelationMemoryIntrinsicProfile,
    derive_relation_memory_intrinsic_profile,
    exploration_decision,
    exploration_probability,
    exploration_sigma,
    relation_search_radius,
    should_explore,
)
from .persistent_state import RelationMemoryPersistentState
from .records import (
    AdaptiveDigitalLifeSecondRoundRecord,
    AdaptiveDigitalLifeSignalRecord,
    RelationMemoryPersistentStateRecord,
    RelationMemorySessionStateRecord,
    RelationMemoryTransitionRecord,
    canonical_digest,
)
from .reflect import reflect01, reflect01_vector
from .session_state import RelationMemorySessionState
from .state_io import (
    export_relation_memory_state_file,
    load_relation_memory_state_file,
    relation_memory_state_map_from_dict,
    relation_memory_state_map_from_json,
    relation_memory_state_map_to_dict,
    relation_memory_state_map_to_json,
)
from .transitions import (
    RelationMemoryTransitionInput,
    RelationMemoryTransitionResult,
    apply_relation_memory_transition,
    apply_relation_memory_transition_with_sigma_multiplier,
    current_relation_k,
)

__all__ = [
    "ADAPTATION_PHASES",
    "ADAPTIVE_DIGITAL_LIFE_MODEL_VERSION",
    "ADAPTIVE_DIGITAL_LIFE_SECOND_ROUND_RECORD_SCHEMA_VERSION",
    "ADAPTIVE_DIGITAL_LIFE_SIGNAL_RECORD_SCHEMA_VERSION",
    "ADOPTION_RESULTS",
    "AdaptiveConnectedDigitalLifeComponent",
    "AdaptiveDigitalLifeSecondRoundRecord",
    "AdaptiveDigitalLifeSignalRecord",
    "BUNDLE1_REJECT_POLICY_VERSION",
    "DIRECTION_FALLBACK_POLICY_VERSION",
    "EXPLORATION_DECISIONS",
    "PERSISTENT_STATE_SCOPE_BY_FIELD",
    "RELATION_MEMORY_INTRINSIC_PROFILE_SCHEMA_VERSION",
    "RELATION_MEMORY_PERSISTENT_STATE_RECORD_SCHEMA_VERSION",
    "RELATION_MEMORY_SESSION_STATE_RECORD_SCHEMA_VERSION",
    "RELATION_MEMORY_TRANSITION_RECORD_SCHEMA_VERSION",
    "RELATION_UPDATE_EFFECTIVE_POLICY_VERSION",
    "RelationMemoryIntrinsicProfile",
    "RelationMemoryPersistentState",
    "RelationMemoryPersistentStateRecord",
    "RelationMemorySearchDirection",
    "RelationMemorySessionState",
    "RelationMemorySessionStateRecord",
    "RelationMemoryTransitionInput",
    "RelationMemoryTransitionRecord",
    "RelationMemoryTransitionResult",
    "apply_relation_memory_transition",
    "apply_relation_memory_transition_with_sigma_multiplier",
    "canonical_digest",
    "current_relation_k",
    "derive_relation_memory_intrinsic_profile",
    "derive_search_direction",
    "export_relation_memory_state_file",
    "exploration_decision",
    "exploration_probability",
    "exploration_sigma",
    "generate_candidate",
    "load_relation_memory_state_file",
    "reflect01",
    "reflect01_vector",
    "relation_memory_state_map_from_dict",
    "relation_memory_state_map_from_json",
    "relation_memory_state_map_to_dict",
    "relation_memory_state_map_to_json",
    "relation_search_radius",
    "should_explore",
]
