"""Stage 8A.3 adaptive, yoked-placebo, and random RMSSD validation."""

from .config import (
    ARM_IDS,
    AUTONOMOUS_ARM,
    RANDOM_ARM,
    VALIDATION_MODEL_VERSION,
    YOKED_ARM,
    ArmContract,
    ValidationCondition,
    ValidationConfig,
    ValidationParticipant,
    arm_contract,
)
from .records import BundleOutcome, ReplayLightState, SessionOutcome
from .runner import AdaptivePlaceboValidationRunner, ValidationRunSummary

__all__ = [
    "ARM_IDS",
    "AdaptivePlaceboValidationRunner",
    "AUTONOMOUS_ARM",
    "RANDOM_ARM",
    "VALIDATION_MODEL_VERSION",
    "YOKED_ARM",
    "ArmContract",
    "BundleOutcome",
    "ReplayLightState",
    "SessionOutcome",
    "ValidationCondition",
    "ValidationConfig",
    "ValidationParticipant",
    "ValidationRunSummary",
    "arm_contract",
]
