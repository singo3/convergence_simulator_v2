"""Stage 8A fixed-preference multi-session orchestration and diagnostics."""

from .comparison import (
    StationaryUserTypeComparison,
    StationaryUserTypeComparisonRow,
    compare_stationary_user_types,
)
from .config import (
    MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION,
    MultiSessionRunnerConfig,
)
from .diagnostics import (
    CONVERGENCE_HISTORY_CSV_FILENAME,
    PATTERN_TRAJECTORY_CSV_FILENAME,
    PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME,
    SESSION_OUTCOMES_CSV_FILENAME,
    STATIONARY_USER_TYPES_CSV_FILENAME,
    USER_TYPE_COMPARISON_CSV_FILENAME,
    convergence_history_digest,
    export_multi_session_diagnostics,
    final_multi_session_state_digest,
    multi_session_persistent_state_digest,
    multi_session_summary,
    session_outcome_digest,
    stationary_user_type_digest,
    user_type_comparison_digest,
)
from .runner import MultiSessionRelationMemoryRunner, SessionSimulationFactory
from .session_outcome import (
    BUNDLE_PRESENTATION_SCHEMA_VERSION,
    MULTI_SESSION_OUTCOME_SCHEMA_VERSION,
    BundleLightPresentation,
    SessionOutcome,
    session_outcome_from_simulation,
)
from .session_seed import (
    DEFAULT_MASTER_SEED,
    DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION,
    REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION,
    SESSION_DURATION_US,
    global_time_offset_us_for_session,
    global_time_us,
    physiology_root_seed_for_session,
)
from .state import (
    MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION,
    MultiSessionRelationState,
    export_multi_session_state_file,
    load_multi_session_state_file,
)

__all__ = [
    "BUNDLE_PRESENTATION_SCHEMA_VERSION",
    "BundleLightPresentation",
    "CONVERGENCE_HISTORY_CSV_FILENAME",
    "DEFAULT_MASTER_SEED",
    "DETERMINISTIC_PER_SESSION_PHYSIOLOGY_SEED_POLICY_VERSION",
    "MULTI_SESSION_OUTCOME_SCHEMA_VERSION",
    "MULTI_SESSION_RELATION_MEMORY_RUNNER_VERSION",
    "MULTI_SESSION_RELATION_STATE_SCHEMA_VERSION",
    "MultiSessionRelationMemoryRunner",
    "MultiSessionRelationState",
    "MultiSessionRunnerConfig",
    "PATTERN_TRAJECTORY_CSV_FILENAME",
    "PERSISTENT_STATE_TRAJECTORY_CSV_FILENAME",
    "REPEAT_SAME_PHYSIOLOGY_SEED_POLICY_VERSION",
    "SESSION_DURATION_US",
    "SESSION_OUTCOMES_CSV_FILENAME",
    "STATIONARY_USER_TYPES_CSV_FILENAME",
    "SessionOutcome",
    "SessionSimulationFactory",
    "StationaryUserTypeComparison",
    "StationaryUserTypeComparisonRow",
    "USER_TYPE_COMPARISON_CSV_FILENAME",
    "compare_stationary_user_types",
    "convergence_history_digest",
    "export_multi_session_diagnostics",
    "export_multi_session_state_file",
    "final_multi_session_state_digest",
    "global_time_offset_us_for_session",
    "global_time_us",
    "load_multi_session_state_file",
    "multi_session_persistent_state_digest",
    "multi_session_summary",
    "physiology_root_seed_for_session",
    "session_outcome_digest",
    "session_outcome_from_simulation",
    "stationary_user_type_digest",
    "user_type_comparison_digest",
]
