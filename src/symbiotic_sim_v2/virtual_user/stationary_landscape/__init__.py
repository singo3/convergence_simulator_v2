"""Stage 8A fixed user-type preference landscapes."""

from .component_factory import (
    StationaryLandscapeLightResponseConfig,
    StationaryStage7PreferenceEvaluator,
    stationary_light_response_config,
    stationary_preference_evaluator,
)
from .config import (
    MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION,
    STATIONARY_GAUSSIAN_PEAK_VERSION,
    STATIONARY_PREFERENCE_LANDSCAPE_VERSION,
    STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION,
    StationaryPreferencePeak,
    StationaryUserTypeProfile,
)
from .evaluator import evaluate_stationary_preference
from .peak import circular_hue_distance, evaluate_peak_match, gaussian_match
from .presets import (
    DEFAULT_STATIONARY_USER_TYPE,
    STATIONARY_USER_TYPE_IDS,
    stationary_user_type_ids,
    stationary_user_type_profile,
)
from .records import StationaryPeakMatch, StationaryPreferenceMatch

__all__ = [
    "DEFAULT_STATIONARY_USER_TYPE",
    "MAXIMUM_WEIGHTED_PEAK_RESPONSE_VERSION",
    "STATIONARY_GAUSSIAN_PEAK_VERSION",
    "STATIONARY_PREFERENCE_LANDSCAPE_VERSION",
    "STATIONARY_USER_TYPE_IDS",
    "STATIONARY_USER_TYPE_PROFILE_SCHEMA_VERSION",
    "StationaryLandscapeLightResponseConfig",
    "StationaryPeakMatch",
    "StationaryPreferenceMatch",
    "StationaryPreferencePeak",
    "StationaryStage7PreferenceEvaluator",
    "StationaryUserTypeProfile",
    "circular_hue_distance",
    "evaluate_peak_match",
    "evaluate_stationary_preference",
    "gaussian_match",
    "stationary_light_response_config",
    "stationary_preference_evaluator",
    "stationary_user_type_ids",
    "stationary_user_type_profile",
]
