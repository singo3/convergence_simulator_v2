"""Stage 4 Garden phase and evaluation vocabulary."""

from enum import StrEnum


class GardenPhase(StrEnum):
    BASELINE_DISCARD = "baseline_discard"
    BASELINE_EVALUATION = "baseline_evaluation"
    BUNDLE_0_DISCARD = "bundle_0_discard"
    BUNDLE_0_EVALUATION = "bundle_0_evaluation"
    BUNDLE_1_DISCARD = "bundle_1_discard"
    BUNDLE_1_EVALUATION = "bundle_1_evaluation"
    BUNDLE_2_DISCARD = "bundle_2_discard"
    BUNDLE_2_EVALUATION = "bundle_2_evaluation"
    OUTSIDE = "outside"


class GardenWindowRole(StrEnum):
    DISCARD = "discard"
    EVALUATION = "evaluation"
    OUTSIDE = "outside"


class GardenEvaluationKind(StrEnum):
    BASELINE = "baseline"
    BUNDLE = "bundle"


class GardenEvaluationQuality(StrEnum):
    VALID = "valid"
    LOW_CONFIDENCE = "low_confidence"
    REJECTED = "rejected"


class GardenSessionStatus(StrEnum):
    BASELINE = "baseline"
    ACTIVE = "active"
    BASELINE_INVALID = "baseline_invalid"
    COMPLETED = "completed"
