"""Stage 8A observable rolling convergence and separate truth diagnostics."""

from .clustering import PatternCluster, select_dominant_cluster
from .config import (
    MAXIMUM_BOUNDED_WINDOW_SESSIONS,
    ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION,
    ROLLING_PATTERN_CONVERGENCE_CONFIG_SCHEMA_VERSION,
    RollingConvergenceConfig,
)
from .evaluator import (
    RollingConvergenceEvaluator,
    evaluate_convergence_history,
    evaluate_rolling_convergence,
)
from .pattern_distance import pattern_distance, patterns_are_near
from .records import (
    CONVERGENCE_STATES,
    ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION,
    RollingConvergenceRecord,
    SessionPatternObservation,
)
from .truth_alignment import evaluate_truth_alignment
from .truth_records import (
    STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION,
    TRUTH_CLASSIFICATIONS,
    TruthAlignmentRecord,
)

__all__ = [
    "CONVERGENCE_STATES",
    "MAXIMUM_BOUNDED_WINDOW_SESSIONS",
    "PatternCluster",
    "ROLLING_CONVERGENCE_RECORD_SCHEMA_VERSION",
    "ROLLING_MAJORITY_PATTERN_CONVERGENCE_VERSION",
    "ROLLING_PATTERN_CONVERGENCE_CONFIG_SCHEMA_VERSION",
    "RollingConvergenceConfig",
    "RollingConvergenceEvaluator",
    "RollingConvergenceRecord",
    "STATIONARY_LANDSCAPE_TRUTH_ALIGNMENT_VERSION",
    "SessionPatternObservation",
    "TRUTH_CLASSIFICATIONS",
    "TruthAlignmentRecord",
    "evaluate_convergence_history",
    "evaluate_rolling_convergence",
    "evaluate_truth_alignment",
    "pattern_distance",
    "patterns_are_near",
    "select_dominant_cluster",
]
