"""Stage 8A.1 observable structured convergence and separate audit helpers."""

from .bpm_common import evaluate_bpm_common
from .classification import classify_structured_convergence
from .config import (
    STRUCTURED_CONVERGENCE_CONFIG_SCHEMA_VERSION,
    STRUCTURED_CONVERGENCE_CONFIG_VERSION,
    STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION,
    StructuredConvergenceConfig,
)
from .evaluator import (
    StructuredConvergenceEvaluator,
    evaluate_structured_convergence_history,
)
from .life_dominance import evaluate_life_dominance
from .mechanical_rotation import (
    evaluate_e_driven_switches,
    evaluate_mechanical_rotation,
)
from .multi_attractor import evaluate_multi_attractor
from .records import (
    STRUCTURED_CONVERGENCE_RECORD_SCHEMA_VERSION,
    STRUCTURED_SESSION_OBSERVATION_SCHEMA_VERSION,
    SUMMARY_CLASSIFICATIONS,
    BpmCommonRecord,
    EDrivenSwitchRecord,
    LifeAttractorRecord,
    LifeDominanceRecord,
    MechanicalRotationRecord,
    MultiAttractorRecord,
    StructuredConvergenceRecord,
    StructuredSessionObservation,
)
from .truth_alignment import (
    STRUCTURED_TRUTH_ALIGNMENT_VERSION,
    TRUTH_CLASSIFICATIONS_V2,
    CommittedPreferenceMatch,
    PeakHitCount,
    StructuredTruthAlignmentRecord,
    evaluate_structured_truth_alignment,
)
from .w_ceiling import (
    W_CEILING_CLASSIFICATIONS,
    W_CEILING_DIAGNOSTIC_VERSION,
    WCeilingDiagnosticRecord,
    WCeilingObservation,
    evaluate_w_ceiling,
)

__all__ = [
    "BpmCommonRecord",
    "CommittedPreferenceMatch",
    "EDrivenSwitchRecord",
    "LifeAttractorRecord",
    "LifeDominanceRecord",
    "MechanicalRotationRecord",
    "MultiAttractorRecord",
    "PeakHitCount",
    "STRUCTURED_CONVERGENCE_CONFIG_SCHEMA_VERSION",
    "STRUCTURED_CONVERGENCE_CONFIG_VERSION",
    "STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION",
    "STRUCTURED_CONVERGENCE_RECORD_SCHEMA_VERSION",
    "STRUCTURED_SESSION_OBSERVATION_SCHEMA_VERSION",
    "STRUCTURED_TRUTH_ALIGNMENT_VERSION",
    "SUMMARY_CLASSIFICATIONS",
    "StructuredConvergenceConfig",
    "StructuredConvergenceEvaluator",
    "StructuredConvergenceRecord",
    "StructuredSessionObservation",
    "StructuredTruthAlignmentRecord",
    "TRUTH_CLASSIFICATIONS_V2",
    "W_CEILING_CLASSIFICATIONS",
    "W_CEILING_DIAGNOSTIC_VERSION",
    "WCeilingDiagnosticRecord",
    "WCeilingObservation",
    "classify_structured_convergence",
    "evaluate_bpm_common",
    "evaluate_e_driven_switches",
    "evaluate_life_dominance",
    "evaluate_mechanical_rotation",
    "evaluate_multi_attractor",
    "evaluate_structured_convergence_history",
    "evaluate_structured_truth_alignment",
    "evaluate_w_ceiling",
]
